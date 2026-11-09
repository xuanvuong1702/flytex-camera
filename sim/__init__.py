"""Mô phỏng end-to-end: firmware C thật (qua FFI) + ứng dụng Linux thật.

Không cần phần cứng. Chạy: python sim/run.py --scenario basic
"""

from __future__ import annotations

__all__ = ["ffi", "clock", "link", "scenario"]
