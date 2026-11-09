"""MQTT và broker trong bộ nhớ.

`Publisher` là interface duy nhất mà tầng service biết. `MemoryBus` +
`MemoryPublisher` dùng cho test và sim, có topic filter `+`/`#`, retained và
ack. `PahoPublisher` là lớp mỏng trên `paho-mqtt`, import bên trong `connect`
để máy dev không cần cài gói; thiếu paho thì báo lỗi rõ, không giả vờ thành
công. TLS thật **CHƯA XÁC MINH** vì chưa có chứng chỉ thiết bị.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Protocol

__all__ = [
    "CloudError",
    "MemoryBus",
    "MemoryPublisher",
    "PahoPublisher",
    "PublishedMessage",
    "Publisher",
    "topic_matches",
]

MessageCallback = Callable[[str, bytes], None]


class CloudError(Exception):
    """Lỗi cloud/MQTT."""


class Publisher(Protocol):
    """Hợp đồng publisher tối thiểu."""

    @property
    def connected(self) -> bool:
        """Đang kết nối tới broker."""

    def connect(self) -> None:
        """Kết nối (có thể ném `CloudError`)."""

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        """Publish một bản tin."""

    def subscribe(self, topic_filter: str, cb: MessageCallback) -> None:
        """Đăng ký nhận bản tin khớp filter."""

    def loop(self, now: float) -> None:
        """Cho phép publisher xử lý I/O mà không chặn."""


@dataclass(frozen=True)
class PublishedMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool


def _split_topic(topic: str) -> list[str]:
    if not isinstance(topic, str) or not topic:
        raise ValueError("topic rong")
    return topic.split("/")


def _validate_filter(topic_filter: str) -> list[str]:
    levels = _split_topic(topic_filter)
    for index, level in enumerate(levels):
        if level == "#":
            if index != len(levels) - 1:
                raise ValueError("'#' chi duoc o cuoi topic filter")
        elif level != "+" and ("+" in level or "#" in level):
            raise ValueError(f"wildcard khong hop le trong level: {level!r}")
    return levels


def topic_matches(topic_filter: str, topic: str) -> bool:
    """Khớp topic theo MQTT: `+` một level, `#` phần còn lại."""
    levels = _validate_filter(topic_filter)
    parts = _split_topic(topic)
    index = 0
    for level in levels:
        if level == "#":
            return True
        if index >= len(parts):
            return False
        if level != "+" and level != parts[index]:
            return False
        index += 1
    return index == len(parts)


class MemoryBus:
    """Broker MQTT trong bộ nhớ: filter, retained, ack, log bản tin."""

    def __init__(self) -> None:
        self._subscriptions: list[tuple[str, MessageCallback]] = []
        self._retained: dict[str, bytes] = {}
        #: Mọi bản tin đã publish, theo thứ tự.
        self.published: list[PublishedMessage] = []
        #: Số bản tin QoS > 0 đã được broker "ack".
        self.ack_count = 0
        self.delivered_count = 0

    # -- broker --------------------------------------------------------
    def publish_message(
        self,
        topic: str,
        payload: bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> int:
        body = bytes(payload)
        _split_topic(topic)
        if qos not in (0, 1, 2):
            raise ValueError("qos phai la 0, 1 hoac 2")
        self.published.append(
            PublishedMessage(topic=topic, payload=body, qos=int(qos), retain=bool(retain))
        )
        if qos > 0:
            self.ack_count += 1
        if retain:
            if body:
                self._retained[topic] = body
            else:
                self._retained.pop(topic, None)
        delivered = 0
        for topic_filter, callback in list(self._subscriptions):
            if topic_matches(topic_filter, topic):
                callback(topic, body)
                delivered += 1
        self.delivered_count += delivered
        return delivered

    def subscribe(
        self,
        topic_filter: str,
        cb: MessageCallback,
        deliver_retained: bool = True,
    ) -> None:
        _validate_filter(topic_filter)
        self._subscriptions.append((topic_filter, cb))
        if deliver_retained:
            for topic, payload in list(self._retained.items()):
                if topic_matches(topic_filter, topic):
                    cb(topic, payload)

    def unsubscribe(self, topic_filter: str, cb: MessageCallback) -> None:
        try:
            self._subscriptions.remove((topic_filter, cb))
        except ValueError:
            pass

    def retained(self, topic: str | None = None) -> dict[str, bytes] | bytes | None:
        if topic is None:
            return dict(self._retained)
        return self._retained.get(topic)

    def publisher(self) -> "MemoryPublisher":
        return MemoryPublisher(self)

    def messages_of(self, topic: str) -> list[bytes]:
        return [msg.payload for msg in self.published if msg.topic == topic]

    def reset_log(self) -> None:
        """Xóa log bản tin (giữ subscription/retained) để test dễ đọc."""
        self.published.clear()
        self.ack_count = 0
        self.delivered_count = 0


class MemoryPublisher:
    """Publisher nối vào `MemoryBus`, dùng cho test và sim."""

    def __init__(self, bus: MemoryBus) -> None:
        self._bus = bus
        self._connected = False
        self.last_loop_at: float | None = None
        self.subscriptions: list[tuple[str, MessageCallback]] = []

    @property
    def bus(self) -> MemoryBus:
        return self._bus

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        if not self._connected:
            raise CloudError("MemoryPublisher chua connect")
        self._bus.publish_message(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic_filter: str, cb: MessageCallback) -> None:
        self._bus.subscribe(topic_filter, cb)
        self.subscriptions.append((topic_filter, cb))

    def loop(self, now: float) -> None:
        self.last_loop_at = float(now)


class PahoPublisher:
    """Publisher paho-mqtt với TLS một chiều/hai chiều.

    **CHƯA XÁC MINH**: chưa chạy với broker thật và chưa có chứng chỉ thiết bị.
    `connect` import `paho.mqtt.client` bên trong; thiếu gói thì
    `CloudError("paho-mqtt chưa cài")`.
    """

    def __init__(
        self,
        host: str,
        port: int,
        ca_path: str,
        cert_path: str,
        key_path: str,
        client_id: str,
        clock: object,
        *,
        keepalive: int = 60,
    ) -> None:
        if not host:
            raise CloudError("thieu mqtt_host")
        if not 0 < int(port) < 65536:
            raise CloudError("mqtt_port ngoai dai")
        self._host = host
        self._port = int(port)
        self._ca_path = str(ca_path)
        self._cert_path = str(cert_path)
        self._key_path = str(key_path)
        self._client_id = client_id
        self._clock = clock
        self._keepalive = int(keepalive)
        self._client: object | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        client = self._client
        if client is None:
            return False
        checker = getattr(client, "is_connected", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:  # pragma: no cover - phụ thuộc paho
                return self._connected
        return self._connected

    def connect(self) -> None:
        for path in (self._ca_path, self._cert_path, self._key_path):
            if not os.path.isfile(path):
                raise CloudError(f"thieu file TLS: {path}")
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
        except ImportError as exc:
            raise CloudError("paho-mqtt chưa cài") from exc
        try:
            client = mqtt.Client(client_id=self._client_id)
            client.tls_set(
                ca_certs=self._ca_path,
                certfile=self._cert_path,
                keyfile=self._key_path,
            )
            client.connect(self._host, self._port, self._keepalive)
        except CloudError:
            raise
        except Exception as exc:
            raise CloudError(f"khong ket noi duoc MQTT: {exc}") from exc
        self._client = client
        self._connected = True

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        if self._client is None or not self.connected:
            raise CloudError("MQTT chua ket noi")
        try:
            info = self._client.publish(  # type: ignore[attr-defined]
                topic, payload, qos=qos, retain=retain
            )
        except Exception as exc:
            raise CloudError(f"publish loi: {exc}") from exc
        code = getattr(info, "rc", 0)
        if code not in (0, None):
            raise CloudError(f"publish bi tu choi, rc={code}")

    def subscribe(self, topic_filter: str, cb: MessageCallback) -> None:
        if self._client is None:
            raise CloudError("MQTT chua ket noi")
        _validate_filter(topic_filter)

        def _on_message(client: object, userdata: object, message: object) -> None:
            topic = getattr(message, "topic")
            payload = bytes(getattr(message, "payload"))
            cb(str(topic), payload)

        try:
            self._client.subscribe(topic_filter, qos=1)  # type: ignore[attr-defined]
            self._client.message_callback_add(  # type: ignore[attr-defined]
                topic_filter, _on_message
            )
        except Exception as exc:
            raise CloudError(f"subscribe loi: {exc}") from exc

    def loop(self, now: float) -> None:
        if self._client is None:
            return
        try:
            self._client.loop(timeout=0)  # type: ignore[attr-defined]
        except Exception as exc:
            raise CloudError(f"MQTT loop loi: {exc}") from exc

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()  # type: ignore[attr-defined]
            except Exception:
                pass
        self._connected = False
        self._client = None
