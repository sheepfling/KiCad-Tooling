"""Exact-version native evidence for source-shaped circular PTH lands."""

from __future__ import annotations

import os
import shutil
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
    "fixtures/fabrication-connectivity/multilayer/four-layer-land-flash.kicad_pcb"
)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_missing_land_flashes_are_found_with_route_copper_retained(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    board = fixture_directory / "board.kicad_pcb"
    shutil.copyfile(_FIXTURE, board)
    export_fabrication_outputs(
        image,
        tmp_path,
        fixture_directory,
        output_directory,
        board,
        ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"),
    )
    settings = FabricationConnectivitySettings(check_raster_phase_stability=False)

    control = analyze_fabrication_connectivity(board, output_directory, settings)

    assert control.status == "PASS"
    assert control.findings == ()
    assert control.unsupported_reasons == ()

    in2_gerber = output_directory / "board-In2_Cu.gbr"
    original = in2_gerber.read_text(encoding="utf-8")
    fault = remove_native_gerber_flash(original, 5, 5)
    fault = remove_native_gerber_flash(fault, 7, 5)
    in2_gerber.write_text(fault, encoding="utf-8")

    repeated = analyze_fabrication_connectivity(board, output_directory, settings)
    report = analyze_fabrication_connectivity(board, output_directory, settings)

    assert report == repeated
    assert report.status == "REVIEW"
    assert {item.code for item in report.findings} == {"SOURCE_LAND_FLASH_MISSING"}
    assert {
        (item.contacts, item.net, item.location_mm, item.missing_layers) for item in report.findings
    } == {
        (("J1-1",), "SIGNAL", (5.0, -5.0), ("In2.Cu",)),
        (("J1-2",), "SIGNAL", (7.0, -5.0), ("In2.Cu",)),
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
                    fingerprint=item.fingerprint,
                    reason="synthetic exact-fingerprint land suppression control",
                )
                for item in report.findings
            ),
        ),
    )
    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert ignored.ignored_findings == report.findings

    in2_gerber.write_text(original, encoding="utf-8")
    restored = analyze_fabrication_connectivity(board, output_directory, settings)
    assert restored.status == "PASS"
    assert restored.findings == ()
