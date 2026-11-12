"""Source-bound structural identity checks for KiCad PCB objects."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from uuid import UUID

from .contracts import read_regular_bytes, repo_path
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .evidence import digest, digest_bytes
from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children, sexpr_root
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.duplicate_object_uuid"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})
_MAX_BOARD_SOURCE_BYTES = 128 * 1024 * 1024


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

    project_relative = Path(str(config.project)).as_posix()
    board_relative = Path(project_relative).with_suffix(".kicad_pcb").as_posix()
    expected_hash = source_hashes.get(board_relative)
    if expected_hash is None:
        return ()

    board_path = repo_path(root, board_relative)
    source, _state = read_regular_bytes(board_path, maximum=_MAX_BOARD_SOURCE_BYTES)
    source_sha256 = digest_bytes(source)
    if source_sha256 != expected_hash:
        raise ValueError(f"PCB source differs from the source-bound hashes: {board_relative}")
    try:
        document = source.decode("utf-8")
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
                    canonical_uuid = _canonical_uuid(atoms[1])
                    if canonical_uuid is not None:
                        line = bisect_right(line_breaks, child.start) + 1
                        occurrences[canonical_uuid].append((line, parent_kind, atoms[0]))
                continue
            pending.append((child, atoms[0]))

    if digest(board_path) != source_sha256:
        raise ValueError(f"PCB source changed while scanning: {board_relative}")

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
                subject=f"{board_relative}:{first_line}:{object_uuid}",
                message=(
                    f"PCB object identity {object_uuid!r} is assigned to {len(entries)} objects "
                    f"on lines {', '.join(lines)}; review the source identities because "
                    "native diagnostics can refer to distinct objects by the same UUID."
                ),
                evidence={
                    "source_path": (board_relative,),
                    "source_sha256": (source_sha256,),
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


def _canonical_uuid(value: str) -> str | None:
    """Accept only canonical hyphenated UUID text, normalizing hex case."""
    try:
        parsed = str(UUID(value))
    except (AttributeError, ValueError):
        return None
    return parsed if parsed == value.lower() else None
