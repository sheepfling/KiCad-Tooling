"""Deterministic geometry serialization checks for the isolated native PCB probe."""

from __future__ import annotations

import unittest
from importlib.machinery import SourceFileLoader
from importlib.resources import files
from importlib.util import module_from_spec, spec_from_loader
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch


class FakePoint:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class FakeLineChain:
    def __init__(self, points: tuple[tuple[int, int], ...]) -> None:
        self._points = tuple(FakePoint(*point) for point in points)

    def PointCount(self) -> int:
        return len(self._points)

    def CPoint(self, index: int) -> FakePoint:
        return self._points[index]


class FakeFilledPolygons:
    def __init__(
        self,
        outlines: tuple[FakeLineChain, ...],
        holes: tuple[tuple[FakeLineChain, ...], ...],
    ) -> None:
        self._outlines = outlines
        self._holes = holes

    def OutlineCount(self) -> int:
        return len(self._outlines)

    def COutline(self, island_index: int) -> FakeLineChain:
        return self._outlines[island_index]

    def HoleCount(self, island_index: int) -> int:
        return len(self._holes[island_index])

    def CHole(self, island_index: int, hole_index: int) -> FakeLineChain:
        return self._holes[island_index][hole_index]


def probe_helpers() -> dict[str, Any]:
    resource = files("kicad_tooling.hwrepo").joinpath("native_pcb_probe.py.in")
    loader = SourceFileLoader("native_pcb_probe_test", str(resource))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Could not create the isolated native probe test module")
    module = module_from_spec(spec)
    with patch.dict("sys.modules", {"pcbnew": ModuleType("pcbnew")}):
        loader.exec_module(module)
    return vars(module)


class NativePcbProbeGeometryTests(unittest.TestCase):
    def test_ring_canonicalization_ignores_rotation_direction_and_duplicate_points(self) -> None:
        canonical_ring = cast(Any, probe_helpers()["canonical_ring_nm"])
        first = FakeLineChain(((3, 0), (3, 2), (0, 2), (0, 0), (3, 0)))
        rotated_reversed = FakeLineChain(((3, 2), (3, 2), (3, 0), (0, 0), (0, 2), (3, 2)))

        expected = [[0, 0], [0, 2], [3, 2], [3, 0]]
        self.assertEqual(canonical_ring(first), expected)
        self.assertEqual(canonical_ring(rotated_reversed), expected)

    def test_island_contours_keep_native_indexes_and_sort_canonical_holes(self) -> None:
        filled_zone_islands = cast(Any, probe_helpers()["filled_zone_islands"])
        outer = FakeLineChain(((0, 0), (10, 0), (10, 10), (0, 10)))
        larger_hole = FakeLineChain(((7, 7), (7, 9), (9, 9), (9, 7)))
        smaller_hole = FakeLineChain(((1, 1), (2, 1), (2, 2), (1, 2)))
        second_island = FakeLineChain(((20, 20), (24, 20), (24, 24), (20, 24)))
        filled = FakeFilledPolygons(
            outlines=(outer, second_island),
            holes=((larger_hole, smaller_hole), ()),
        )

        result = filled_zone_islands(filled)

        self.assertEqual(tuple(item["island_index"] for item in result), (0, 1))
        self.assertEqual(result[0]["outline_nm"][0], [0, 0])
        self.assertEqual(
            result[0]["holes_nm"],
            [
                [[1, 1], [1, 2], [2, 2], [2, 1]],
                [[7, 7], [7, 9], [9, 9], [9, 7]],
            ],
        )
        self.assertEqual(result[1]["holes_nm"], [])

    def test_canonicalization_rejects_degenerate_native_rings(self) -> None:
        canonical_ring = cast(Any, probe_helpers()["canonical_ring_nm"])

        with self.assertRaisesRegex(ValueError, "fewer than three distinct points"):
            canonical_ring(FakeLineChain(((0, 0), (1, 1), (0, 0))))


if __name__ == "__main__":
    unittest.main()
