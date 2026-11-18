"""Source-land requirement selection and exact Gerber-flash matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    Contact,
    GerberFeature,
    GerberLayer,
    parse_gerber,
)
from kicad_tooling.hwrepo.fabrication_connectivity_raster import PadAssignment
from kicad_tooling.hwrepo.fabrication_contact_land import (
    CircularLandRequirement,
    circular_land_requirements,
    missing_circular_land_flashes,
    raster_visible_missing_layers,
)
from kicad_tooling.hwrepo.fabrication_contact_source import SourceComponentPad
from kicad_tooling.hwrepo.fabrication_via_binding import SourceVia

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _flash(x_mm: float, y_mm: float, diameter_mm: float = 1.0) -> GerberFeature:
    return GerberFeature("flash", ((x_mm, y_mm),), aperture=("C", (diameter_mm,)))


def _layer(name: str, *features: GerberFeature) -> GerberLayer:
    return GerberLayer(name, name, tuple(features))


def test_circular_requirements_include_only_full_stack_plated_round_lands() -> None:
    pads = (
        SourceComponentPad(
            "J1",
            "1",
            "SIGNAL",
            "through",
            5_000_000,
            5_000_000,
            drill_plating="plated",
            pad_shape="circle",
            size_x_nm=1_000_000,
            size_y_nm=1_000_000,
        ),
        SourceComponentPad(
            "J1",
            "2",
            "SIGNAL",
            "through",
            7_000_000,
            5_000_000,
            drill_plating="plated",
            pad_shape="oval",
            size_x_nm=1_000_000,
            size_y_nm=800_000,
        ),
        SourceComponentPad(
            "J1",
            "3",
            None,
            None,
            9_000_000,
            5_000_000,
            drill_plating="nonplated",
            pad_shape="circle",
            size_x_nm=1_000_000,
            size_y_nm=1_000_000,
        ),
        SourceComponentPad(
            "J1",
            "4",
            "SIGNAL",
            "through",
            11_000_000,
            5_000_000,
            drill_plating="plated",
            pad_shape="circle",
            size_x_nm=1_000_000,
            size_y_nm=1_000_000,
            has_custom_padstack=True,
        ),
    )
    vias = (SourceVia("SIGNAL", 6_000_000, 5_000_000, 400_000, 800_000),)

    requirements = circular_land_requirements(pads, vias)

    assert requirements == (
        CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000),
        CircularLandRequirement("VIA-via", "SIGNAL", 6_000_000, -5_000_000, 800_000),
    )


def test_source_flash_must_match_center_and_aperture_size_on_every_layer() -> None:
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    layers = (
        _layer("F.Cu", _flash(5.0, -5.0)),
        _layer("In1.Cu", _flash(5.0, -5.0, 0.8)),
        _layer("In2.Cu"),
    )

    missing = missing_circular_land_flashes(layers, (requirement,))

    assert len(missing) == 1
    assert missing[0].requirement == requirement
    assert missing[0].layers == ("In1.Cu", "In2.Cu")


def test_six_decimal_inch_rounding_is_accepted_but_a_shifted_flash_is_not() -> None:
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)

    within_quantization = _layer("F.Cu", _flash(5.000012, -5.000012, 1.000012))
    outside_quantization = _layer("In1.Cu", _flash(5.000014, -5.0, 1.0))

    missing = missing_circular_land_flashes(
        (within_quantization, outside_quantization), (requirement,)
    )

    assert len(missing) == 1
    assert missing[0].layers == ("In1.Cu",)


def test_each_source_contact_requires_its_own_flash_even_at_a_shared_center() -> None:
    first = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    second = CircularLandRequirement("J2-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    layer = _layer("F.Cu", _flash(5.0, -5.0))

    missing = missing_circular_land_flashes((layer,), (first, second))

    assert len(missing) == 1
    assert missing[0].requirement == second
    assert missing[0].layers == ("F.Cu",)


def test_extra_geometry_does_not_substitute_for_the_source_circle_flash() -> None:
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    rectangle = GerberFeature("flash", ((5.0, -5.0),), aperture=("R", (1.0, 1.0)))
    region = GerberFeature("region", ((4.5, -5.0), (5.5, -5.0), (5.0, -4.5), (4.5, -5.0)))

    missing = missing_circular_land_flashes((_layer("F.Cu", rectangle, region),), (requirement,))

    assert len(missing) == 1
    assert missing[0].layers == ("F.Cu",)


def test_source_flash_finding_is_limited_to_layers_with_raster_copper() -> None:
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    missing = missing_circular_land_flashes((_layer("F.Cu"), _layer("In1.Cu")), (requirement,))[0]
    assignment = PadAssignment(
        Contact("SIGNAL", "J1", "1", 5.0, -5.0, "through", 1.0),
        (7,),
        ("In1.Cu",),
    )

    assert raster_visible_missing_layers(missing, (assignment,)) == ("F.Cu",)


def test_source_flash_finding_defers_to_layer_presence_when_raster_sees_no_copper() -> None:
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 5_000_000, -5_000_000, 1_000_000)
    missing = missing_circular_land_flashes((_layer("F.Cu"), _layer("In1.Cu")), (requirement,))[0]
    assignment = PadAssignment(
        Contact("SIGNAL", "J1", "1", 5.0, -5.0, "through", 1.0),
        (),
        ("F.Cu", "In1.Cu"),
    )

    assert raster_visible_missing_layers(missing, (assignment,)) == ()


def test_inch_aperture_is_normalized_before_source_land_comparison(tmp_path: Path) -> None:
    gerber = tmp_path / "board-F_Cu.gbr"
    gerber.write_text(
        "%FSLAX46Y46*%\n%MOIN*%\n%ADD10C,0.039370*%\nD10*\nX5000000Y-5000000D03*\nM02*\n",
        encoding="utf-8",
    )
    layer = parse_gerber(gerber, "F.Cu")
    requirement = CircularLandRequirement("J1-1", "SIGNAL", 127_000_000, -127_000_000, 1_000_000)

    aperture = layer.features[0].aperture
    assert aperture is not None
    assert aperture[0] == "C"
    assert aperture[1] == pytest.approx((0.999998,))
    assert missing_circular_land_flashes((layer,), (requirement,)) == ()
