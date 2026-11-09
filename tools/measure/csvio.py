"""CSV input/output for G0 measurement rows.

The file format is exactly the column order of
:data:`tools.measure.schema.FIELD_NAMES`, UTF-8, comma separated.  Rows are
written with LF line endings so the files stay clean in git on Windows.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from .schema import FIELD_NAMES, Measurement, MeasurementError


def _normalise_header(row: list[str]) -> list[str]:
    return [cell.strip().lstrip("\ufeff") for cell in row]


def load_with_lines(path: str | Path) -> list[tuple[int, Measurement]]:
    """Load rows and keep the CSV line number for each row.

    Structural problems (wrong header, wrong number of cells) raise
    :class:`MeasurementError` with the line number in the message.  Semantic
    validation is left to :func:`tools.measure.schema.validate` so the
    ``check`` command can count all bad rows instead of stopping at the first.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise MeasurementError(f"CSV file does not exist: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise MeasurementError(f"CSV file is empty: {csv_path}") from exc

        header = _normalise_header(header)
        if tuple(header) != FIELD_NAMES:
            expected = ",".join(FIELD_NAMES)
            found = ",".join(header) if header else "<empty>"
            raise MeasurementError(
                f"CSV header mismatch; expected '{expected}', got '{found}'"
            )

        rows: list[tuple[int, Measurement]] = []
        for cells in reader:
            line_no = reader.line_num
            if not any(cell.strip() for cell in cells):
                # Blank separator line, harmless.
                continue
            if len(cells) != len(FIELD_NAMES):
                raise MeasurementError(
                    f"CSV line {line_no}: expected {len(FIELD_NAMES)} cells, "
                    f"got {len(cells)}"
                )
            data = dict(zip(FIELD_NAMES, cells, strict=True))
            rows.append((line_no, Measurement(**data)))
    return rows


def load(path: str | Path) -> list[Measurement]:
    """Load measurement rows from ``path`` (structure checked, values not)."""
    return [row for _, row in load_with_lines(path)]


def save(path: str | Path, rows: list[Measurement]) -> None:
    """Write measurement rows as UTF-8 CSV with LF line endings."""
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(FIELD_NAMES),
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
