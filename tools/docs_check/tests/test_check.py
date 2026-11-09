"""Fixture-repo tests for tools.docs_check.check.

Every fixture lives in a temporary directory; the checker is always called
with ``--root <temp dir>`` so it never scans the real repository.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.docs_check import check

CHECK_SCRIPT = REPO_ROOT / "tools" / "docs_check" / "check.py"


def make_id(prefix: str, number: int) -> str:
    """Build an ID at runtime so test sources never carry invalid literals."""
    return f"{prefix}-{number:02d}"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def append_toc(root: Path, rel_path: str, title: str = "fixture") -> None:
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    text += f"| [{title}]({rel_path}) | fixture |\n"
    readme.write_text(text, encoding="utf-8", newline="\n")


def add_doc(root: Path, name: str, content: str, toc: bool = True) -> Path:
    path = root / "docs" / name
    write(path, content)
    if toc:
        append_toc(root, f"docs/{name}", name)
    return path


def build_clean(root: Path) -> None:
    write(
        root / "README.md",
        "# Fixture\n"
        "\n"
        "## Mục lục\n"
        "\n"
        "| File | Nội dung |\n"
        "|---|---|\n"
        "| [00](docs/00.md) | yeu cau |\n"
        "| [08](docs/08-kiem-chung.md) | kiem chung |\n"
        "| [10](docs/10-rui-ro.md) | rui ro |\n"
        "| [11](docs/11-nhat-ky-quyet-dinh.md) | quyet dinh |\n",
    )
    write(
        root / "docs" / "00.md",
        "# 00\n"
        "\n"
        "Xem M-01, R-01, O-01, D-01. Link [08](08-kiem-chung.md).\n",
    )
    write(
        root / "docs" / "08-kiem-chung.md",
        "# 08\n"
        "\n"
        "| ID | Noi dung |\n"
        "|---|---|\n"
        "| M-01 | mot |\n"
        "| M-02 | hai |\n",
    )
    write(
        root / "docs" / "10-rui-ro.md",
        "# 10\n"
        "\n"
        "| ID | Rui ro |\n"
        "|---|---|\n"
        "| R-01 | mot |\n",
    )
    write(
        root / "docs" / "11-nhat-ky-quyet-dinh.md",
        "# 11\n"
        "\n"
        "## 1\n"
        "\n"
        "| ID | Quyet dinh |\n"
        "|---|---|\n"
        "| D-01 | mot |\n"
        "\n"
        "## 3\n"
        "\n"
        "| ID | Cau hoi |\n"
        "|---|---|\n"
        "| O-01 | mot |\n",
    )
    write(
        root / "spec" / "generated" / "regmap.md",
        "# Regmap (sinh tự động)\n",
    )


def run_check(root: Path, *extra: str) -> tuple[int, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = check.main(["--root", str(root), *extra])
    return code, out.getvalue()


class CleanRepoTest(unittest.TestCase):
    def test_clean_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            code, out = run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("OK:", out)
        self.assertIn("khong co loi", out)
        self.assertTrue(out.isascii())

    def test_json_output_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            code, out = run_check(root, "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["errors"], [])
        self.assertGreaterEqual(payload["stats"]["tables"], 5)


class TocTest(unittest.TestCase):
    def test_missing_toc_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            (root / "docs" / "00.md").unlink()
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("muc luc tro toi file khong ton tai: docs/00.md", out)

    def test_docs_file_not_in_toc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(root, "extra.md", "# Extra\n", toc=False)
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("thieu file trong muc luc: docs/extra.md", out)

    def test_doc_marked_ignore_is_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "extra.md",
                "# Extra\n\n<!-- docs-check: ignore -->\n",
                toc=False,
            )
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_generated_doc_is_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(root, "extra.md", "# Extra (sinh tự động)\n", toc=False)
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_missing_non_md_toc_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            append_toc(root, "docs/nope.txt", "nope")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("muc luc tro toi file khong ton tai: docs/nope.txt", out)

    def test_missing_readme_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            (root / "README.md").unlink()
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("thieu README.md", out)


class IdReferenceTest(unittest.TestCase):
    def test_unknown_m_id(self) -> None:
        unknown = make_id("M", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write(f"\nXem {unknown}.\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn(f"ma {unknown} khong co trong docs/08-kiem-chung.md", out)

    def test_unknown_r_id(self) -> None:
        unknown = make_id("R", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write(f"\nXem {unknown}.\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn(f"ma {unknown}", out)

    def test_unknown_o_id(self) -> None:
        unknown = make_id("O", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write(f"\nXem {unknown}.\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn(f"ma {unknown}", out)

    def test_unknown_d_id(self) -> None:
        unknown = make_id("D", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write(f"\nXem {unknown}.\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn(f"ma {unknown}", out)

    def test_all_known_prefixes_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write("\nM-02 R-01 O-01 D-01.\n")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_missing_registry_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            (root / "docs" / "10-rui-ro.md").unlink()
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("thieu file so lieu ID: docs/10-rui-ro.md", out)

    def test_excluded_directories_are_not_scanned(self) -> None:
        unknown = make_id("M", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            for dirname in (".git", "build", "__pycache__"):
                write(root / dirname / "bad.md", f"# Bad\n\n{unknown}\n")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)


class LinkTest(unittest.TestCase):
    def test_dead_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write("\n[missing](missing.md)\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("link chet: missing.md", out)

    def test_link_with_anchor_to_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(root, "02.md", "# 02\n\nNoi dung.\n")
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write("\n[ok](02.md#phan-2)\n")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_external_links_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write("\n[web](https://example.com/x.md)\n")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_link_inside_fence_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "03.md",
                "# 03\n\n```\n[dead](nowhere.md)\n```\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 0, out)


class TableTest(unittest.TestCase):
    def test_row_with_wrong_cell_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "tables.md",
                "# Tables\n"
                "\n"
                "| A | B | C |\n"
                "|---|---|---|\n"
                "| 1 | 2 |\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("tables.md:5 dong co 2 o, tieu de co 3 o", out)

    def test_separator_with_wrong_cell_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "tables.md",
                "# Tables\n"
                "\n"
                "| A | B | C |\n"
                "|---|---|\n"
                "| 1 | 2 | 3 |\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("dong phan cach co 2 o, tieu de co 3 o", out)

    def test_table_without_leading_pipes_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "plain.md",
                "# Plain\n"
                "\n"
                "A | B | C\n"
                "---|---|---\n"
                "1 | 2\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("plain.md:5 dong co 2 o, tieu de co 3 o", out)

    def test_table_inside_fence_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            add_doc(
                root,
                "fence.md",
                "# Fence\n"
                "\n"
                "```text\n"
                "| A | B |\n"
                "|---|---|\n"
                "| 1 |\n"
                "```\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 0, out)


class GeneratedFileTest(unittest.TestCase):
    def test_missing_marker_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            write(root / "spec" / "generated" / "hand.md", "# Hand written\n")
            code, out = run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("file sinh thieu nhan", out)
        self.assertIn("spec/generated/hand.md", out)

    def test_marker_on_second_line_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            write(
                root / "spec" / "generated" / "ok.md",
                "\n# AUTOGENERATED from spec\n",
            )
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_hidden_placeholder_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            write(root / "spec" / "generated" / ".gitkeep", "")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_json_and_csv_are_exempt_from_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            write(root / "spec" / "generated" / "schema.json", "{}\n")
            write(root / "spec" / "generated" / "pinout.csv", "a,b\n1,2\n")
            code, out = run_check(root)
        self.assertEqual(code, 0, out)


class CliTest(unittest.TestCase):
    def test_json_error_payload_is_ascii(self) -> None:
        unknown = make_id("M", 77)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            with (root / "docs" / "00.md").open("a", encoding="utf-8") as fh:
                fh.write(f"\n{unknown}\n")
            code, out = run_check(root, "--json")
        self.assertEqual(code, 1)
        self.assertTrue(out.isascii())
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        rules = {error["rule"] for error in payload["errors"]}
        self.assertIn("id-ref", rules)
        self.assertTrue(any(unknown in error["message"]
                            for error in payload["errors"]))

    def test_missing_root_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_check(Path(tmp) / "nope")
        self.assertEqual(code, 2)
        self.assertIn("LOI:", out)

    def test_script_entry_point_on_clean_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_clean(root)
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK:", result.stdout)
        self.assertTrue(result.stdout.isascii())


if __name__ == "__main__":
    unittest.main(verbosity=2)
