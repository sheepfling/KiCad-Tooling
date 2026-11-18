"""Fail closed when finite Gerber dimensions exceed raster limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, GerberLayer
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_connectivity_raster import analyze_raster
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize("oversized", (False, True), ids=("within-budget", "outside-budget"))
def test_finite_aperture_geometry_respects_raster_budget(tmp_path: Path, oversized: bool) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    if oversized:
        gerber = fabrication / "board-F_Cu.gbr"
        source = gerber.read_text(encoding="utf-8")
        marker = "%ADD10C,0.500000*%"
        assert source.count(marker) == 1
        gerber.write_text(
            source.replace(marker, f"%ADD10C,{'1' + '0' * 308}*%", 1),
            encoding="utf-8",
        )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "31"
    assert result.findings == ()
    if oversized:
        assert result.status == "UNSUPPORTED"
        assert "raster exceeds" in result.unsupported_reasons[0]
    else:
        assert result.status == "PASS"
        assert result.unsupported_reasons == ()


def test_finite_contact_geometry_exceeding_raster_budget_is_rejected() -> None:
    contact = Contact("SIGNAL", "J1", "1", 0.0, 0.0, "top", 1e100)

    with pytest.raises(ValueError, match="raster exceeds"):
        analyze_raster((GerberLayer("synthetic-F_Cu.gbr", "F.Cu", ()),), (contact,), (), 50)
