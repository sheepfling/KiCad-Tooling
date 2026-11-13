"""Review source-bound custom DRC rules with malformed condition clauses."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_malformed_condition_evidence import (
    PcbDruMalformedConditionCandidate,
    PcbDruMalformedConditionFindingEvidence,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_rule_declarations
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def custom_drc_malformed_condition_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruMalformedConditionCandidate, ...]:
    """Review single direct condition clauses whose source shape is malformed."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()

    source = source_file.local_path.read_text(encoding="utf-8")
    if "${" in source:
        return ()
    rules = native_rule_declarations(source)
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")

    candidates: list[PcbDruMalformedConditionCandidate] = []
    for rule in rules:
        if rule.condition_issue is None:
            continue
        source_evidence = PcbDruMalformedConditionFindingEvidence(
            source_file=source_file,
            rule_name=rule.name,
            rule_ordinal=rule.ordinal,
            condition_issue=rule.condition_issue,
        )
        candidates.append(
            PcbDruMalformedConditionCandidate.from_source_evidence(
                source_evidence,
                message=(
                    f"Custom DRC rule {rule.name!r} has a malformed direct condition "
                    f"clause: {rule.condition_issue} Review the saved rule and exact "
                    "native DRC behavior; this prompt does not establish a board defect."
                ),
            )
        )
    return tuple(candidates)
