"""CSV round-trip and file-format tests for tools.measure.csvio."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure import csvio  # noqa: E402
from tools.measure.schema import (  # noqa: E402
    FIELD_NAMES,
    Measurement,
    MeasurementError,
    validate,
)

SAMPLES = REPO_ROOT / "tools" / "measure" / "samples"
TEMPLATE = SAMPLES / "g0-template.csv"
EXAMPLE = SAMPLES / "g0-example.csv"


class CsvIoTest(unittest.TestCase):
    def test_template_has_six_empty_rows(self) -> None:
        rows = csvio.load_with_lines(TEMPLATE)
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            [row.id for _, row in rows],
            ["M-01", "M-02", "M-03", "M-30", "M-31", "M-32"],
        )
        self.assertEqual([line for line, _ in rows], [2, 3, 4, 5, 6, 7])
        for _, row in rows:
            self.assertEqual(row.value, "")
            self.assertEqual(row.pass_fail, "NA")
            validate(row)

    def test_example_rows_are_valid_and_labelled(self) -> None:
        rows = csvio.load(EXAMPLE)
        self.assertEqual(len(rows), 7)
        for row in rows:
            validate(row)
            self.assertIn("DU LIEU MINH HOA - KHONG PHAI DO", row.notes)
        self.assertEqual(
            [row.pass_fail for row in rows if row.id == "M-31"], ["FAIL"]
        )

    def test_round_trip_preserves_every_field(self) -> None:
        rows = [
            Measurement(
                id="M-01",
                date="2026-11-09",
                board_rev="Rev0",
                condition="bench, 25 C",
                instrument="PPK2",
                quantity="power",
                value="1.4",
                unit="W",
                uncertainty_pct="10",
                pass_fail="PASS",
                notes='note with comma, quote " and newline\nsecond line',
            ),
            Measurement(
                id="M-02",
                quantity="current",
                unit="mA",
                value="",
                pass_fail="NA",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "round-trip.csv"
            csvio.save(path, rows)
            loaded = csvio.load(path)
        self.assertEqual(loaded, rows)

    def test_saved_file_is_utf8_without_bom_and_lf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.csv"
            csvio.save(path, [Measurement(id="M-03", quantity="latency",
                                          unit="s", value="8", pass_fail="PASS")])
            raw = path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", raw)
        self.assertEqual(
            raw.split(b"\n", 1)[0].decode("ascii"), ",".join(FIELD_NAMES)
        )

    def test_header_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("id,value,unit\nM-01,1.4,W\n", encoding="utf-8")
            with self.assertRaises(MeasurementError):
                csvio.load(path)

    def test_wrong_cell_count_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.csv"
            path.write_text(
                ",".join(FIELD_NAMES) + "\nM-01,2026-11-09\n", encoding="utf-8"
            )
            with self.assertRaises(MeasurementError) as ctx:
                csvio.load(path)
        self.assertIn("line 2", str(ctx.exception))

    def test_blank_lines_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.csv"
            path.write_text(
                ",".join(FIELD_NAMES)
                + "\n\n"
                + "M-01,,,,,power,,W,,NA,\n\n",
                encoding="utf-8",
            )
            rows = csvio.load(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, "M-01")

    def test_missing_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MeasurementError):
                csvio.load(Path(tmp) / "nope.csv")

    def test_empty_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(MeasurementError):
                csvio.load(path)

    def test_extra_column_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extra.csv"
            path.write_text(
                ",".join(FIELD_NAMES) + ",extra\n"
                + "M-01,,,,,power,,W,,NA,,x\n",
                encoding="utf-8",
            )
            with self.assertRaises(MeasurementError):
                csvio.load(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
