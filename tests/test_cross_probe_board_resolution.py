"""Source and receipt identity for PCB cross-probe marker inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.cross_probe_board import resolve_cross_probe_board_markers
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing

pytestmark = [pytest.mark.architecture, pytest.mark.evidence_lint]


def _drawing(*, file: str = "pcb.svg", mapping_supported: bool = True) -> ReviewDrawing:
    return ReviewDrawing(
        kind="pcb",
        file=file,
        source_artifact="native/pcb.svg",
        sha256="b" * 64,
        width_mm=100.0,
        height_mm=80.0,
        mapping_supported=mapping_supported,
    )


def test_board_marker_resolution_binds_board_bytes_and_unique_receipt_drawing() -> None:
    source = (
        Path(__file__).parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
    ).read_bytes()
    source_sha256 = hashlib.sha256(source).hexdigest()
    drawing = _drawing()

    resolution = resolve_cross_probe_board_markers(
        board_path="projects/demo/kicad/demo.kicad_pcb",
        board_source_sha256=source_sha256,
        board_source=source,
        findings_view_path="build/findings-view/review.json",
        findings_view_sha256="c" * 64,
        drawings=(drawing,),
    )

    assert resolution.board_status == "COMPLETE"
    assert resolution.board_source_sha256 == source_sha256
    assert resolution.findings_view_path == "build/findings-view/review.json"
    assert resolution.findings_view_sha256 == "c" * 64
    assert resolution.anchors_by_casefolded_reference["c1"]
    assert resolution.drawing_candidates == (drawing,)
    assert resolution.drawing_status == "UNIQUE"
    assert resolution.board_drawing is drawing
    with pytest.raises(TypeError):
        resolution.anchors_by_casefolded_reference["r2"] = ()  # type: ignore[index]


def test_valid_empty_board_is_complete_not_blocked() -> None:
    source = b"(kicad_pcb)"

    resolution = resolve_cross_probe_board_markers(
        board_path="projects/demo/kicad/demo.kicad_pcb",
        board_source_sha256=hashlib.sha256(source).hexdigest(),
        board_source=source,
        findings_view_path="build/findings-view/review.json",
        findings_view_sha256="c" * 64,
        drawings=(),
    )

    assert resolution.board_status == "COMPLETE"
    assert not resolution.anchors_by_casefolded_reference
    assert not resolution.issues
    assert resolution.drawing_status == "UNAVAILABLE"


def test_missing_board_is_blocked_even_when_a_board_drawing_is_retained() -> None:
    drawing = _drawing()

    resolution = resolve_cross_probe_board_markers(
        board_path="projects/demo/kicad/demo.kicad_pcb",
        board_source_sha256=None,
        board_source=None,
        findings_view_path="build/findings-view/review.json",
        findings_view_sha256="c" * 64,
        drawings=(drawing,),
    )

    assert resolution.board_status == "BLOCKED"
    assert not resolution.anchors_by_casefolded_reference
    assert resolution.issues == ("PCB source is unavailable.",)
    assert resolution.drawing_status == "UNIQUE"
    assert resolution.board_drawing is drawing


def test_multiple_pcb_drawings_are_explicitly_ambiguous() -> None:
    first = _drawing(file="pcb-front.svg")
    second = _drawing(file="pcb-overview.svg")
    source = b"(kicad_pcb)"

    resolution = resolve_cross_probe_board_markers(
        board_path="projects/demo/kicad/demo.kicad_pcb",
        board_source_sha256=hashlib.sha256(source).hexdigest(),
        board_source=source,
        findings_view_path="build/findings-view/review.json",
        findings_view_sha256="c" * 64,
        drawings=(first, second),
    )

    assert resolution.drawing_status == "AMBIGUOUS"
    assert resolution.drawing_candidates == (first, second)
    assert resolution.board_drawing is None


def test_single_unsupported_pcb_drawing_is_retained_without_claiming_mapping() -> None:
    drawing = _drawing(mapping_supported=False)
    source = b"(kicad_pcb)"

    resolution = resolve_cross_probe_board_markers(
        board_path="projects/demo/kicad/demo.kicad_pcb",
        board_source_sha256=hashlib.sha256(source).hexdigest(),
        board_source=source,
        findings_view_path="build/findings-view/review.json",
        findings_view_sha256="c" * 64,
        drawings=(drawing,),
    )

    assert resolution.drawing_status == "UNSUPPORTED"
    assert resolution.board_drawing is drawing


def test_board_source_bytes_must_match_the_admitted_digest() -> None:
    with pytest.raises(ValueError, match="do not match their admitted source hash"):
        resolve_cross_probe_board_markers(
            board_path="projects/demo/kicad/demo.kicad_pcb",
            board_source_sha256="a" * 64,
            board_source=b"(kicad_pcb)",
            findings_view_path="build/findings-view/review.json",
            findings_view_sha256="c" * 64,
            drawings=(),
        )
