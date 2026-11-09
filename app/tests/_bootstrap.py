"""Đặt `app/` và gốc repo lên `sys.path` cho test.

File này được import theo hai cách:

- ``python app/tests/test_x.py``  -> ``import _bootstrap`` (sys.path có app/tests)
- ``python -m unittest discover -s app/tests -t .`` -> ``from app.tests import _bootstrap``
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

for _path in (APP, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
