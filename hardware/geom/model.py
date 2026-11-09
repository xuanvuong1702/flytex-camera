"""Mô hình hình học board: đọc spec, kiểm tra, phục vụ vẽ."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "hardware" / "spec" / "boards.toml"
B2B_SPEC_PATH = ROOT / "spec" / "b2b.toml"

EDGES = ("top", "bottom", "left", "right", "inside")


class GeometryError(ValueError):
    """Hình học board không hợp lệ."""


@dataclass(frozen=True)
class Hole:
    x: float
    y: float


@dataclass(frozen=True)
class Connector:
    name: str
    x: float
    y: float
    edge: str
    note: str = ""


@dataclass(frozen=True)
class Board:
    key: str
    name: str
    width: float
    height: float
    thickness: float
    holes: tuple[Hole, ...]
    connectors: tuple[Connector, ...]

    @property
    def area_mm2(self) -> float:
        return self.width * self.height

    def connector(self, name: str) -> Connector | None:
        for item in self.connectors:
            if item.name == name:
                return item
        return None


@dataclass(frozen=True)
class Geometry:
    boards: tuple[Board, ...]
    hole_diameter: float
    clearance: float
    min_connector_distance: float

    def board(self, key: str) -> Board:
        for item in self.boards:
            if item.key == key:
                return item
        raise GeometryError(f"khong co board {key}")


def b2b_pin_count() -> int:
    with B2B_SPEC_PATH.open("rb") as handle:
        spec = tomllib.load(handle)
    return int(spec["connector"]["pins_total"])


def load(path: str | Path | None = None) -> Geometry:
    source = Path(path) if path is not None else SPEC_PATH
    with source.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("schema") != "flytex.boards/1":
        raise GeometryError("schema khong dung flytex.boards/1")
    mounting = data.get("mounting", {})
    hole_d = float(mounting.get("hole_diameter_mm", 3.2))
    clearance = float(mounting.get("clearance_mm", 0.5))
    min_distance = float(mounting.get("min_connector_distance_mm", 3.0))
    boards: list[Board] = []
    for key in ("pwr", "cmp"):
        raw = data.get(key)
        if not isinstance(raw, dict):
            raise GeometryError(f"thieu khoi [{key}]")
        holes = tuple(
            Hole(float(item["x"]), float(item["y"]))
            for item in raw.get("mount_holes", [])
        )
        connectors = tuple(
            Connector(
                str(item["name"]),
                float(item["x"]),
                float(item["y"]),
                str(item.get("edge", "inside")),
                str(item.get("note", "")),
            )
            for item in raw.get("connectors", [])
        )
        boards.append(
            Board(
                key=key,
                name=str(raw.get("name", key.upper())),
                width=float(raw["width_mm"]),
                height=float(raw["height_mm"]),
                thickness=float(raw.get("thickness_mm", 1.6)),
                holes=holes,
                connectors=connectors,
            )
        )
    return Geometry(tuple(boards), hole_d, clearance, min_distance)


def validate(geometry: Geometry) -> list[str]:
    """Trả danh sách lỗi; danh sách rỗng nghĩa là hợp lệ."""
    issues: list[str] = []
    names: set[str] = set()
    for board in geometry.boards:
        if board.name in names:
            issues.append(f"trung ten board: {board.name}")
        names.add(board.name)
        if not 20.0 <= board.width <= 200.0 or not 20.0 <= board.height <= 200.0:
            issues.append(f"{board.name}: kich thuoc ngoai dai 20..200 mm")
        radius = geometry.hole_diameter / 2.0 + geometry.clearance
        for index, hole in enumerate(board.holes):
            if not (radius <= hole.x <= board.width - radius):
                issues.append(f"{board.name}: lo {index} ngoai bien theo x")
            if not (radius <= hole.y <= board.height - radius):
                issues.append(f"{board.name}: lo {index} ngoai bien theo y")
        for i, first in enumerate(board.holes):
            for second in board.holes[i + 1:]:
                distance = math.hypot(first.x - second.x, first.y - second.y)
                if distance < geometry.hole_diameter + geometry.clearance:
                    issues.append(
                        f"{board.name}: hai lo qua gan ({distance:.2f} mm)"
                    )
        seen: set[str] = set()
        for connector in board.connectors:
            if connector.name in seen:
                issues.append(f"{board.name}: trung connector {connector.name}")
            seen.add(connector.name)
            if connector.edge not in EDGES:
                issues.append(f"{connector.name}: edge khong hop le")
            if not (0.0 <= connector.x <= board.width):
                issues.append(f"{connector.name}: x ngoai board")
            if not (0.0 <= connector.y <= board.height):
                issues.append(f"{connector.name}: y ngoai board")
            if connector.edge == "top" and connector.y != board.height:
                issues.append(f"{connector.name}: edge top nhung y != height")
            if connector.edge == "bottom" and connector.y != 0.0:
                issues.append(f"{connector.name}: edge bottom nhung y != 0")
            if connector.edge == "left" and connector.x != 0.0:
                issues.append(f"{connector.name}: edge left nhung x != 0")
            if connector.edge == "right" and connector.x != board.width:
                issues.append(f"{connector.name}: edge right nhung x != width")
            if connector.edge == "inside" and (
                connector.x in (0.0, board.width) or connector.y in (0.0, board.height)
            ):
                issues.append(f"{connector.name}: edge inside nhung nam tren bien")
            for hole in board.holes:
                distance = math.hypot(
                    connector.x - hole.x, connector.y - hole.y
                )
                if distance < radius + geometry.min_connector_distance:
                    issues.append(
                        f"{connector.name}: qua gan lo bat vit ({distance:.2f} mm)"
                    )
    for board in geometry.boards:
        b2b = board.connector("J_B2B")
        if b2b is None:
            issues.append(f"{board.name}: thieu J_B2B")
    pins = b2b_pin_count()
    if pins != 26:
        issues.append(f"spec/b2b.toml co {pins} chan, hinh hoc gia dinh 26 (2x13)")
    return issues


def check(geometry: Geometry | None = None) -> Geometry:
    geometry = geometry if geometry is not None else load()
    issues = validate(geometry)
    if issues:
        raise GeometryError("; ".join(issues))
    return geometry
