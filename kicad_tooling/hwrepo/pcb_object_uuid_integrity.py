"""Source-bound structural identity checks for KiCad PCB objects."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children, sexpr_root
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .pcb_source_identity import canonical_pcb_uuid
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.duplicate_object_uuid"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def duplicate_pcb_object_uuid_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review repeated UUIDs in one exact, source-hashed PCB board file."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    if config.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return ()

    board = read_source_bound_pcb_board(root, config, source_hashes)
    if board is None:
        return ()
    try:
        document = board.source.decode("utf-8")
        board_root = sexpr_root(document, "kicad_pcb")
    except (UnicodeError, ValueError):
        return ()

    occurrences: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    line_breaks = tuple(index for index, character in enumerate(document) if character == "\n")
    pending: list[tuple[SExprSpan, str]] = [(board_root, "kicad_pcb")]
    while pending:
        parent, parent_kind = pending.pop()
        for child in sexpr_children(document, parent.start + 1, parent.end - 1):
            atoms = sexpr_atoms(document, child)
            if not atoms:
                continue
            if atoms[0] in {"uuid", "tstamp"}:
                if len(atoms) == 2:
                    canonical_uuid = canonical_pcb_uuid(atoms[1])
                    if canonical_uuid is not None:
                        line = bisect_right(line_breaks, child.start) + 1
                        occurrences[canonical_uuid].append((line, parent_kind, atoms[0]))
                continue
            pending.append((child, atoms[0]))

    verify_source_bound_pcb_board_unchanged(board)

    candidates: list[Candidate] = []
    for object_uuid, entries in sorted(occurrences.items()):
        if len(entries) < 2:
            continue
        ordered = tuple(sorted(entries))
        lines = tuple(str(line) for line, _kind, _field in ordered)
        kinds = tuple(kind for _line, kind, _field in ordered)
        identity_fields = tuple(field for _line, _kind, field in ordered)
        first_line = ordered[0][0]
        candidates.append(
            Candidate(
                rule_id=_RULE_ID,
                subject=f"{board.relative_path}:{first_line}:{object_uuid}",
                message=(
                    f"PCB object identity {object_uuid!r} is assigned to {len(entries)} objects "
                    f"on lines {', '.join(lines)}; review the source identities because "
                    "native diagnostics can refer to distinct objects by the same UUID."
                ),
                evidence={
                    "source_path": (board.relative_path,),
                    "source_sha256": (board.sha256,),
                    "object_uuid": (object_uuid,),
                    "occurrence_count": (str(len(entries)),),
                    "source_lines": lines,
                    "object_kinds": tuple(sorted(set(kinds))),
                    "occurrence_object_kinds": kinds,
                    "occurrence_identity_fields": identity_fields,
                },
            )
        )
    return tuple(candidates)
