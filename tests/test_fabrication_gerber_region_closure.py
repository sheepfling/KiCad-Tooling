"""Reject Gerber regions whose contours are not explicitly closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_gerber,
)
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_CLOSED_TRIANGLE = """G36*
X1000000Y-1000000D02*
X2000000Y-1000000D01*
X2000000Y-2000000D01*
X1000000Y-1000000D01*
G37*
"""
_OPEN_TRIANGLE = _CLOSED_TRIANGLE.replace(
    "X1000000Y-1000000D01*\nG37*", "X1000000Y-2000000D01*\nG37*"
)


def _gerber_with_region(tmp_path: Path, region: str) -> tuple[Path, Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.count("M02*") == 1
    gerber.write_text(source.replace("M02*", f"{region}M02*", 1), encoding="utf-8")
    return board, fabrication, gerber


def _region(points: tuple[tuple[int, int], ...]) -> str:
    start, *remaining = points
    commands = ["G36*", f"X{start[0]}Y{start[1]}D02*"]
    commands.extend(f"X{x}Y{y}D01*" for x, y in remaining)
    return "\n".join(commands + ["G37*"]) + "\n"


def test_explicitly_closed_region_contour_remains_supported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, _CLOSED_TRIANGLE)

    layer = parse_gerber(gerber, "F.Cu")

    region = layer.features[-1]
    assert region.kind == "region"
    assert len(region.points) == 4
    assert region.points[0] == region.points[-1]


def test_open_region_contour_is_unsupported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, _OPEN_TRIANGLE)

    with pytest.raises(UnsupportedFabricationFormat, match="region contour.*closed"):
        parse_gerber(gerber, "F.Cu")


def test_arc_interpolation_remains_unsupported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, "G02*\n")

    with pytest.raises(UnsupportedFabricationFormat, match="arc or quadrant interpolation"):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    ("points", "reason"),
    [
        (
            ((0, 0), (4_000_000, 4_000_000), (0, 4_000_000), (4_000_000, 0), (0, 0)),
            "self-intersects",
        ),
        (
            (
                (0, 0),
                (4_000_000, 0),
                (4_000_000, 4_000_000),
                (2_000_000, 3_000_000),
                (0, 4_000_000),
                (2_000_000, 0),
                (1_000_000, -2_000_000),
                (0, 0),
            ),
            "self-intersects",
        ),
        (
            ((0, 0), (1_000_000, 0), (2_000_000, 0), (3_000_000, 0), (0, 0)),
            "overlapping adjacent edges",
        ),
        (
            ((0, 0), (2_000_000, 0), (2_000_000, 0), (0, 2_000_000), (0, 0)),
            "repeats a vertex",
        ),
        (
            ((0, 0), (3_000_000, 0), (1_000_000, 0), (2_000_000, 2_000_000), (0, 0)),
            "overlapping adjacent edges",
        ),
    ],
    ids=(
        "bow-tie",
        "non-adjacent-vertex-touch",
        "degenerate-collinear",
        "repeated-vertex",
        "overlap",
    ),
)
def test_non_simple_region_contours_are_unsupported(
    tmp_path: Path, points: tuple[tuple[int, int], ...], reason: str
) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, _region(points))

    with pytest.raises(UnsupportedFabricationFormat, match=reason):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    "vertices",
    [
        ((0, 0), (4_000_000, 0), (4_000_000, 4_000_000), (0, 4_000_000)),
        (
            (0, 0),
            (4_000_000, 0),
            (4_000_000, 4_000_000),
            (2_000_000, 2_000_000),
            (0, 4_000_000),
        ),
    ],
    ids=("convex", "concave"),
)
def test_simple_convex_and_concave_regions_support_translation_and_reversal(
    tmp_path: Path, vertices: tuple[tuple[int, int], ...]
) -> None:
    variants = (
        vertices + (vertices[0],),
        tuple((x + 12_345_000, y - 7_654_000) for x, y in vertices)
        + ((vertices[0][0] + 12_345_000, vertices[0][1] - 7_654_000),),
        tuple(reversed(vertices)) + (vertices[-1],),
    )
    for index, points in enumerate(variants):
        case_dir = tmp_path / str(index)
        case_dir.mkdir()
        _, _, gerber = _gerber_with_region(case_dir, _region(points))

        assert parse_gerber(gerber, "F.Cu").features[-1].kind == "region"


def test_region_with_more_than_the_bounded_edge_limit_is_unsupported(tmp_path: Path) -> None:
    vertices = tuple((index * 100, index * index * 100) for index in range(2_049))
    points = vertices + (vertices[0],)
    _, _, gerber = _gerber_with_region(tmp_path, _region(points))

    with pytest.raises(UnsupportedFabricationFormat, match="exceeds 2048 supported edges"):
        parse_gerber(gerber, "F.Cu")


def test_open_region_blocks_source_bound_connectivity(tmp_path: Path) -> None:
    board, fabrication, _ = _gerber_with_region(tmp_path, _OPEN_TRIANGLE)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "43"
    assert result.status == "UNSUPPORTED"
    assert "region contour" in result.unsupported_reasons[0]
    assert result.findings == ()


def test_self_intersecting_region_blocks_source_bound_connectivity(tmp_path: Path) -> None:
    bow_tie = ((0, 0), (4_000_000, 4_000_000), (0, 4_000_000), (4_000_000, 0), (0, 0))
    board, fabrication, _ = _gerber_with_region(tmp_path, _region(bow_tie))

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "43"
    assert result.status == "UNSUPPORTED"
    assert "self-intersects" in result.unsupported_reasons[0]
    assert result.findings == ()
