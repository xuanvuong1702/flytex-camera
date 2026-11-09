"""Test gói devkit trước khi mua."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devkit.scripts import devkit_check, feature_test  # noqa: E402


class DevkitTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in (
            "README.md", "bom.csv", "wiring.md", "flash.md",
            "troubleshooting.md", "config/devkit.json",
            "systemd/flytex-device.service",
            "scripts/devkit_check.py", "scripts/feature_test.py",
            "scripts/provision.sh",
        ):
            self.assertTrue((ROOT / "devkit" / name).exists(), name)

    def test_bom_has_required_items(self) -> None:
        with (ROOT / "devkit" / "bom.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        items = {row["item"] for row in rows}
        for required in ("SBC", "Camera", "Modem", "PSU", "USB-TTL"):
            self.assertIn(required, items)

    def test_config_is_valid(self) -> None:
        sys.path.insert(0, str(ROOT / "app"))
        from flytex.config import Config

        data = json.loads((ROOT / "devkit" / "config" / "devkit.json").read_text(encoding="utf-8"))
        config = Config.from_dict(data)
        self.assertEqual(config.mode, "eco")
        self.assertGreater(config.clip_s, 0)

    def test_check_dry_run(self) -> None:
        self.assertEqual(devkit_check.main(["--dry-run"]), 0)

    def test_feature_dry_run(self) -> None:
        self.assertEqual(feature_test.main(["--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
