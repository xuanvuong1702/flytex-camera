"""Command line interface for tools.measure.

Examples (from the repo root)::

    python -m tools.measure.cli sample --out tools/measure/samples/g0-template.csv
    python -m tools.measure.cli check  --csv tools/measure/samples/g0-template.csv
    python -m tools.measure.cli report --csv tools/measure/samples/g0-example.csv --out report.md

All console output is ASCII.  The generated markdown report is UTF-8 and may
contain Vietnamese; write it with ``--out`` instead of relying on the console
code page.
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

if __package__ in (None, ""):
    # Allow ``python tools/measure/cli.py`` as well as ``python -m ...``.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.measure import csvio, energy, report, schema
else:
    from . import csvio, energy, report, schema


_TEMPLATE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("M-01", "power", "W", "Cong suat tung trang thai S0-S3, co va khong co IR"),
    ("M-02", "current", "mA", "Dong ngu Eco trung binh 24 gio, muc tieu < 1 mA"),
    ("M-03", "current", "mA", "Dong va do tre lenh cua Watch; them dong latency neu can"),
    ("M-30", "bandwidth", "Mbps", "Bang thong tai len 4G, ba nha mang"),
    ("M-31", "latency", "s", "Do tre xem truc tiep qua relay, muc tieu <= 1.5 s"),
    ("M-32", "boolean", "bool", "eDRX/PSM duoc mang chap nhan: 1 = co, 0 = khong"),
)


def build_template_rows() -> list[schema.Measurement]:
    """Empty G0 rows for the IDs used in docs/08-kiem-chung.md."""
    return [
        schema.Measurement(
            id=mid,
            quantity=quantity,
            unit=unit,
            value="",
            pass_fail="NA",
            notes=notes,
        )
        for mid, quantity, unit, notes in _TEMPLATE_ROWS
    ]


def _ascii_fold(text: str) -> str:
    """Fold text to ASCII for safe console output (never for file output)."""
    replacements = {
        "\u0111": "d",
        "\u0110": "D",
        "\u00d7": "x",
        "\u2265": ">=",
        "\u2264": "<=",
        "\u00b1": "+/-",
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return unicodedata.normalize("NFKD", text).encode(
        "ascii", "ignore"
    ).decode("ascii")


def _print_error(message: object) -> None:
    print("LOI: " + _ascii_fold(str(message)))


def _cmd_sample(args: argparse.Namespace) -> int:
    rows = build_template_rows()
    csvio.save(args.out, rows)
    print(
        f"WROTE: {_ascii_fold(str(args.out))} "
        f"({len(rows)} rows, value empty, pass_fail NA)"
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        rows = csvio.load_with_lines(args.csv)
    except (schema.MeasurementError, csv.Error, OSError, UnicodeError) as exc:
        _print_error(exc)
        return 1

    errors = 0
    for line_no, measurement in rows:
        try:
            schema.validate(measurement)
        except schema.MeasurementError as exc:
            errors += 1
            print(
                f"LOI: {_ascii_fold(str(args.csv))}:{line_no} "
                f"{_ascii_fold(str(exc))}"
            )

    if errors:
        print(f"LOI: {errors} dong loi, {len(rows) - errors} dong hop le")
        return 1
    print(f"OK: {len(rows)} dong hop le, 0 loi")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        pairs = csvio.load_with_lines(args.csv)
    except (schema.MeasurementError, csv.Error, OSError, UnicodeError) as exc:
        _print_error(exc)
        return 1

    bad = 0
    measurements: list[schema.Measurement] = []
    for line_no, measurement in pairs:
        try:
            schema.validate(measurement)
        except schema.MeasurementError as exc:
            bad += 1
            print(
                f"LOI: {_ascii_fold(str(args.csv))}:{line_no} "
                f"{_ascii_fold(str(exc))}"
            )
        else:
            measurements.append(measurement)
    if bad:
        print(f"LOI: {bad} dong khong hop le, khong ghi bao cao")
        return 1

    try:
        pack = energy.Pack(
            capacity_ah=args.capacity_ah,
            nominal_v=args.nominal_v,
            usable_fraction=args.usable_fraction,
        )
        scenarios = energy.default_g0_scenarios(args.hours)
        markdown = report.render_markdown(scenarios, measurements, pack)
    except (energy.EnergyError, schema.MeasurementError, TypeError) as exc:
        _print_error(exc)
        return 1

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(markdown)
        print(
            f"WROTE: {_ascii_fold(str(args.out))} "
            f"({len(markdown)} chars, {len(scenarios)} scenarios, "
            f"{len(measurements)} measurements)"
        )
    else:
        # The markdown contains Vietnamese; fold it to ASCII rather than
        # risking a UnicodeEncodeError on a legacy Windows console.
        sys.stdout.write(_ascii_fold(markdown))
        if not markdown.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.measure.cli",
        description="G0 measurements and energy report (stdlib only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser(
        "sample", help="write an empty G0 CSV template for M-01..M-03, M-30..M-32"
    )
    sample.add_argument("--out", required=True, help="output CSV path")
    sample.set_defaults(func=_cmd_sample)

    check = sub.add_parser("check", help="validate a measurement CSV")
    check.add_argument("--csv", required=True, help="input CSV path")
    check.set_defaults(func=_cmd_check)

    rep = sub.add_parser(
        "report", help="read measurements and render the markdown report"
    )
    rep.add_argument("--csv", required=True, help="input measurement CSV path")
    rep.add_argument(
        "--out", help="write UTF-8 markdown here; stdout gets an ASCII version"
    )
    rep.add_argument(
        "--capacity-ah", type=float, default=15.0,
        help="pack capacity in Ah (default 15, docs/16 and D-18)",
    )
    rep.add_argument(
        "--nominal-v", type=float, default=energy.LFP_NOMINAL_V,
        help="pack nominal voltage (default 3.2)",
    )
    rep.add_argument(
        "--usable-fraction", type=float,
        default=energy.DEFAULT_USABLE_FRACTION,
        help="usable fraction (default 0.85)",
    )
    rep.add_argument(
        "--hours", type=float, default=7.0,
        help="scenario duration in hours (default 7)",
    )
    rep.set_defaults(func=_cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (schema.MeasurementError, energy.EnergyError, csv.Error) as exc:
        _print_error(exc)
        return 1
    except (OSError, UnicodeError) as exc:
        _print_error(exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
