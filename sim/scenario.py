"""Các kịch bản end-to-end.

Mỗi kịch bản dựng một thiết bị mô phỏng (SimRig), chạy một chuỗi sự kiện và
khẳng định các bất biến. Không có kịch bản nào dùng thời gian thực.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Callable

from .harness import BUILD, ScenarioFailure, SimRig, check
from .ffi import PIN_MODEM_PWR, PIN_MODEM_RI, PIN_SOC_PWR

RI_PIN = PIN_MODEM_RI


def scenario_basic(rig: SimRig) -> str:
    """PIR → ghi → về đúng chế độ → motion vào hàng đợi → live → ngủ."""
    check(rig.controller.state.value == "s0", "phải bắt đầu ở S0 Eco")

    rig.wake_by_pir()
    check(rig.controller.state.value == "s2", "PIR phải đưa hệ thống vào S2")
    check(rig.recorder.recording, "phải đang ghi sau PIR")

    rig.advance(4.0)
    check(not rig.recorder.recording, "clip phải kết thúc sau clip_s")
    check(rig.queue.stats()["queued"] >= 1, "phải có sự kiện motion trong hàng đợi")

    # Hết nghỉ thì về đúng chế độ đã cấu hình, không luôn về Eco.
    rig.advance(2.0)
    check(rig.controller.state.value == "s0", "phải về S0 sau clip (mode eco)")

    pending = rig.queue.peek(rig.clock.now())
    check(pending is not None, "hàng đợi phải còn bản tin để gửi")
    check(pending["type"] == "motion", f"bản tin đầu phải là motion, gặp {pending['type']}")
    message_id = pending["id"]
    check(isinstance(message_id, str) and len(message_id) == 16, "id phải 16 hex")
    rig.queue.mark_sent(message_id)

    # Live: vào S3, hết giờ quay về S2 rồi ngủ.
    rig.controller.request_live(4.0)
    rig.tick()
    check(rig.controller.state.value == "s3", "request_live phải vào S3")
    rig.advance(6.0)
    check(rig.controller.state.value in ("s0", "s1"), "hết live phải về chế độ ngủ")

    clips = rig.recorder.list_clips()
    check(len(clips) >= 2, f"phải có ít nhất 2 clip, có {len(clips)}")
    stats = rig.stats()
    check(stats.get("stop_entries", 0) > 0, "MCU phải vào STOP ít nhất một lần")
    return f"clips={len(clips)} states={','.join(rig.states)}"


def scenario_low_battery(rig: SimRig) -> str:
    """Pin cạn: đóng file, gửi shutdown, MCU cắt rail, vào sinh tồn."""
    # Giữ clip dài hơn 60 s để firmware kịp 6 mẫu cảnh báo (10 s/mẫu).
    rig.controller.config.clip_s = 70.0
    rig.wake_by_pir()
    check(rig.controller.state.value == "s2", "phải đang ghi")
    rig.advance(1.0)

    # 3,04 V: dưới ngưỡng cảnh báo, trên ngưỡng tắt của MCU.
    rig.sim.set_adc_mv(0, 1520)
    rig.advance(65.0)

    check(rig.controller.shutdown_requested, "phải yêu cầu tắt an toàn")
    check(rig.controller.shutdown_done, "phải báo SOC_SHUTDOWN_DONE cho MCU")
    rig.advance(2.0)
    check(rig.sim.get_output(PIN_SOC_PWR) == 0, "MCU phải cắt rail SoC sau khi tắt")
    check(not rig.recorder.recording, "không được còn ghi sau khi tắt")
    types = _pending_types(rig)
    check("fault" in types or "shutdown" in types or "motion" in types,
          f"phải có bản tin sự kiện, gặp {types}")
    return f"types={types} state={rig.controller.state.value}"


def scenario_watch_wake(rig: SimRig) -> str:
    """Watch: modem giữ, RI đánh thức, WAKE_CHAN SMS; tắt kênh thì RI vô hiệu."""
    check(rig.controller.state.value == "s1", "mode watch phải ở S1")
    rig.mcu.set_wake_chan("sms")
    rig.mcu.set_wake_period_s(900)
    rig.clock.advance(4.0)
    check(rig.sim.get_output(PIN_MODEM_PWR) == 1, "Watch phải giữ rail modem")

    # Xung RI: modem báo có SMS. Đọc EVENT ngay, trước khi controller kịp xóa.
    rig.sim.set_input(RI_PIN, 1)
    rig.clock.advance(0.3)
    rig.sim.set_input(RI_PIN, 0)
    clock_events = rig.mcu.events()
    check("WAKE_ALARM" in clock_events, f"RI phải tạo WAKE_ALARM, gặp {sorted(clock_events)}")
    check(rig.sim.get_output(PIN_SOC_PWR) == 1, "RI phải bật rail SoC")
    return "s1 -> RI -> SoC on, WAKE_ALARM ok"


def scenario_watch_ri_off(rig: SimRig) -> str:
    """WAKE_CHAN=off: RI không được đánh thức, không được bật rail."""
    check(rig.controller.state.value == "s1", "mode watch phải ở S1")
    rig.mcu.set_wake_chan("off")
    rig.clock.advance(2.0)
    check(rig.sim.get_output(PIN_SOC_PWR) == 0, "SoC phải đang tắt")
    rig.sim.set_input(RI_PIN, 1)
    rig.clock.advance(0.5)
    rig.sim.set_input(RI_PIN, 0)
    check(rig.sim.get_output(PIN_SOC_PWR) == 0, "RI không được đánh thức khi WAKE_CHAN=off")
    events = rig.mcu.events()
    check("WAKE_ALARM" not in events, f"không được có WAKE_ALARM, gặp {sorted(events)}")
    return "RI ignored when channel off"


def _pending_types(rig: SimRig) -> list[str]:
    msg = rig.queue.peek(rig.clock.now())
    if msg is None:
        return []
    return [str(msg.get("type"))]


def scenario_tickless_day(rig: SimRig) -> str:
    """24 giờ không sự kiện: không có tick 1 ms, chỉ có hẹn giờ lấy mẫu."""
    base = rig.stats()
    advanced = rig.sim.advance_ms(24 * 3600 * 1000)
    stats = rig.stats()
    stops = stats["stop_entries"] - base["stop_entries"]
    stop_ms = stats["stop_ms"] - base["stop_ms"]
    check(advanced >= 24 * 3600 * 1000 - 1000, f"mới trôi {advanced} ms")
    check(stop_ms >= 24 * 3600 * 1000 - 60_000, f"tổng ngủ chỉ {stop_ms} ms")
    # 1 tick 1 ms sẽ là 86,4 triệu lần; hẹn giờ 10 s là 8640 lần.
    check(stops <= 9000, f"thức quá nhiều lần trong 24 giờ: {stops}")
    check(stops >= 100, f"quá ít lần thức, nghi không lấy mẫu pin: {stops}")
    return f"24h: {stops} lần vào STOP, ngủ {stop_ms/1000:.0f}s"


SCENARIOS: dict[str, Callable[[SimRig], str]] = {
    "basic": scenario_basic,
    "low-battery": scenario_low_battery,
    "watch-wake": scenario_watch_wake,
    "watch-ri-off": scenario_watch_ri_off,
    "tickless-day": scenario_tickless_day,
}

RIG_OPTIONS: dict[str, dict] = {
    "basic": {"mode": "eco", "clip_s": 3.0, "live_s": 4.0, "settle_s": 1.0},
    "low-battery": {"mode": "eco", "clip_s": 30.0, "settle_s": 1.0},
    "watch-wake": {"mode": "watch", "clip_s": 3.0, "settle_s": 1.0},
    "watch-ri-off": {"mode": "watch", "clip_s": 3.0, "settle_s": 1.0},
    "tickless-day": {"mode": "eco", "clip_s": 3.0, "settle_s": 1.0},
}


def run(name: str) -> tuple[bool, str]:
    rig = SimRig(BUILD / f"work-{name}", **RIG_OPTIONS.get(name, {}))
    passed = False
    detail = ""
    try:
        detail = SCENARIOS[name](rig)
        passed = True
    except ScenarioFailure as exc:
        detail = f"BẤT BIẾN SAI: {exc}"
    except Exception as exc:  # noqa: BLE001 - báo mọi lỗi của kịch bản
        detail = f"LỖI: {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
    finally:
        try:
            report = rig.write_report(name, passed, detail)
            rig.close()
        except Exception as exc:  # noqa: BLE001 - không che lỗi gốc
            detail += f"\n(không ghi được báo cáo: {exc})"
    return passed, detail


def all_scenarios() -> list[str]:
    return list(SCENARIOS)
