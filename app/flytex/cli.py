"""CLI của ứng dụng thiết bị.

Chạy từ thư mục `app` (để import được gói `flytex`):

    python -m flytex.cli selftest
    python -m flytex.cli run --config /data/config.json
    python -m flytex.cli sim --seconds 60

Mọi thứ in ra stdout đều là ASCII để console Windows không lỗi encoding.
`run` cần phần cứng thật; thiếu thì báo lỗi rõ và trả mã khác 0.
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
import tempfile
from pathlib import Path

from . import APP_VERSION
from .clock import FakeClock
from .cloud import MemoryBus
from .commands import CommandRouter
from .config import Config, ConfigError
from .diagnostics import Diagnostics
from .identity import Identity, IdentityError
from .mcu import I2cLink, McuClient, McuError, MemoryMcu, ProtocolMismatch
from .media import FakeSource, RkMpiSource
from .modem import AtClient, FakeModem
from .recorder import SegmentRecorder
from .service import DeviceService
from .tsmux import TsMuxer
from .uplink import UplinkQueue
from .upload import FakeUploader, UploadSpool


def _ascii(text: object) -> str:
    return str(text).encode("ascii", errors="replace").decode("ascii")


def _out(text: str = "") -> None:
    print(_ascii(text))


def _err(text: str) -> None:
    print(_ascii(text), file=sys.stderr)


def _check(name: str, action) -> bool:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - selftest phải báo mọi lỗi
        _out(f"FAIL {name}: {type(exc).__name__}: {_ascii(exc)}")
        return False
    _out(f"OK   {name}")
    return True


def _selftest() -> int:
    """Kiểm tra nội bộ: import, spec, cấu hình mẫu, vòng đời cơ bản."""
    from . import mqtt_gen, regs_gen

    checks = 0
    passed = 0

    def run(name: str, action) -> None:
        nonlocal checks, passed
        checks += 1
        if _check(name, action):
            passed += 1

    def check_regmap() -> None:
        if regs_gen.PROTO_VER >> 4 != regs_gen.PROTO_MAJOR:
            raise AssertionError("PROTO_VER khong khop PROTO_MAJOR")
        seen: set[int] = set()
        for reg in regs_gen.REGISTERS:
            for addr in range(reg.addr, reg.addr + reg.size):
                if addr in seen:
                    raise AssertionError(f"dia chi trung: 0x{addr:02X}")
                seen.add(addr)
        if len(seen) != regs_gen.REG_COUNT:
            raise AssertionError("so byte regmap khong khop REG_COUNT")
        if regs_gen.REG_BY_NAME["FW_VER"].reset != regs_gen.REG_BY_NAME["FW_VER"].reset:
            raise AssertionError("khong doc duoc FW_VER reset")

    def check_mqtt() -> None:
        if mqtt_gen.VERSION != 1:
            raise AssertionError("phien ban MQTT khac 1")
        if not mqtt_gen.EVENT_TYPES:
            raise AssertionError("khong co event type")
        for name, rule in mqtt_gen.COMMANDS.items():
            for param, spec in rule.items():
                if spec["type"] not in ("int", "string", "array"):
                    raise AssertionError(f"{name}.{param} kieu la: {spec['type']}")
        if "NOT_IMPLEMENTED" not in mqtt_gen.ACK_ERRORS:
            raise AssertionError("thieu ma ack NOT_IMPLEMENTED")

    def check_config() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config()
            config.save(path)
            loaded = Config.load(path)
            if loaded != config:
                raise AssertionError("config roundtrip khong khop")
            config.set_allowed("mode", "watch")
            if config.mode != "watch":
                raise AssertionError("set_allowed khong doi mode")

    def check_mcu() -> None:
        clock = FakeClock()
        memory = MemoryMcu(clock)
        mcu = McuClient(memory)
        mcu.check_protocol()
        if mcu.proto_version != "1.1":
            raise AssertionError("proto_version sai")
        if mcu.mode() != "eco":
            raise AssertionError("mode reset sai")
        memory.raise_event({"PIR"})
        if mcu.events() != {"PIR"}:
            raise AssertionError("event khong doc duoc")

    def check_recorder() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            recorder = SegmentRecorder(Path(tmp) / "clips", clock, TsMuxer())
            recorder.start("0123456789abcdef")
            recorder.write(0.0, b"frame")
            clock.advance(0.1)
            info = recorder.stop()
            if info.size_b <= 0 or len(recorder.list_clips()) != 1:
                raise AssertionError("ghi clip khong tao chi muc")

    def check_queue() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            queue = UplinkQueue(Path(tmp) / "queue.jsonl", clock, max_bytes=1 << 20)
            queue.enqueue({"type": "status"}, "status")
            message = queue.peek(clock.now())
            if message is None or len(str(message.get("id"))) != 16:
                raise AssertionError("id ban tin khong phai 16 hex")

    def check_identity() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            identity = Identity.generate_for_test(Path(tmp) / "identity")
            loaded = Identity.load(identity.root)
            if loaded.device_id != identity.device_id:
                raise AssertionError("device_id khong khop")

    run("import cac module", lambda: None)
    run("regmap sinh tu spec", check_regmap)
    run("mqtt sinh tu spec", check_mqtt)
    run("config mau roundtrip", check_config)
    run("mcu memory protocol/event", check_mcu)
    run("recorder ghi clip", check_recorder)
    run("uplink id 16 hex", check_queue)
    run("identity test fixture", check_identity)
    _out(f"selftest: {passed}/{checks} OK, version={APP_VERSION}")
    return 0 if passed == checks else 1


def _run(config_path: str, data_root: str) -> int:
    """Khởi động ứng dụng thật; cần Linux, I2C và SDK RK MPI."""
    try:
        config = Config.load(config_path)
        identity = Identity.load(Path(data_root) / "identity")
    except (ConfigError, IdentityError) as exc:
        _err(f"error: {exc}")
        return 2
    _out(
        "flytex-device: config ok, device="
        f"{identity.device_id} mode={config.mode}"
    )
    try:
        link = I2cLink()
        mcu = McuClient(link)
        mcu.check_protocol()
    except ProtocolMismatch as exc:
        _err(f"error: MCU protocol mismatch: {exc}")
        return 3
    except McuError as exc:
        _err(f"error: khong mo duoc MCU: {exc}")
        return 3
    _out(f"flytex-device: MCU proto={mcu.proto_version} fw={mcu.fw_version}")
    try:
        media = RkMpiSource()
        media.start()
    except NotImplementedError as exc:
        _err(f"error: {exc}")
        _err("error: run can SDK RK MPI; xem docs/14 muc 4.3 (CHUA XAC MINH)")
        mcu.close()
        return 4
    # Không thể tới đây khi chưa có SDK; nhánh dưới giữ chỗ cho chỗ nối dây.
    _err("error: modem UART transport chua hien thuc (xem bao cao)")
    mcu.close()
    return 5


def _sim(seconds: int) -> int:
    """Chạy sim không cần phần cứng: MemoryMcu + FakeModem + MemoryBus."""
    if seconds < 1:
        _err("error: --seconds phai >= 1")
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="flytex-sim-") as tmp_name:
            tmp = Path(tmp_name)
            clock = FakeClock(start=1_760_000_000.0)
            mcu_memory = MemoryMcu(clock)
            mcu_memory.set_status("SOC_POWER_ON", True)
            mcu_memory.set_battery_mv(3900)
            mcu_memory.set_temps(24, 22)
            mcu = McuClient(mcu_memory)

            fake_modem = FakeModem(clock, powered=False)
            urcs: list[str] = []
            modem = AtClient(fake_modem, clock, on_urc=urcs.append, pwrkey=fake_modem)
            modem.power_on(timeout=5.0)
            modem.sim_status()
            modem.registration()
            modem.signal_dbm()

            identity = Identity.generate_for_test(tmp / "identity")
            config = Config(
                mode="eco",
                clip_s=5,
                live_s=10,
                settle_s=2,
                apn="internet",
                mqtt_host="memory",
                mqtt_port=1883,
                relay_url="http://relay.invalid/live",
                wake_chan="off",
            )
            config_path = tmp / "config.json"
            config.save(config_path)

            bus = MemoryBus()
            publisher = bus.publisher()
            recorder = SegmentRecorder(
                tmp / "clips",
                clock,
                TsMuxer(),
                segment_s=3.0,
                max_bytes=1 << 20,
                pin_budget_bytes=1 << 19,
            )
            queue = UplinkQueue(
                tmp / "queue.jsonl",
                clock,
                max_bytes=1 << 20,
                rng=random.Random(7),  # nosec B311 - RNG mo phong
            )
            media = FakeSource(clock, fps=5.0)
            diagnostics = Diagnostics(tmp / "diag", clock)
            router = CommandRouter(
                {},
                dev=identity.device_id,
                clock=clock,
                log=diagnostics.log,
            )
            uploader = FakeUploader()
            spool = UploadSpool(tmp / "upload.jsonl", clock)
            service = DeviceService(
                identity,
                config,
                clock,
                mcu,
                modem,
                media,
                recorder,
                queue,
                publisher,
                router,
                diagnostics,
                config_path=config_path,
                uploader=uploader,
                spool=spool,
            )
            service.boot()

            command_topic = f"dev/{identity.device_id}/cmd"
            def send_command(cmd_type: str, **params: object) -> None:
                payload = {
                    "v": 1,
                    "id": secrets.token_hex(8),
                    "dev": identity.device_id,
                    "ts": int(clock.now()),
                    "type": cmd_type,
                }
                payload.update(params)
                bus.publish_message(
                    command_topic,
                    json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                )

            simulated = 0
            always_sleep = False
            for second in range(seconds):
                if second == 1:
                    mcu_memory.raise_event({"PIR"})
                elif second == 2:
                    send_command("status.get")
                elif second == 3:
                    send_command("live.start", duration_s=10)
                elif second == 14:
                    # Đang trong S2 sau live: mode.set phải bị từ chối BUSY.
                    send_command("mode.set", mode="watch")
                service.step(clock.now())
                simulated += 1
                if service.sleep_requested:
                    always_sleep = True
                    break
                clock.sleep(1.0)

            types: dict[str, int] = {}
            for published in bus.published:
                try:
                    body = json.loads(published.payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(body, dict):
                    name = str(body.get("type", "?"))
                    types[name] = types.get(name, 0) + 1
            state = service.power.state.value
            mode = service.power.mode
            clips = len(recorder.list_clips())
            stats = queue.stats()
            service.stop()
            _out(
                "sim: "
                f"seconds={simulated} state={state} mode={mode} "
                f"clips={clips} queued={stats['queued']} "
                f"published={len(bus.published)} sleep_cmd={int(always_sleep)} "
                f"uploaded={len(uploader.calls)}"
            )
            _out(
                "sim: types="
                + ",".join(f"{key}={value}" for key, value in sorted(types.items()))
            )
            _out(
                "sim: mcu_commands="
                + ",".join(mcu_memory.commands)
                + f" urcs={len(urcs)}"
            )
            return 0
    except Exception as exc:  # noqa: BLE001 - CLI báo lỗi, không traceback dài
        _err(f"sim error: {type(exc).__name__}: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flytex.cli",
        description="Flytex camera device application (ASCII output)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("selftest", help="run internal consistency checks")

    run_parser = sub.add_parser("run", help="run on real hardware (Linux)")
    run_parser.add_argument("--config", required=True, help="path to config.json")
    run_parser.add_argument(
        "--data-root", default="/data", help="data partition root (default /data)"
    )

    sim_parser = sub.add_parser("sim", help="run without hardware")
    sim_parser.add_argument(
        "--seconds", type=int, default=60, help="simulated seconds (default 60)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    if args.command == "run":
        return _run(args.config, args.data_root)
    if args.command == "sim":
        return _sim(args.seconds)
    _err("error: unknown command")  # pragma: no cover - argparse chặn trước
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
