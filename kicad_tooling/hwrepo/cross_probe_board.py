"""Read placed footprint anchors from one hash-checked KiCad board source."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

from .findings_view_models import ReviewDrawing
from .kicad_sexpr import sexpr_atoms as _atoms
from .kicad_sexpr import sexpr_children as _children
from .model_primitives import Digest, RepositoryPath


@dataclass(frozen=True, slots=True)
class BoardFootprintAnchor:
    reference: str
    footprint: str
    x_mm: float | None
    y_mm: float | None
    side: Literal["F.Cu", "B.Cu"] | None
    issue: str | None = None


BoardFootprintAnchorsByCasefoldedReference: TypeAlias = Mapping[
    str, tuple[BoardFootprintAnchor, ...]
]
BoardMarkerDrawingStatus: TypeAlias = Literal["UNAVAILABLE", "UNIQUE", "AMBIGUOUS", "UNSUPPORTED"]


@dataclass(frozen=True, slots=True)
class CrossProbeBoardMarkerResolution:
    """Bind PCB anchors and the selected drawing state to their source receipts."""

    board_path: RepositoryPath
    board_source_sha256: Digest | None
    board_status: Literal["COMPLETE", "BLOCKED"]
    anchors_by_casefolded_reference: BoardFootprintAnchorsByCasefoldedReference
    findings_view_path: RepositoryPath
    findings_view_sha256: Digest
    drawing_candidates: tuple[ReviewDrawing, ...]
    drawing_status: BoardMarkerDrawingStatus
    board_drawing: ReviewDrawing | None
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        anchors = MappingProxyType(
            {
                reference: tuple(items)
                for reference, items in self.anchors_by_casefolded_reference.items()
            }
        )
        drawing_candidates = tuple(self.drawing_candidates)
        issues = tuple(self.issues)
        if any(
            not reference or reference != reference.casefold() or not items
            for reference, items in anchors.items()
        ):
            raise ValueError("PCB anchor indexes require non-empty case-folded entries")
        if any(
            anchor.reference.casefold() != reference
            for reference, items in anchors.items()
            for anchor in items
        ):
            raise ValueError("PCB anchors must match their normalized index keys")
        expected_board_status = "COMPLETE" if self.board_source_sha256 is not None else "BLOCKED"
        if self.board_status != expected_board_status:
            raise ValueError("PCB board status must match its retained source hash")
        if self.board_status == "BLOCKED":
            if anchors or issues != ("PCB source is unavailable.",):
                raise ValueError("Unavailable PCB source requires blocked empty anchor evidence")
        elif issues:
            raise ValueError("Complete PCB source evidence cannot carry capture issues")
        if any(drawing.kind != "pcb" for drawing in drawing_candidates):
            raise ValueError("PCB drawing resolution may retain only PCB drawings")
        if not drawing_candidates:
            expected_drawing_status = "UNAVAILABLE"
        elif len(drawing_candidates) > 1:
            expected_drawing_status = "AMBIGUOUS"
        else:
            selected = next(iter(drawing_candidates))
            expected_drawing_status = "UNIQUE" if selected.mapping_supported else "UNSUPPORTED"
        if self.drawing_status != expected_drawing_status:
            raise ValueError("PCB drawing status must match its retained candidates")
        expected_drawing = next(iter(drawing_candidates)) if len(drawing_candidates) == 1 else None
        if self.board_drawing != expected_drawing:
            raise ValueError("Only one retained PCB drawing may be selected")
        object.__setattr__(self, "anchors_by_casefolded_reference", anchors)
        object.__setattr__(self, "drawing_candidates", drawing_candidates)
        object.__setattr__(self, "issues", issues)


def board_footprint_anchors(source: bytes) -> BoardFootprintAnchorsByCasefoldedReference:
    """Index all anchors by case-folded reference without discarding duplicates."""
    try:
        text = source.decode("utf-8")
        roots = _children(text, 0, len(text))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Malformed KiCad PCB source") from exc
    if len(roots) != 1 or _atoms(text, roots[0])[:1] != ("kicad_pcb",):
        raise ValueError("Expected one kicad_pcb root")
    found: dict[str, list[BoardFootprintAnchor]] = defaultdict(list)
    for node in _children(text, roots[0].start + 1, roots[0].end - 1):
        header = _atoms(text, node)
        if not header or header[0] not in {"footprint", "module"}:
            continue
        footprint = header[1] if len(header) > 1 else ""
        children = _children(text, node.start + 1, node.end - 1)
        atoms = tuple(_atoms(text, child) for child in children)
        references = [
            item[2] for item in atoms if len(item) == 3 and item[:2] == ("property", "Reference")
        ]
        if not references:
            references = [
                item[2] for item in atoms if len(item) >= 3 and item[:2] == ("fp_text", "reference")
            ]
        if not references or not references[0]:
            continue
        reference = references[0]
        issue: str | None = None
        if len(references) != 1:
            issue = "Footprint has multiple reference fields"
        positions = [item for item in atoms if item[:1] == ("at",)]
        layers = [item for item in atoms if item[:1] == ("layer",)]
        x_mm: float | None = None
        y_mm: float | None = None
        side: Literal["F.Cu", "B.Cu"] | None = None
        if len(positions) != 1 or len(positions[0]) not in {3, 4}:
            issue = "Footprint has no unique position"
        else:
            try:
                x_mm, y_mm = float(positions[0][1]), float(positions[0][2])
            except ValueError:
                issue = "Footprint position is not numeric"
            else:
                if not math.isfinite(x_mm) or not math.isfinite(y_mm):
                    issue = "Footprint position is not finite"
        if len(layers) != 1 or len(layers[0]) != 2 or layers[0][1] not in {"F.Cu", "B.Cu"}:
            issue = "Footprint side is unsupported"
        else:
            side = layers[0][1]  # pyright: ignore[reportAssignmentType]
        found[reference.casefold()].append(
            BoardFootprintAnchor(reference, footprint, x_mm, y_mm, side, issue)
        )
    return MappingProxyType({key: tuple(values) for key, values in found.items()})


def resolve_cross_probe_board_markers(
    *,
    board_path: RepositoryPath,
    board_source_sha256: Digest | None,
    board_source: bytes | None,
    findings_view_path: RepositoryPath,
    findings_view_sha256: Digest,
    drawings: tuple[ReviewDrawing, ...],
) -> CrossProbeBoardMarkerResolution:
    """Capture source-bound board anchors and preserve PCB drawing cardinality."""
    if board_source is None:
        if board_source_sha256 is not None:
            raise ValueError("Unavailable PCB source cannot have a source hash")
        anchors: BoardFootprintAnchorsByCasefoldedReference = {}
        board_status: Literal["COMPLETE", "BLOCKED"] = "BLOCKED"
        issues = ("PCB source is unavailable.",)
    else:
        if board_source_sha256 is None:
            raise ValueError("PCB source bytes require their admitted source hash")
        if hashlib.sha256(board_source).hexdigest() != board_source_sha256:
            raise ValueError("PCB source bytes do not match their admitted source hash")
        anchors = board_footprint_anchors(board_source)
        board_status = "COMPLETE"
        issues = ()
    pcb_drawings = tuple(drawing for drawing in drawings if drawing.kind == "pcb")
    if not pcb_drawings:
        drawing_status: BoardMarkerDrawingStatus = "UNAVAILABLE"
        board_drawing = None
    elif len(pcb_drawings) > 1:
        drawing_status = "AMBIGUOUS"
        board_drawing = None
    else:
        board_drawing = next(iter(pcb_drawings))
        drawing_status = "UNIQUE" if board_drawing.mapping_supported else "UNSUPPORTED"
    return CrossProbeBoardMarkerResolution(
        board_path=board_path,
        board_source_sha256=board_source_sha256,
        board_status=board_status,
        anchors_by_casefolded_reference=anchors,
        findings_view_path=findings_view_path,
        findings_view_sha256=findings_view_sha256,
        drawing_candidates=pcb_drawings,
        drawing_status=drawing_status,
        board_drawing=board_drawing,
        issues=issues,
    )
