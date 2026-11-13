"""Review source-bound custom DRC constraints with unparseable bounds."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_malformed_bounds_evidence import (
    PcbDruMalformedBoundsCandidate,
    PcbDruMalformedBoundsFindingEvidence,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_constraints
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def custom_drc_malformed_bound_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruMalformedBoundsCandidate, ...]:
    """Review recognized constraint clauses whose bound parser reports an issue."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()

    source = source_file.local_path.read_text(encoding="utf-8")
    if "${" in source:
        return ()
    constraints = native_constraints(source)
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")

    candidates: list[PcbDruMalformedBoundsCandidate] = []
    for constraint in constraints:
        if constraint.bounds_issue is None:
            continue
        source_evidence = PcbDruMalformedBoundsFindingEvidence(
            source_file=source_file,
            rule_name=constraint.rule_name,
            rule_ordinal=constraint.ordinal,
            constraint_name=constraint.name,
            parser_issue=constraint.bounds_issue,
        )
        candidates.append(
            PcbDruMalformedBoundsCandidate.from_source_evidence(
                source_evidence,
                message=(
                    f"Custom DRC rule {constraint.rule_name!r} has a {constraint.name} bound "
                    f"that this tooling parser cannot verify: {constraint.bounds_issue} Review "
                    "the saved constraint and exact native DRC behavior; this source prompt "
                    "does not establish a board defect."
                ),
            )
        )
    return tuple(candidates)
