"""Hàng đợi uplink bền trên đĩa.

Mỗi bản tin có `id` 16 hex, được append vào `queue.jsonl` và `fsync` ngay.
Nhật ký là chuỗi thao tác (`add`, `ack`, `retry`, `drop`) nên sau khi khởi
động lại có thể dựng đúng trạng thái: không mất bản tin chưa gửi, không gửi
trùng bản tin đã được ack.

Thứ tự ưu tiên: `fault` > `motion` > `status` > `battery`/`temp`. Khi đầy,
bản tin ưu tiên thấp nhất bị bỏ và id bị bỏ được trả về (không im lặng).
"""

from __future__ import annotations

import json
import os
import random
import uuid
from collections import OrderedDict
from pathlib import Path

from .clock import Clock

__all__ = ["PRIORITY_RANK", "UplinkError", "UplinkQueue"]

PRIORITY_RANK: dict[str, int] = {
    "fault": 4,
    "motion": 3,
    "status": 2,
    "battery": 1,
    "temp": 1,
}

_HEX16 = set("0123456789abcdef")


class UplinkError(Exception):
    """Lỗi hàng đợi uplink."""


def _is_hex16(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 16
        and all(char in _HEX16 for char in value)
    )


class UplinkQueue:
    """Hàng đợi bền, ưu tiên và có backoff."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        clock: Clock,
        max_bytes: int,
        max_attempts: int = 6,
        *,
        base_delay_s: float = 2.0,
        max_delay_s: float = 300.0,
        jitter: float = 0.2,
        rng: random.Random | None = None,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes phai > 0")
        if max_attempts < 1:
            raise ValueError("max_attempts phai >= 1")
        if base_delay_s <= 0 or max_delay_s <= 0:
            raise ValueError("base_delay_s va max_delay_s phai > 0")
        if not 0.0 <= jitter < 1.0:
            raise ValueError("jitter phai trong [0, 1)")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._max_bytes = int(max_bytes)
        self._max_attempts = int(max_attempts)
        self._base_delay = float(base_delay_s)
        self._max_delay = float(max_delay_s)
        self._jitter = float(jitter)
        self._rng = rng if rng is not None else random.Random()
        self._msgs: dict[str, dict] = {}
        self._priority: dict[str, str] = {}
        self._order: dict[str, int] = {}
        self._next_attempt: dict[str, float] = {}
        self._attempts: dict[str, int] = {}
        self._acked: OrderedDict[str, None] = OrderedDict()
        self._next_order = 0
        self._bytes = 0
        self._acked_limit = 4096
        self.corrupt_lines = 0
        self._sent_count = 0
        self._dropped_count = 0
        #: Các id đã bị bỏ trong lần `enqueue` gần nhất.
        self.last_evicted: tuple[str, ...] = ()
        self._load()

    # -- API -----------------------------------------------------------
    def enqueue(self, msg: dict, priority: str) -> str | None:
        """Thêm bản tin; trả id bị bỏ nếu hàng đợi đầy, ngược lại `None`.

        `id` được gán vào chính dict `msg` nếu thiếu. Bản tin trùng id với
        bản đã có hoặc đã ack bị coi là trùng và không được thêm.
        """
        if priority not in PRIORITY_RANK:
            allowed = ", ".join(sorted(PRIORITY_RANK))
            raise UplinkError(f"priority khong hop le: {priority!r}; cho phep: {allowed}")
        payload = dict(msg)
        message_id = payload.get("id")
        if message_id is None:
            message_id = self._new_id()
            payload["id"] = message_id
        elif not _is_hex16(message_id):
            raise UplinkError("id ban tin phai la 16 ky tu hex thuong")
        elif message_id in self._msgs or message_id in self._acked:
            return None
        self.last_evicted = ()
        size = self._encoded_size(payload)
        rank = PRIORITY_RANK[priority]
        if size > self._max_bytes:
            self._dropped_count += 1
            self.last_evicted = (str(message_id),)
            return str(message_id)
        # Có thể giải phóng bao nhiêu byte từ các bản tin ưu tiên <= bản mới?
        freeable = sum(
            self._encoded_size(self._msgs[mid])
            for mid in self._msgs
            if PRIORITY_RANK[self._priority[mid]] <= rank
        )
        if self._bytes + size - freeable > self._max_bytes:
            # Dù bỏ hết bản tin cùng/nhỏ hơn ưu tiên vẫn không đủ chỗ: bỏ bản mới.
            self._dropped_count += 1
            self.last_evicted = (str(message_id),)
            return str(message_id)
        evicted: list[str] = []
        while self._bytes + size > self._max_bytes:
            victim = self._lowest_priority()
            if victim is None:
                break
            victim_rank = PRIORITY_RANK[self._priority[victim]]
            if victim_rank > rank:  # pragma: no cover - đã chặn bằng freeable
                break
            self._drop(victim, "queue_full")
            evicted.append(victim)
        if self._bytes + size > self._max_bytes:  # pragma: no cover - phòng thủ
            self._dropped_count += 1
            self.last_evicted = (str(message_id),)
            return str(message_id)
        self._append({"op": "add", "priority": priority, "msg": payload})
        self._msgs[str(message_id)] = payload
        self._priority[str(message_id)] = priority
        self._order[str(message_id)] = self._next_order
        self._next_order += 1
        self._next_attempt[str(message_id)] = 0.0
        self._attempts[str(message_id)] = 0
        self._bytes += size
        self.last_evicted = tuple(evicted)
        return evicted[0] if evicted else None

    def peek(self, now: float) -> dict | None:
        """Bản tin sẵn sàng gửi có ưu tiên cao nhất (cùng hạng: cũ nhất)."""
        best_id: str | None = None
        best_rank = -1
        for message_id in sorted(self._msgs, key=lambda mid: self._order[mid]):
            if self._next_attempt.get(message_id, 0.0) > float(now):
                continue
            rank = PRIORITY_RANK[self._priority[message_id]]
            if rank > best_rank:
                best_rank = rank
                best_id = message_id
        if best_id is None:
            return None
        return dict(self._msgs[best_id])

    def mark_sent(self, message_id: str) -> bool:
        """Xóa bản tin sau khi publish thành công; trả `False` nếu đã biết."""
        if message_id not in self._msgs:
            return False
        self._append({"op": "ack", "id": message_id})
        self._remove(message_id)
        self._remember_ack(message_id)
        self._sent_count += 1
        return True

    def retry_later(self, message_id: str, error: object) -> float | None:
        """Lùi thời điểm thử lại; trả số giây chờ, `None` nếu đã bỏ bản tin."""
        if message_id not in self._msgs:
            return None
        attempt = self._attempts.get(message_id, 0) + 1
        self._attempts[message_id] = attempt
        if attempt >= self._max_attempts:
            self._drop(message_id, "max_attempts")
            return None
        delay = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
        factor = 1.0 + self._rng.uniform(-self._jitter, self._jitter)
        delay = min(max(0.0, delay * factor), self._max_delay)
        next_at = self._clock.now() + delay
        self._next_attempt[message_id] = next_at
        self._append(
            {
                "op": "retry",
                "id": message_id,
                "attempt": attempt,
                "next": next_at,
                "error": str(error)[:200],
            }
        )
        return delay

    def stats(self) -> dict[str, object]:
        by_priority: dict[str, int] = {}
        for priority in self._priority.values():
            by_priority[priority] = by_priority.get(priority, 0) + 1
        nexts = [
            value
            for mid, value in self._next_attempt.items()
            if mid in self._msgs
        ]
        return {
            "queued": len(self._msgs),
            "bytes": self._bytes,
            "max_bytes": self._max_bytes,
            "by_priority": by_priority,
            "next_attempt_at": min(nexts) if nexts else None,
            "acked": self._sent_count,
            "dropped": self._dropped_count,
            "corrupt_lines": self.corrupt_lines,
        }

    def pending_ids(self) -> list[str]:
        """Id các bản tin còn chờ, theo thứ tự chèn (tiện cho test)."""
        return sorted(self._msgs, key=lambda mid: self._order[mid])

    def __len__(self) -> int:
        return len(self._msgs)

    # -- nội bộ --------------------------------------------------------
    def _new_id(self) -> str:
        while True:
            # 16 hex theo spec/mqtt.toml (uuid4().hex là 32, không dùng).
            candidate = uuid.uuid4().hex[:16]
            if candidate not in self._msgs and candidate not in self._acked:
                return candidate

    def _encoded_size(self, msg: dict) -> int:
        return len(self._encode(msg))

    @staticmethod
    def _encode(value: object) -> bytes:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

    def _lowest_priority(self) -> str | None:
        victim: str | None = None
        victim_key: tuple[int, int] | None = None
        for message_id in self._msgs:
            key = (
                PRIORITY_RANK[self._priority[message_id]],
                self._order[message_id],
            )
            if victim_key is None or key < victim_key:
                victim_key = key
                victim = message_id
        return victim

    def _append(self, record: dict) -> None:
        line = self._encode(record)
        try:
            with open(self.path, "ab") as handle:
                handle.write(line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise UplinkError(f"khong ghi duoc hang doi: {exc}") from exc

    def _remove(self, message_id: str) -> None:
        msg = self._msgs.pop(message_id, None)
        if msg is not None:
            self._bytes -= self._encoded_size(msg)
        self._priority.pop(message_id, None)
        self._order.pop(message_id, None)
        self._next_attempt.pop(message_id, None)
        self._attempts.pop(message_id, None)

    def _drop(self, message_id: str, reason: str) -> None:
        if message_id not in self._msgs:
            return
        self._append({"op": "drop", "id": message_id, "reason": reason})
        self._remove(message_id)
        self._dropped_count += 1

    def _remember_ack(self, message_id: str) -> None:
        self._acked[message_id] = None
        self._acked.move_to_end(message_id)
        while len(self._acked) > self._acked_limit:
            self._acked.popitem(last=False)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise UplinkError(f"khong doc duoc hang doi: {exc}") from exc
        for chunk in raw.split(b"\n"):
            if not chunk.strip():
                continue
            try:
                record = json.loads(chunk.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.corrupt_lines += 1
                continue
            if not isinstance(record, dict):
                self.corrupt_lines += 1
                continue
            self._apply_record(record)

    def _apply_record(self, record: dict) -> None:
        op = record.get("op")
        if op == "add":
            msg = record.get("msg")
            priority = record.get("priority")
            if (
                not isinstance(msg, dict)
                or not _is_hex16(msg.get("id"))
                or priority not in PRIORITY_RANK
            ):
                self.corrupt_lines += 1
                return
            message_id = str(msg["id"])
            if message_id in self._msgs:
                return
            if message_id in self._acked:
                return
            self._msgs[message_id] = msg
            self._priority[message_id] = str(priority)
            self._order[message_id] = self._next_order
            self._next_order += 1
            self._next_attempt[message_id] = 0.0
            self._attempts[message_id] = 0
            self._bytes += self._encoded_size(msg)
            return
        message_id = record.get("id")
        if not isinstance(message_id, str):
            self.corrupt_lines += 1
            return
        if op == "ack":
            if message_id in self._msgs:
                self._remove(message_id)
            self._remember_ack(message_id)
            return
        if op == "drop":
            if message_id in self._msgs:
                self._remove(message_id)
                self._dropped_count += 1
            return
        if op == "retry":
            if message_id not in self._msgs:
                return
            try:
                self._attempts[message_id] = int(record.get("attempt", 1))
                self._next_attempt[message_id] = float(record.get("next", 0.0))
            except (TypeError, ValueError):
                self.corrupt_lines += 1
            return
        # op lạ: bỏ qua để tiến hóa lược đồ về sau.
