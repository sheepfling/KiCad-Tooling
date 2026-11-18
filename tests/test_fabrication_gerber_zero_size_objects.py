"""Gerber zero-size objects must not add copper during raster analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    Contact,
    GerberFeature,
    GerberLayer,
    parse_gerber,
)
from kicad_tooling.hwrepo.fabrication_connectivity_raster import analyze_raster

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _write_gerber_object(path: Path, diameter: float, operation: str) -> Path:
    object_commands = {
        "flash": "X0Y0D03*",
        "stroke": "X-500000Y0D02*\nX500000Y0D01*",
    }
    path.write_text(
        "\n".join(
            (
                "%FSLAX26Y26*%",
                "%MOMM*%",
                f"%ADD10C,{diameter}*%",
                "D10*",
                object_commands[operation],
                "M02*",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("operation", ("flash", "stroke"))
@pytest.mark.parametrize(
    ("diameter", "expect_short"),
    ((0.0, False), (0.1, True)),
    ids=("zero-size-does-not-add-copper", "positive-size-remains-copper"),
)
def test_zero_size_objects_do_not_create_phantom_copper(
    tmp_path: Path, operation: str, diameter: float, expect_short: bool
) -> None:
    gerber = _write_gerber_object(tmp_path / "synthetic-F_Cu.gbr", diameter, operation)
    layer = parse_gerber(gerber, "F.Cu")
    contacts = (
        Contact("NET_A", "J1", "1", 0.0, 0.0, "top", 0.2),
        Contact("NET_B", "J2", "1", 0.0, 0.0, "top", 0.2),
    )

    result = analyze_raster((layer,), contacts, (), density=100)

    assert bool(result.shorts) is expect_short
    assert bool(result.no_copper) is not expect_short


def test_zero_size_object_does_not_expand_raster_bounds() -> None:
    contact = Contact("NET_A", "J1", "1", 0.0, 0.0, "top", 0.2)
    remote_zero_flash = GerberFeature("flash", ((100_000.0, 100_000.0),), aperture=("C", (0.0,)))
    layer = GerberLayer("synthetic-F_Cu.gbr", "F.Cu", (remote_zero_flash,))

    result = analyze_raster((layer,), (contact,), (), density=25)

    assert result.no_copper == (contact,)
    assert result.shorts == ()
