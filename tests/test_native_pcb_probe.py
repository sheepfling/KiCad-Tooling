"""Deterministic geometry serialization checks for the isolated native PCB probe."""

from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.resources import files
from importlib.util import module_from_spec, spec_from_loader
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

import pytest


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


class FakeLayerSet:
    def __init__(self, layers: set[int]) -> None:
        self.layers = layers

    def Contains(self, layer: int) -> bool:
        return layer in self.layers


class FakeEnabledLayers:
    def CuStack(self) -> tuple[int, ...]:
        return (0, 1, 2)


class FakeRuleArea:
    def __init__(self, *, is_rule_area: bool = True) -> None:
        self.is_rule_area = is_rule_area
        self.m_Uuid = type(
            "Uuid", (), {"AsString": lambda _self: "12345678-1234-5678-1234-567812345678"}
        )()

    def GetIsRuleArea(self) -> bool:
        return self.is_rule_area

    def Outline(self) -> FakeFilledPolygons:
        return FakeFilledPolygons(
            outlines=(FakeLineChain(((0, 0), (10, 0), (10, 8), (0, 8))),),
            holes=((FakeLineChain(((2, 2), (2, 4), (4, 4), (4, 2))),),),
        )

    def GetLayerSet(self) -> FakeLayerSet:
        return FakeLayerSet({0, 2})

    def GetNetname(self) -> str:
        return ""

    def GetZoneName(self) -> str:
        return "antenna-no-copper"

    def GetDoNotAllowTracks(self) -> bool:
        return True

    def GetDoNotAllowVias(self) -> bool:
        return True

    def GetDoNotAllowPads(self) -> bool:
        return True

    def GetDoNotAllowZoneFills(self) -> bool:
        return True

    def GetDoNotAllowFootprints(self) -> bool:
        return False


class FakeBoard:
    def GetEnabledLayers(self) -> FakeEnabledLayers:
        return FakeEnabledLayers()

    def GetLayerName(self, layer: int) -> str:
        return ("F.Cu", "In1.Cu", "B.Cu")[layer]


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


def test_ring_canonicalization_ignores_rotation_direction_and_duplicate_points() -> None:
    canonical_ring = cast(Any, probe_helpers()["canonical_ring_nm"])
    first = FakeLineChain(((3, 0), (3, 2), (0, 2), (0, 0), (3, 0)))
    rotated_reversed = FakeLineChain(((3, 2), (3, 2), (3, 0), (0, 0), (0, 2), (3, 2)))

    expected = [[0, 0], [0, 2], [3, 2], [3, 0]]
    assert canonical_ring(first) == expected
    assert canonical_ring(rotated_reversed) == expected


def test_island_contours_keep_native_indexes_and_sort_canonical_holes() -> None:
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

    assert tuple(item["island_index"] for item in result) == (0, 1)
    assert result[0]["outline_nm"][0] == [0, 0]
    assert result[0]["holes_nm"] == [
        [[1, 1], [1, 2], [2, 2], [2, 1]],
        [[7, 7], [7, 9], [9, 9], [9, 7]],
    ]
    assert result[1]["holes_nm"] == []


def test_canonicalization_rejects_degenerate_native_rings() -> None:
    canonical_ring = cast(Any, probe_helpers()["canonical_ring_nm"])

    with pytest.raises(ValueError, match="fewer than three distinct points"):
        canonical_ring(FakeLineChain(((0, 0), (1, 1), (0, 0))))


def test_rule_area_observation_serializes_outline_holes_layers_and_restrictions() -> None:
    rule_area_observation = cast(Any, probe_helpers()["rule_area_observation"])

    result = rule_area_observation(FakeRuleArea(), FakeBoard())

    assert result == {
        "uuid": "12345678-1234-5678-1234-567812345678",
        "name": "antenna-no-copper",
        "layers": ["F.Cu", "B.Cu"],
        "net": None,
        "polygons": [
            {
                "outline_nm": [[0, 0], [0, 8], [10, 8], [10, 0]],
                "holes_nm": [[[2, 2], [2, 4], [4, 4], [4, 2]]],
            }
        ],
        "forbids_tracks": True,
        "forbids_vias": True,
        "forbids_pads": True,
        "forbids_zone_fills": True,
        "forbids_footprints": False,
    }


def test_rule_area_observation_ignores_non_rule_zones() -> None:
    rule_area_observation = cast(Any, probe_helpers()["rule_area_observation"])

    assert rule_area_observation(FakeRuleArea(is_rule_area=False), FakeBoard()) is None
