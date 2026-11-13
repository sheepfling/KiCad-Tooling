"""Review source-bound custom DRC disallow constraints with no object types."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_empty_disallow_evidence import (
    PcbDruEmptyDisallowCandidate,
    PcbDruEmptyDisallowFindingEvidence,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_rule_declarations
from .pcb_dru_constraint_type_registry import supports_kicad_10_0_constraint_registry
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def empty_custom_drc_disallow_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruEmptyDisallowCandidate, ...]:
    """Review literal ``disallow`` clauses that name zero object types."""
    if not (
        is_supported_pcb_dru_kicad_version(config.kicad_version)
        and supports_kicad_10_0_constraint_registry(config.kicad_version)
    ):
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

    candidates: list[PcbDruEmptyDisallowCandidate] = []
    for rule in rules:
        clauses = zip(
            rule.constraint_types,
            rule.constraint_disallow_object_types,
            strict=True,
        )
        for constraint_ordinal, (constraint_type, object_types) in enumerate(clauses, start=1):
            if constraint_type != "disallow" or object_types is None or object_types:
                continue
            source_evidence = PcbDruEmptyDisallowFindingEvidence(
                source_file=source_file,
                rule_name=rule.name,
                rule_ordinal=rule.ordinal,
                constraint_ordinal=constraint_ordinal,
            )
            candidates.append(
                PcbDruEmptyDisallowCandidate.from_source_evidence(
                    source_evidence,
                    message=(
                        f"Custom DRC rule {rule.name!r} has a disallow constraint with no "
                        "object types. KiCad documents one or more object types for this "
                        "constraint; review whether an operand was omitted. This source "
                        "review does not establish a board defect."
                    ),
                )
            )
    return tuple(candidates)
