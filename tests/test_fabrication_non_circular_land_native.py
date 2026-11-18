"""Exact-version native evidence for oval and rectangular plated lands."""

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
    "fixtures/fabrication-connectivity/multilayer/four-layer-shaped-land-flash.kicad_pcb"
)
_COPPER_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def _export_fixture(image: str, tmp_path: Path, board_text: str) -> tuple[Path, Path]:
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    board = fixture_directory / "board.kicad_pcb"
    board.write_text(board_text, encoding="utf-8")
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
def test_native_missing_shaped_lands_are_found_with_route_copper_retained(
    tmp_path: Path, version: str
) -> None:
    board, output_directory = _export_fixture(
        PINNED_NATIVE_KICAD_IMAGES[version],
        tmp_path,
        _FIXTURE.read_text(encoding="utf-8"),
    )
    settings = FabricationConnectivitySettings(check_raster_phase_stability=False)

    control = analyze_fabrication_connectivity(board, output_directory, settings)

    assert control.status == "PASS"
    assert control.findings == ()
    assert control.unsupported_reasons == ()

    in2_gerber = output_directory / "board-In2_Cu.gbr"
    original = in2_gerber.read_text(encoding="utf-8")
    fault = original
    for x_mm in (5, 9, 13):
        fault = remove_native_gerber_flash(fault, x_mm, 5)
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
        (("J1-2",), "SIGNAL", (9.0, -5.0), ("In2.Cu",)),
        (("J1-3",), "SIGNAL", (13.0, -5.0), ("In2.Cu",)),
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
                    reason="synthetic exact-fingerprint shaped-land suppression control",
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


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_diagonal_rectangle_macro_remains_unsupported(tmp_path: Path, version: str) -> None:
    board_text = _FIXTURE.read_text(encoding="utf-8")
    original_pad = '(pad "3" thru_hole rect (at 8 0 90)'
    assert board_text.count(original_pad) == 1
    rotated_board = board_text.replace(original_pad, '(pad "3" thru_hole rect (at 8 0 45)', 1)
    board, output_directory = _export_fixture(
        PINNED_NATIVE_KICAD_IMAGES[version], tmp_path, rotated_board
    )

    report = analyze_fabrication_connectivity(
        board,
        output_directory,
        FabricationConnectivitySettings(check_raster_phase_stability=False),
    )

    assert report.status == "UNSUPPORTED"
    assert report.findings == ()
    assert any("RotRect" in reason for reason in report.unsupported_reasons)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_diagonal_oval_macro_remains_unsupported(tmp_path: Path, version: str) -> None:
    board_text = _FIXTURE.read_text(encoding="utf-8")
    original_pad = '(pad "1" thru_hole oval (at 0 0 90)'
    assert board_text.count(original_pad) == 1
    rotated_board = board_text.replace(original_pad, '(pad "1" thru_hole oval (at 0 0 45)', 1)
    board, output_directory = _export_fixture(
        PINNED_NATIVE_KICAD_IMAGES[version], tmp_path, rotated_board
    )

    report = analyze_fabrication_connectivity(
        board,
        output_directory,
        FabricationConnectivitySettings(check_raster_phase_stability=False),
    )

    assert report.status == "UNSUPPORTED"
    assert report.findings == ()
    assert report.unsupported_reasons
