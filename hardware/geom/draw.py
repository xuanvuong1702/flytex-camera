"""Sinh bản vẽ SVG và bảng hình học từ mô hình board."""

from __future__ import annotations

from .model import Board, Geometry

SCALE = 6.0  # px/mm
MARGIN = 12.0  # mm quanh board


def _xy(x_mm: float, y_mm: float, height: float) -> tuple[float, float]:
    """Đổi toạ độ board (gốc dưới-trái) sang SVG (gốc trên-trái)."""
    return ((x_mm + MARGIN) * SCALE, (height - y_mm + MARGIN) * SCALE)


def render_svg(board: Board, geometry: Geometry) -> str:
    width_px = (board.width + 2 * MARGIN) * SCALE
    height_px = (board.height + 2 * MARGIN) * SCALE
    x0 = MARGIN * SCALE
    y0 = MARGIN * SCALE
    w = board.width * SCALE
    h = board.height * SCALE
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_px:.0f}" height="{height_px:.0f}" '
        f'viewBox="0 0 {width_px:.0f} {height_px:.0f}">',
        '<rect width="100%" height="100%" fill="#fafafa"/>',
        f'<text x="{x0:.0f}" y="{(MARGIN / 2) * SCALE:.0f}" '
        f'font-family="sans-serif" font-size="14">'
        f'{board.name} — {board.width:.0f}×{board.height:.0f} mm — '
        f'top view, mm, origin bottom-left</text>',
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="#e8f0e8" stroke="#204020" stroke-width="1.5"/>',
    ]
    for index, hole in enumerate(board.holes):
        cx, cy = _xy(hole.x, hole.y, board.height)
        r = geometry.hole_diameter / 2.0 * SCALE
        out.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="none" stroke="#803030" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{cx + r + 2:.0f}" y="{cy + 2:.0f}" '
            f'font-family="sans-serif" font-size="8" fill="#803030">'
            f'H{index + 1}</text>'
        )
    for connector in board.connectors:
        cx, cy = _xy(connector.x, connector.y, board.height)
        colour = "#a04000" if connector.name == "J_B2B" else "#204080"
        out.append(
            f'<rect x="{cx - 6:.1f}" y="{cy - 4:.1f}" width="12" height="8" '
            f'fill="{colour}" opacity="0.85"/>'
        )
        anchor = "start" if connector.x < board.width * 0.7 else "end"
        dx = 8 if anchor == "start" else -8
        out.append(
            f'<text x="{cx + dx:.0f}" y="{cy - 6:.0f}" text-anchor="{anchor}" '
            f'font-family="sans-serif" font-size="8" fill="{colour}">'
            f'{connector.name}</text>'
        )
    legend_y = height_px - 6
    out.append(
        f'<text x="{x0:.0f}" y="{legend_y:.0f}" font-family="sans-serif" '
        f'font-size="9" fill="#404040">'
        f'{len(board.holes)} lỗ M3, {len(board.connectors)} connector; '
        f'J_B2B là hợp đồng với board còn lại</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_markdown(geometry: Geometry) -> str:
    out = [
        "# Hình học board (sinh tự động)",
        "",
        "- Nguồn: `hardware/spec/boards.toml`; kiểm tra: `python -m hardware.geom.cli --check`.",
        "- Đơn vị mm, gốc toạ độ ở góc dưới-trái, nhìn từ trên.",
        "",
        "| Board | Kích thước | Diện tích | Lỗ bắt vít | Connector |",
        "|---|---|---|---|---|",
    ]
    for board in geometry.boards:
        out.append(
            f"| {board.name} | {board.width:.0f} × {board.height:.0f} × "
            f"{board.thickness:.1f} | {board.area_mm2 / 100:.1f} cm² | "
            f"{len(board.holes)} | {len(board.connectors)} |"
        )
    for board in geometry.boards:
        out += ["", f"## {board.name}", "", "| Connector | x | y | Cạnh | Ghi chú |",
                "|---|---|---|---|---|"]
        for connector in board.connectors:
            out.append(
                f"| {connector.name} | {connector.x:.1f} | {connector.y:.1f} | "
                f"{connector.edge} | {connector.note} |"
            )
        out += ["", "| Lỗ | x | y |", "|---|---|---|"]
        for index, hole in enumerate(board.holes):
            out.append(f"| H{index + 1} | {hole.x:.1f} | {hole.y:.1f} |")
    out += [
        "",
        "## Kiểm tra tự động",
        "",
        f"- Đường kính lỗ: {geometry.hole_diameter:.1f} mm, khe hở "
        f"{geometry.clearance:.1f} mm.",
        f"- Khoảng cách tối thiểu connector–lỗ: "
        f"{geometry.min_connector_distance:.1f} mm.",
        "- Cả hai board phải có `J_B2B` và khớp 26 chân của `spec/b2b.toml`.",
        "",
        "Đây là bản vẽ khái niệm để chốt vị trí; không phải bản vẽ chế tạo. "
        "Gerber cần KiCad và footprint đã kiểm bằng linh kiện thật.",
    ]
    return "\n".join(out) + "\n"
