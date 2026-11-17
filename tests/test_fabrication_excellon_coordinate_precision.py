"""Keep Excellon binding tolerances specific to each coordinate axis."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_contact_source import SourceComponentPad
from kicad_tooling.hwrepo.fabrication_drill_binding import require_excellon_source_drills
from kicad_tooling.hwrepo.fabrication_excellon import DrillHit, parse_excellon

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _source_pad(x_nm: int, y_nm: int) -> SourceComponentPad:
    return SourceComponentPad(
        reference="J1",
        number="1",
        net_name="SIGNAL",
        contact_layer="through",
        x_nm=x_nm,
        y_nm=y_nm,
        drill_nm=300_000,
        drill_plating="plated",
        drill_shape="circular",
        drill_width_nm=300_000,
        drill_height_nm=300_000,
    )


def _source_oval_pad(width_nm: int, height_nm: int) -> SourceComponentPad:
    return SourceComponentPad(
        reference="J1",
        number="1",
        net_name="SIGNAL",
        contact_layer="through",
        x_nm=10_000_000,
        y_nm=20_000_000,
        drill_nm=min(width_nm, height_nm),
        drill_plating="plated",
        drill_shape="oval",
        drill_width_nm=width_nm,
        drill_height_nm=height_nm,
    )


def _hit(coordinates: str, tool_diameter: str = "0.300") -> DrillHit:
    (hit,) = parse_excellon(
        f"M48\n; FILE_FORMAT=3:0\nMETRIC,LZ\nT1C{tool_diameter}\n%\nT1\n{coordinates}\nM30\n"
    )
    return hit


def _routed_slot_hit(start: str, end: str) -> DrillHit:
    (hit,) = parse_excellon(
        f"M48\n; FILE_FORMAT=3:0\nMETRIC,LZ\nT1C0.600\n%\nT1\nG00{start}\nM15\nG01{end}\nM16\nM30\n"
    )
    return hit


@pytest.mark.parametrize(
    ("coordinates", "source_x_nm", "source_y_nm"),
    (
        ("X010Y-20.000", 10_000_000, 20_100_000),
        ("X10.000Y-020", 10_100_000, 20_000_000),
    ),
    ids=("coarse-x-must-not-widen-y", "coarse-y-must-not-widen-x"),
)
def test_coarse_axis_precision_does_not_hide_precise_axis_mismatch(
    coordinates: str,
    source_x_nm: int,
    source_y_nm: int,
) -> None:
    hit = _hit(coordinates)

    with pytest.raises(UnsupportedFabricationFormat, match="no circular drill hit at source pad"):
        require_excellon_source_drills((_source_pad(source_x_nm, source_y_nm),), (), (hit,), ())


@pytest.mark.parametrize(
    ("coordinates", "source_x_nm", "source_y_nm"),
    (
        ("X010Y-20.000", 10_400_000, 20_000_000),
        ("X10.000Y-020", 10_000_000, 20_400_000),
    ),
    ids=("coarse-x-rounding-control", "coarse-y-rounding-control"),
)
def test_each_axis_accepts_its_own_declared_rounding_interval(
    coordinates: str,
    source_x_nm: int,
    source_y_nm: int,
) -> None:
    hit = _hit(coordinates)

    assert (
        require_excellon_source_drills((_source_pad(source_x_nm, source_y_nm),), (), (hit,), ())
        == ()
    )


@pytest.mark.parametrize(
    ("coordinates", "width_nm", "height_nm", "reject"),
    (
        ("X10Y-19.950G85X10.4Y-20.050", 1_000_000, 600_000, True),
        ("X10Y-20.000G85X10.4Y-20.000", 1_000_000, 600_000, False),
        ("X9.950Y-20G85X10.050Y-20.4", 600_000, 1_000_000, True),
        ("X10.000Y-20G85X10.000Y-20.4", 600_000, 1_000_000, False),
    ),
    ids=(
        "coarse-x-must-not-widen-precise-y-slot",
        "coarse-x-slot-control",
        "coarse-y-must-not-widen-precise-x-slot",
        "coarse-y-slot-control",
    ),
)
def test_slot_geometry_uses_per_axis_coordinate_precision(
    coordinates: str,
    width_nm: int,
    height_nm: int,
    reject: bool,
) -> None:
    hit = _hit(coordinates, "0.600")
    source_pad = _source_oval_pad(width_nm, height_nm)

    if reject:
        with pytest.raises(UnsupportedFabricationFormat, match="slot geometry"):
            require_excellon_source_drills((source_pad,), (), (hit,), ())
    else:
        assert require_excellon_source_drills((source_pad,), (), (hit,), ()) == ()


@pytest.mark.parametrize(
    (
        "start",
        "end",
        "width_nm",
        "height_nm",
        "reject",
        "x_resolution_nm",
        "y_resolution_nm",
    ),
    (
        (
            "X10Y-19.950",
            "X10.4Y-20.050",
            1_000_000,
            600_000,
            True,
            1_000_000,
            1_000,
        ),
        (
            "X10Y-20.000",
            "X10.4Y-20.000",
            1_000_000,
            600_000,
            False,
            1_000_000,
            1_000,
        ),
        (
            "X9.950Y-20",
            "X10.050Y-20.4",
            600_000,
            1_000_000,
            True,
            1_000,
            1_000_000,
        ),
        (
            "X10.000Y-20",
            "X10.000Y-20.4",
            600_000,
            1_000_000,
            False,
            1_000,
            1_000_000,
        ),
    ),
    ids=(
        "coarse-x-must-not-widen-precise-y-routed-slot",
        "coarse-x-routed-slot-control",
        "coarse-y-must-not-widen-precise-x-routed-slot",
        "coarse-y-routed-slot-control",
    ),
)
def test_routed_slot_geometry_uses_per_axis_coordinate_precision(
    start: str,
    end: str,
    width_nm: int,
    height_nm: int,
    reject: bool,
    x_resolution_nm: int,
    y_resolution_nm: int,
) -> None:
    hit = _routed_slot_hit(start, end)
    source_pad = _source_oval_pad(width_nm, height_nm)

    assert (hit.x_coordinate_resolution_nm, hit.y_coordinate_resolution_nm) == (
        x_resolution_nm,
        y_resolution_nm,
    )
    if reject:
        with pytest.raises(UnsupportedFabricationFormat, match="slot geometry"):
            require_excellon_source_drills((source_pad,), (), (hit,), ())
    else:
        assert require_excellon_source_drills((source_pad,), (), (hit,), ()) == ()
