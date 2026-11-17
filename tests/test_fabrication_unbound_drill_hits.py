"""Review policy for Excellon hits without source pad or via ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
    FabricationConnectivitySummary,
)
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _write_drills(
    path: Path,
    *,
    plating: str,
    hits: tuple[str, ...],
) -> None:
    function = "Plated,1,2,PTH" if plating == "plated" else "NonPlated,NPTH"
    path.write_text(
        "M48\n"
        f"; #@! TF.FileFunction,{function}\n"
        "FMAT,2\nMETRIC\n%\nG90\nG05\nT1C0.300\nT1\n" + "\n".join(hits) + "\nM30\n",
        encoding="utf-8",
    )


def _unbound(result: FabricationConnectivitySummary):
    return tuple(item for item in result.findings if item.code == "UNBOUND_DRILL_HIT")


def test_unbound_plated_hit_is_stable_review_blockable_and_exactly_ignorable(
    tmp_path: Path,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    pth = fabrication / "board-PTH.drl"
    _write_drills(pth, plating="plated", hits=("X12.000Y-12.000",))
    settings = FabricationConnectivitySettings()

    result = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)

    assert result == repeated
    assert result.analyzer_version == "15"
    assert result.status == "REVIEW"
    assert not result.unsupported_reasons
    (finding,) = _unbound(result)
    assert finding.location_mm == (12.0, 12.0)
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.plating == "plated"
    assert finding.drill_evidence.start_mm == (12.0, 12.0)
    assert finding.drill_evidence.end_mm is None
    assert finding.drill_evidence.diameter_mm == 0.3
    assert finding.drill_evidence.multiplicity == 1

    blocked = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(mode="block"),
    )
    assert blocked.status == "FAIL"
    assert _unbound(blocked) == (finding,)

    ignored_settings = FabricationConnectivitySettings(
        ignores=(
            FabricationConnectivityIgnore(
                fingerprint=finding.fingerprint,
                reason="intentional mechanical hole",
            ),
        )
    )
    ignored = analyze_fabrication_connectivity(board, fabrication, ignored_settings)
    assert ignored.status == "PASS"
    assert ignored.findings == ()
    assert ignored.ignored_findings == (finding,)

    _write_drills(pth, plating="plated", hits=())
    stale = analyze_fabrication_connectivity(board, fabrication, ignored_settings)
    assert stale.status == "FAIL"
    assert stale.stale_ignore_fingerprints == (finding.fingerprint,)


def test_identical_unbound_hits_are_grouped_with_multiplicity_in_identity(
    tmp_path: Path,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    pth = fabrication / "board-PTH.drl"
    _write_drills(pth, plating="plated", hits=("X12.000Y-12.000",))
    single = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )
    (single_finding,) = _unbound(single)

    _write_drills(
        pth,
        plating="plated",
        hits=("X12.000Y-12.000", "X12.000Y-12.000"),
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    (finding,) = _unbound(result)
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.multiplicity == 2
    assert finding.fingerprint != single_finding.fingerprint


def test_unbound_nonplated_slot_reports_board_coordinates_and_geometry(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    npth = fabrication / "board-NPTH.drl"
    _write_drills(
        npth,
        plating="nonplated",
        hits=("X12.000Y-12.000G85X14.000Y-12.000",),
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    (finding,) = _unbound(result)
    assert result.status == "REVIEW"
    assert finding.location_mm == (13.0, 12.0)
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.plating == "nonplated"
    assert finding.drill_evidence.start_mm == (12.0, 12.0)
    assert finding.drill_evidence.end_mm == (14.0, 12.0)
