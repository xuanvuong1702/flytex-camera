"""Test lớp kiểm tra include C."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import check_c_includes


class IncludeCheckTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        self.assertEqual(check_c_includes.offenders(ROOT), [])

    def test_missing_include_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fw = root / "firmware" / "x"
            fw.mkdir(parents=True)
            (fw / "bad.c").write_text("void f(void){ if (0) { (void)NULL; } }\n", encoding="utf-8")
            found = check_c_includes.offenders(root)
            self.assertEqual([path.name for path in found], ["bad.c"])

    def test_with_include_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fw = root / "firmware" / "x"
            fw.mkdir(parents=True)
            (fw / "good.c").write_text(
                "#include <stddef.h>\nvoid f(void){ (void)NULL; }\n", encoding="utf-8"
            )
            self.assertEqual(check_c_includes.offenders(root), [])

    def test_non_firmware_files_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app").mkdir()
            (root / "app" / "x.c").write_text("void f(void){ (void)NULL; }\n", encoding="utf-8")
            self.assertEqual(check_c_includes.offenders(root), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
