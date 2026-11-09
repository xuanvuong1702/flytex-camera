"""CLI hình học board.

    python -m hardware.geom.cli            # in bảng
    python -m hardware.geom.cli --write    # ghi SVG + boards.md
    python -m hardware.geom.cli --check    # CI: file phải khớp và hình học hợp lệ
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # chạy trực tiếp
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hardware.geom import draw, model  # type: ignore import-not-found
else:
    from . import draw, model

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = {
    ROOT / "hardware" / "drawings" / "pwr.svg": lambda g: draw.render_svg(
        g.board("pwr"), g
    ),
    ROOT / "hardware" / "drawings" / "cmp.svg": lambda g: draw.render_svg(
        g.board("cmp"), g
    ),
    ROOT / "hardware" / "boards.md": draw.render_markdown,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="ghi file sinh")
    parser.add_argument("--check", action="store_true", help="kiểm tra khớp file")
    args = parser.parse_args(argv)

    try:
        geometry = model.check()
    except model.GeometryError as exc:
        print(f"LOI HINH HOC: {exc}", file=sys.stderr)
        return 1
    if args.check:
        stale = []
        for path, render in OUTPUTS.items():
            content = render(geometry)
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != content:
                stale.append(path.relative_to(ROOT))
        if stale:
            print("File hinh hoc lech spec, chay --write:", file=sys.stderr)
            for path in stale:
                print(f"  - {path}", file=sys.stderr)
            return 1
        print(
            f"OK: hinh hoc hop le, {len(OUTPUTS)} file khop; "
            f"{len(geometry.boards)} board"
        )
        return 0
    if args.write:
        for path, render in OUTPUTS.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(geometry), encoding="utf-8", newline="\n")
            print(f"ghi {path.relative_to(ROOT)}")
        return 0
    for board in geometry.boards:
        print(
            f"{board.name}: {board.width:.0f}x{board.height:.0f} mm, "
            f"{len(board.holes)} lo, {len(board.connectors)} connector"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
