"""Enforce Gerber aperture identifier bounds and uniqueness."""

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


def _write_gerber(tmp_path: Path, *records: str) -> Path:
    path = tmp_path / "aperture-identity.gbr"
    path.write_text(
        "\n".join(("%FSLAX26Y26*%", "%MOMM*%", *records, "M02*", "")),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "definition",
    (
        pytest.param("%ADD9C,0.500000*%", id="reserved-code-below-10"),
        pytest.param("%ADD2147483648C,0.500000*%", id="above-signed-32-bit-max"),
        pytest.param("%ADD١٠C,0.500000*%", id="non-ascii-aperture-number"),
    ),
)
def test_invalid_aperture_identifiers_are_unsupported(tmp_path: Path, definition: str) -> None:
    gerber = _write_gerber(tmp_path, definition)

    with pytest.raises(UnsupportedFabricationFormat, match="aperture.*(identifier|number|D-code)"):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    "second_definition",
    (
        pytest.param("%ADD10R,0.5X0.5*%", id="same-number"),
        pytest.param("%ADD010R,0.5X0.5*%", id="same-number-with-leading-zero"),
    ),
)
def test_aperture_identifiers_cannot_be_reassigned(tmp_path: Path, second_definition: str) -> None:
    gerber = _write_gerber(
        tmp_path,
        "%ADD10C,0.500000*%",
        second_definition,
    )

    with pytest.raises(
        UnsupportedFabricationFormat, match="aperture.*(reassign|duplicate|already)"
    ):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    "selection",
    (
        pytest.param("D١٠*", id="non-ascii-number"),
        pytest.param("D9*", id="reserved-code-below-10"),
        pytest.param("D2147483648*", id="above-signed-32-bit-max"),
    ),
)
def test_aperture_selection_requires_an_ascii_number_in_range(
    tmp_path: Path, selection: str
) -> None:
    gerber = _write_gerber(
        tmp_path,
        "%ADD10C,0.500000*%",
        selection,
        "X0Y0D03*",
    )

    with pytest.raises(UnsupportedFabricationFormat, match="aperture D-code"):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    "identifier",
    ("10", "010", "2147483647"),
    ids=("minimum", "leading-zero", "signed-32-bit-maximum"),
)
def test_standard_aperture_identifier_boundaries_remain_supported(
    tmp_path: Path, identifier: str
) -> None:
    gerber = _write_gerber(
        tmp_path,
        f"%ADD{identifier}C,0.500000*%",
        f"D{identifier}*",
        "X0Y0D03*",
    )

    layer = parse_gerber(gerber, "F.Cu")

    assert len(layer.features) == 1


def test_reassigned_aperture_blocks_source_bound_connectivity(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    marker = "%ADD10C,0.500000*%"
    assert source.count(marker) == 1
    gerber.write_text(
        source.replace(marker, f"{marker}\n%ADD010R,0.5X0.5*%", 1),
        encoding="utf-8",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "42"
    assert result.status == "UNSUPPORTED"
    assert "aperture" in result.unsupported_reasons[0]
    assert result.findings == ()
