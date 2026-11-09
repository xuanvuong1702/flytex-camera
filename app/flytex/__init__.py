"""Ứng dụng Linux trên SoC cho camera 4G Flytex.

Gói này chứa các module nghiệp vụ (nguồn, MCU, modem, ghi hình, uplink,
cloud, lệnh) và CLI. Mọi phụ thuộc phần cứng đều đi qua interface tiêm được
để chạy được trên máy phát triển không có phần cứng.

Hai file `regs_gen.py` và `mqtt_gen.py` được sinh từ `spec/`; không sửa tay.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Phiên bản phần mềm gửi trong bản tin MQTT (`boot.sw`, `status.fw`).
APP_VERSION = __version__

__all__ = ["APP_VERSION", "__version__"]
