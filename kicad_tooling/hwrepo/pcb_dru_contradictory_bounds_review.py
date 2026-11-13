"""Review custom PCB DRC constraints with contradictory explicit bounds."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_contradictory_bounds_evidence import (
    PcbDruContradictoryBoundsCandidate,
    PcbDruContradictoryBoundsFindingEvidence,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_constraints
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def contradictory_custom_drc_constraint_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruContradictoryBoundsCandidate, ...]:
    """Review source constraints whose positive minimum exceeds their maximum."""
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

    candidates: list[PcbDruContradictoryBoundsCandidate] = []
    for constraint in constraints:
        if (
            constraint.issue is not None
            or constraint.minimum_nm is None
            or constraint.maximum_nm is None
            or constraint.minimum_nm <= constraint.maximum_nm
        ):
            continue
        source_evidence = PcbDruContradictoryBoundsFindingEvidence(
            source_file=source_file,
            rule_name=constraint.rule_name,
            rule_ordinal=constraint.ordinal,
            constraint_name=constraint.name,
            minimum_nm=constraint.minimum_nm,
            maximum_nm=constraint.maximum_nm,
        )
        candidates.append(
            PcbDruContradictoryBoundsCandidate.from_source_evidence(
                source_evidence,
                message=(
                    f"Custom DRC rule {constraint.rule_name!r} sets {constraint.name} minimum "
                    f"({constraint.minimum_nm} nm) above its maximum "
                    f"({constraint.maximum_nm} nm); review the rule's intended bounds. "
                    "This source review does not establish a board defect."
                ),
            )
        )
    return tuple(candidates)
