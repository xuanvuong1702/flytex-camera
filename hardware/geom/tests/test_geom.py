"""Test mô hình hình học board và bản vẽ sinh ra."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.geom import cli, draw, model  # noqa: E402


def as_dict(geometry: model.Geometry) -> dict:
    return {
        "boards": [
            {
                "key": board.key,
                "name": board.name,
                "width": board.width,
                "height": board.height,
                "thickness": board.thickness,
                "holes": [(hole.x, hole.y) for hole in board.holes],
                "connectors": [
                    (item.name, item.x, item.y, item.edge) for item in board.connectors
                ],
            }
            for board in geometry.boards
        ]
    }


class ModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = model.load()

    def test_spec_is_valid(self) -> None:
        self.assertEqual(model.validate(self.geometry), [])
        model.check(self.geometry)

    def test_two_boards_with_b2b(self) -> None:
        names = [board.name for board in self.geometry.boards]
        self.assertEqual(names, ["PWR", "CMP"])
        for board in self.geometry.boards:
            self.assertIsNotNone(board.connector("J_B2B"))

    def test_hole_outside_rejected(self) -> None:
        broken = copy.deepcopy(self.geometry)
        pwr = broken.boards[0]
        object.__setattr__(pwr, "holes", pwr.holes + (model.Hole(0.5, 0.5),))
        self.assertTrue(any("ngoai bien" in item for item in model.validate(broken)))

    def test_overlapping_holes_rejected(self) -> None:
        broken = copy.deepcopy(self.geometry)
        pwr = broken.boards[0]
        object.__setattr__(pwr, "holes", pwr.holes + (model.Hole(5.5, 5.0),))
        self.assertTrue(any("qua gan" in item for item in model.validate(broken)))

    def test_connector_off_edge_rejected(self) -> None:
        broken = copy.deepcopy(self.geometry)
        pwr = broken.boards[0]
        object.__setattr__(
            pwr,
            "connectors",
            pwr.connectors + (model.Connector("J_X", 50.0, 5.0, "top"),),
        )
        self.assertTrue(any("edge top" in item for item in model.validate(broken)))

    def test_duplicate_connector_rejected(self) -> None:
        broken = copy.deepcopy(self.geometry)
        pwr = broken.boards[0]
        object.__setattr__(
            pwr,
            "connectors",
            pwr.connectors + (model.Connector("J_USBC", 30.0, 0.0, "bottom"),),
        )
        self.assertTrue(any("trung connector" in item for item in model.validate(broken)))

    def test_missing_b2b_rejected(self) -> None:
        broken = copy.deepcopy(self.geometry)
        pwr = broken.boards[0]
        kept = tuple(item for item in pwr.connectors if item.name != "J_B2B")
        object.__setattr__(pwr, "connectors", kept)
        self.assertTrue(any("thieu J_B2B" in item for item in model.validate(broken)))


class DrawTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = model.check()

    def test_svg_contains_board_and_connectors(self) -> None:
        svg = draw.render_svg(self.geometry.board("pwr"), self.geometry)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("PWR", svg)
        self.assertIn("J_B2B", svg)
        self.assertIn("J_USBC", svg)
        self.assertIn("</svg>", svg)

    def test_markdown_lists_boards_and_connectors(self) -> None:
        text = draw.render_markdown(self.geometry)
        self.assertIn("## PWR", text)
        self.assertIn("## CMP", text)
        self.assertIn("J_B2B", text)
        self.assertIn("26 chân", text)

    def test_cli_check_matches_files(self) -> None:
        self.assertEqual(cli.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
