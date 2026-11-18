"""Bind exported IPC-D-356 VIA diameters to source PCB via sizes."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import Contact, UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_via_binding import (
    SourceVia,
    require_ipc356_source_via_geometry,
    source_board_vias,
)
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_SOURCE_VIA = SourceVia("SIGNAL", 6_000_000, 5_000_000, 300_000, 700_000)


def _contact(*, size_x_mm: float | None = 0.7, size_y_mm: float | None = 0.0) -> Contact:
    return Contact(
        "SIGNAL",
        "VIA",
        "via",
        6.0,
        -5.0,
        "through",
        0.7,
        size_x_mm=size_x_mm,
        size_y_mm=size_y_mm,
    )


def test_matching_source_and_ipc356_via_diameters_are_supported() -> None:
    vias = source_board_vias((_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8"))

    assert vias == (_SOURCE_VIA,)
    require_ipc356_source_via_geometry(vias, (_contact(),))


@pytest.mark.parametrize("delta_nm", (1_270, -1_270))
def test_via_diameter_decimil_rounding_tolerance_is_allowed(delta_nm: int) -> None:
    diameter_mm = 0.7 + delta_nm / 1_000_000

    require_ipc356_source_via_geometry((_SOURCE_VIA,), (_contact(size_x_mm=diameter_mm),))


@pytest.mark.parametrize(
    ("size_x_mm", "size_y_mm", "message"),
    (
        (0.701272, 0.0, "dimensions differ"),
        (0.7, 0.01, "dimensions differ"),
        (None, 0.0, "dimensions are unavailable"),
        (0.7, None, "dimensions are unavailable"),
    ),
    ids=("oversized", "noncircular", "missing-x", "missing-y"),
)
def test_mismatched_or_unavailable_via_dimensions_fail_closed(
    size_x_mm: float | None, size_y_mm: float | None, message: str
) -> None:
    with pytest.raises(UnsupportedFabricationFormat, match=message):
        require_ipc356_source_via_geometry(
            (_SOURCE_VIA,), (_contact(size_x_mm=size_x_mm, size_y_mm=size_y_mm),)
        )


def test_source_via_without_bound_copper_size_fails_closed() -> None:
    source_without_size = SourceVia("SIGNAL", 6_000_000, 5_000_000, 300_000)

    with pytest.raises(UnsupportedFabricationFormat, match="copper size is unavailable"):
        require_ipc356_source_via_geometry((source_without_size,), (_contact(),))


@pytest.mark.parametrize(
    ("replacement", "message"),
    (
        ("", "copper size"),
        ("(size 0)", "non-positive copper size"),
        ("(size 0.7 0.8)", "copper size"),
    ),
    ids=("missing", "zero", "multiple-dimensions"),
)
def test_source_via_requires_one_positive_scalar_copper_size(
    replacement: str, message: str
) -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")
    malformed = board.replace("(size 0.7)", replacement, 1)

    with pytest.raises(UnsupportedFabricationFormat, match=message):
        source_board_vias(malformed)


def test_custom_via_padstack_fails_closed() -> None:
    board = (_FIXTURES / "via.kicad_pcb").read_text(encoding="utf-8")
    custom = board.replace("(size 0.7)", "(size 0.7) (padstack (mode front))", 1)

    with pytest.raises(UnsupportedFabricationFormat, match="custom padstack"):
        source_board_vias(custom)


def test_board_without_vias_accepts_no_exported_via_contacts() -> None:
    board = (_FIXTURES / "clean.kicad_pcb").read_text(encoding="utf-8")

    require_ipc356_source_via_geometry(source_board_vias(board), ())


def test_analyzer_rejects_mutated_via_diameter_before_rasterization(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, through=True)
    baseline = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings()
    )
    assert baseline.status == "PASS"

    ipc = fabrication / "board.d356"
    source = ipc.read_text(encoding="utf-8")
    ipc.write_text(source.replace("X0236Y0000", "X0394Y0000"), encoding="utf-8")
    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert not result.findings
    assert "VIA dimensions differ" in result.unsupported_reasons[0]
