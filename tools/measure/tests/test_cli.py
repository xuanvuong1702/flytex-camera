"""End-to-end tests for tools.measure.cli using temporary files."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure import cli, csvio
from tools.measure.schema import Measurement

TEMPLATE = REPO_ROOT / "tools" / "measure" / "samples" / "g0-template.csv"
EXAMPLE = REPO_ROOT / "tools" / "measure" / "samples" / "g0-example.csv"


def run_cli(*argv: str) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class SampleCommandTest(unittest.TestCase):
    def test_sample_writes_six_empty_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.csv"
            code, out, _ = run_cli("sample", "--out", str(path))
            self.assertEqual(code, 0)
            self.assertTrue(out.isascii())
            rows = csvio.load(path)
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row.value == "" for row in rows))
            self.assertTrue(all(row.pass_fail == "NA" for row in rows))
            self.assertEqual(
                [row.id for row in rows],
                ["M-01", "M-02", "M-03", "M-30", "M-31", "M-32"],
            )

    def test_sample_then_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.csv"
            self.assertEqual(run_cli("sample", "--out", str(path))[0], 0)
            code, out, _ = run_cli("check", "--csv", str(path))
            self.assertEqual(code, 0)
            self.assertIn("OK: 6 dong hop le, 0 loi", out)
            self.assertTrue(out.isascii())


class CheckCommandTest(unittest.TestCase):
    def test_check_finds_bad_row_and_keeps_counting(self) -> None:
        rows = [
            Measurement(id="M-01", quantity="power", unit="W",
                        value="1.4", pass_fail="PASS"),
            Measurement(id="M-02", quantity="power", unit="mA",
                        value="0.4", pass_fail="PASS"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.csv"
            csvio.save(path, rows)
            code, out, _ = run_cli("check", "--csv", str(path))
        self.assertEqual(code, 1)
        self.assertIn("LOI:", out)
        self.assertIn("1 dong loi, 1 dong hop le", out)
        self.assertTrue(out.isascii())

    def test_check_bad_header_fails_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-header.csv"
            path.write_text("id,value\nM-01,1.4\n", encoding="utf-8")
            code, out, _ = run_cli("check", "--csv", str(path))
        self.assertEqual(code, 1)
        self.assertIn("LOI:", out)
        self.assertTrue(out.isascii())

    def test_check_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_cli(
                "check", "--csv", str(Path(tmp) / "nope.csv")
            )
        self.assertEqual(code, 1)
        self.assertIn("LOI:", out)

    def test_check_repo_sample_example(self) -> None:
        code, out, _ = run_cli("check", "--csv", str(EXAMPLE))
        self.assertEqual(code, 0)
        self.assertIn("OK: 7 dong hop le", out)


class ReportCommandTest(unittest.TestCase):
    def test_report_writes_utf8_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report.md"
            code, out, _ = run_cli(
                "report", "--csv", str(TEMPLATE), "--out", str(out_path)
            )
            text = out_path.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("Số liệu có nhãn CHƯA ĐO", text)
        self.assertIn("Không có phép đo thật: chưa được qua G0", text)
        self.assertIn("WROTE:", out)
        self.assertTrue(out.isascii())

    def test_report_without_out_is_ascii_on_stdout(self) -> None:
        code, out, _ = run_cli(
            "report", "--csv", str(EXAMPLE), "--capacity-ah", "10"
        )
        self.assertEqual(code, 0)
        self.assertTrue(out.isascii())
        self.assertIn("CANH BAO", out)
        self.assertIn("KHONG DAT", out)

    def test_report_default_pack_is_15_ah(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "default.md"
            code, _, _ = run_cli(
                "report", "--csv", str(TEMPLATE), "--out", str(out_path)
            )
            text = out_path.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("40.8 Wh", text)
        self.assertIn("Tham chiếu pack 10 Ah", text)
        self.assertIn("12.7 Ah", text)

    def test_report_fails_on_invalid_csv(self) -> None:
        rows = [
            Measurement(id="M-02", quantity="power", unit="mA",
                        value="0.4", pass_fail="PASS"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bad.csv"
            out_path = Path(tmp) / "report.md"
            csvio.save(csv_path, rows)
            code, out, _ = run_cli(
                "report", "--csv", str(csv_path), "--out", str(out_path)
            )
            self.assertFalse(out_path.exists())
        self.assertEqual(code, 1)
        self.assertIn("LOI:", out)
        self.assertTrue(out.isascii())

    def test_report_15_ah_pack_passes_night(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report-15ah.md"
            code, _, _ = run_cli(
                "report",
                "--csv",
                str(TEMPLATE),
                "--out",
                str(out_path),
                "--capacity-ah",
                "15",
            )
            text = out_path.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("40.8 Wh", text)
        self.assertIn("Mọi kịch bản đều đạt", text)
        self.assertIn("Tham chiếu pack 10 Ah", text)
        self.assertIn("12.7 Ah", text)


class SubprocessTest(unittest.TestCase):
    def test_python_dash_m_entry_point(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.measure.cli",
                "check",
                "--csv",
                str(TEMPLATE),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: 6 dong hop le", result.stdout)
        self.assertTrue(result.stdout.isascii())

    def test_direct_script_entry_point(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "measure" / "cli.py"),
                "check",
                "--csv",
                str(TEMPLATE),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: 6 dong hop le", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
