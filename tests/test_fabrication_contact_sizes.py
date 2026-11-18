"""IPC-D-356 pad dimensions must match the source PCB pad geometry."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def test_ipc_pad_size_mismatch_with_source_returns_unsupported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    ipc = fabrication / "board.d356"
    source = ipc.read_text(encoding="utf-8")
    marker = "X0394Y0000"
    assert source.count(marker) == 2
    ipc.write_text(source.replace(marker, "X0591Y0000", 1), encoding="utf-8")

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()
    assert "pad dimensions differ" in result.unsupported_reasons[0]


def _set_first_pad_as_rectangle(board: Path, fabrication: Path, y_size: str) -> None:
    source = board.read_text(encoding="utf-8")
    marker = '(pad "1" smd circle (at 0 0) (size 1 1)'
    assert source.count(marker) == 1
    board.write_text(
        source.replace(marker, '(pad "1" smd rect (at 0 0) (size 2 1)'), encoding="utf-8"
    )

    ipc = fabrication / "board.d356"
    lines = ipc.read_text(encoding="utf-8").splitlines()
    updated, count = re.subn(
        r"X[0-9]{4}Y[0-9]{4}R[0-9]{3}S[0-9]", f"X0787Y{y_size}R000S2", lines[1], count=1
    )
    assert count == 1
    lines[1] = updated
    ipc.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_rectangular_ipc_dimensions_match_source_control(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _set_first_pad_as_rectangle(board, fabrication, "0394")

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "PASS"
    assert result.unsupported_reasons == ()


def test_rectangular_ipc_y_size_mismatch_with_source_is_unsupported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _set_first_pad_as_rectangle(board, fabrication, "0591")

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()
    assert "pad dimensions differ" in result.unsupported_reasons[0]
