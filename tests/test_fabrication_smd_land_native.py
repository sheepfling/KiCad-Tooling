"""Exact-version source-land coverage for top- and bottom-side SMD pads."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
)
from tests.fabrication_connectivity_native_support import (
    export_fabrication_outputs,
    remove_native_gerber_flash,
)
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_ARTIFACT_CONNECTIVITY") != "1",
        reason="native fabrication artifact checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURE = Path(__file__).parent / (
    "fixtures/fabrication-connectivity/multilayer/four-layer-smd-land-flash.kicad_pcb"
)
_COPPER_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
_SETTINGS = FabricationConnectivitySettings(check_raster_phase_stability=False)


def _export_fixture(image: str, tmp_path: Path) -> tuple[Path, Path]:
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    board = fixture_directory / "board.kicad_pcb"
    board.write_text(_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    export_fabrication_outputs(
        image,
        tmp_path,
        fixture_directory,
        output_directory,
        board,
        _COPPER_LAYERS,
    )
    return board, output_directory


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_missing_smd_lands_are_found_only_on_their_outer_copper(
    tmp_path: Path, version: str
) -> None:
    board, output_directory = _export_fixture(PINNED_NATIVE_KICAD_IMAGES[version], tmp_path)
    control = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)

    assert control.status == "PASS"
    assert control.findings == ()
    assert control.unsupported_reasons == ()

    top_gerber = output_directory / "board-F_Cu.gbr"
    bottom_gerber = output_directory / "board-B_Cu.gbr"
    original_top = top_gerber.read_text(encoding="utf-8")
    original_bottom = bottom_gerber.read_text(encoding="utf-8")
    faulted_top = remove_native_gerber_flash(original_top, 9, 10)
    faulted_top = remove_native_gerber_flash(faulted_top, 13, 10)
    faulted_bottom = remove_native_gerber_flash(original_bottom, 17, 10)
    top_gerber.write_text(faulted_top, encoding="utf-8")
    bottom_gerber.write_text(faulted_bottom, encoding="utf-8")

    report = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)
    repeated = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)

    assert report == repeated
    assert report.status == "REVIEW"
    assert {finding.code for finding in report.findings} == {"SOURCE_LAND_FLASH_MISSING"}
    assert {
        (finding.contacts, finding.net, finding.location_mm, finding.missing_layers)
        for finding in report.findings
    } == {
        (("J2-1",), "SIGNAL", (9.0, -10.0), ("F.Cu",)),
        (("J3-1",), "SIGNAL", (13.0, -10.0), ("F.Cu",)),
        (("J4-1",), "SIGNAL", (17.0, -10.0), ("B.Cu",)),
    }

    blocked = analyze_fabrication_connectivity(
        board,
        output_directory,
        FabricationConnectivitySettings(mode="block", check_raster_phase_stability=False),
    )
    ignored = analyze_fabrication_connectivity(
        board,
        output_directory,
        FabricationConnectivitySettings(
            mode="block",
            check_raster_phase_stability=False,
            ignores=tuple(
                FabricationConnectivityIgnore(
                    fingerprint=finding.fingerprint,
                    reason="synthetic exact-fingerprint SMD land suppression control",
                )
                for finding in report.findings
            ),
        ),
    )
    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert ignored.ignored_findings == report.findings

    top_gerber.write_text(original_top, encoding="utf-8")
    bottom_gerber.write_text(original_bottom, encoding="utf-8")
    restored = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)
    assert restored.status == "PASS"
    assert restored.findings == ()
