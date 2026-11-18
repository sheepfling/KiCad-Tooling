"""Fail closed on unrepresentable IPC-D-356 numeric fields."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _replace_first_contact_coordinate(record: str, digits: str) -> str:
    updated, count = re.subn(r"(?<=A01X)[+ -]?[0-9]+(?=Y)", digits, record, count=1)
    assert count == 1
    return updated


def _replace_first_contact_size(record: str, digits: str) -> str:
    match = re.search(r"X([0-9]+)Y0000R000S2$", record)
    assert match is not None
    return record[: match.start(1)] + digits + record[match.end(1) :]


def _mutate_first_contact(fabrication: Path, mutate: Callable[[str], str]) -> None:
    path = fabrication / "board.d356"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = mutate(lines[1])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_unrepresentable_ipc_coordinate_returns_unsupported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _mutate_first_contact(
        fabrication,
        lambda line: _replace_first_contact_coordinate(line, "9" * 309),
    )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()
    assert "IPC-D-356 numeric field" in result.unsupported_reasons[0]


def test_unrepresentable_ipc_pad_size_returns_unsupported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _mutate_first_contact(
        fabrication,
        lambda line: _replace_first_contact_size(line, "9" * 309),
    )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()
    assert "IPC-D-356 numeric field" in result.unsupported_reasons[0]


def test_oversized_finite_ipc_pad_size_mismatch_returns_unsupported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _mutate_first_contact(
        fabrication,
        lambda line: _replace_first_contact_size(line, "9" * 100),
    )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()
    assert "pad dimensions differ" in result.unsupported_reasons[0]


def test_ipc_coordinates_require_ascii_digits(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    _mutate_first_contact(
        fabrication,
        lambda line: line.replace("A01X+001969Y", "A01X+٠٠١٩٦٩Y", 1),
    )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.findings == ()


def test_normal_ipc_numeric_fields_remain_supported(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.analyzer_version == "33"
    assert result.status == "PASS"
    assert result.unsupported_reasons == ()
