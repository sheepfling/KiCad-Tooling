"""Source-bound review of incomplete PCB footprint schematic paths."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import (
    sexpr_atoms,
    sexpr_children,
    sexpr_nodes,
    sexpr_root,
    sexpr_tokens,
)
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .pcb_footprint_reference_inventory import pcb_footprint_reference
from .pcb_source_identity import canonical_pcb_uuid
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.footprint_path_trailing_separator"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def pcb_footprint_path_trailing_separator_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review PCB footprint paths whose final path segment is empty."""
    if config.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return ()
    board = read_source_bound_pcb_board(root, config, source_hashes)
    if board is None or config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    try:
        document = board.source.decode("utf-8")
        board_root = sexpr_root(document, "kicad_pcb")
    except (UnicodeError, ValueError):
        return ()

    line_breaks = tuple(index for index, character in enumerate(document) if character == "\n")
    candidates: list[Candidate] = []
    for footprint in sexpr_children(document, board_root.start + 1, board_root.end - 1):
        if sexpr_atoms(document, footprint)[:1] != ("footprint",):
            continue
        path_nodes = sexpr_nodes(document, footprint, "path")
        if len(path_nodes) != 1:
            continue
        path_node = path_nodes[0]
        path_atoms = sexpr_atoms(document, path_node)
        path_tokens = sexpr_tokens(document, path_node)
        if len(path_atoms) != 2 or len(path_tokens) != 2 or not path_tokens[1].quoted:
            continue
        instance_path = path_atoms[1]
        path_uuid_segments = _trailing_path_uuid_segments(instance_path)
        if path_uuid_segments is None:
            continue

        reference = pcb_footprint_reference(document, footprint) or "<no ref>"
        line = bisect_right(line_breaks, path_node.start) + 1
        candidates.append(
            Candidate(
                rule_id=_RULE_ID,
                subject=f"{board.relative_path}:{line}:{reference}:{instance_path}",
                message=(
                    f"PCB footprint {reference} has schematic instance path "
                    f"{instance_path!r} ending in an empty path segment; review its "
                    "update-from-schematic identity."
                ),
                evidence={
                    "source_path": (board.relative_path,),
                    "source_sha256": (board.sha256,),
                    "reference": (reference,),
                    "source_line": (str(line),),
                    "instance_path": (instance_path,),
                    "path_uuid_segments": path_uuid_segments,
                },
            )
        )

    verify_source_bound_pcb_board_unchanged(board)
    return tuple(sorted(candidates, key=lambda item: item.subject))


def _trailing_path_uuid_segments(instance_path: str) -> tuple[str, ...] | None:
    """Recognize a trailing separator after one or more canonical UUID segments."""
    if not instance_path.startswith("/") or not instance_path.endswith("/"):
        return None
    segments = instance_path[1:-1].split("/")
    if not segments:
        return None
    canonical = tuple(canonical_pcb_uuid(segment) for segment in segments)
    if any(value is None for value in canonical):
        return None
    return tuple(value for value in canonical if value is not None)
