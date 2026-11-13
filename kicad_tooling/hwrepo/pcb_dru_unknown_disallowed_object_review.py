"""Review unknown object types in source-bound custom DRC disallow clauses."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_pcb_dru_unknown_disallowed_object_evidence import (
    PcbDruUnknownDisallowedObjectCandidate,
    PcbDruUnknownDisallowedObjectFindingEvidence,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_rule_declarations
from .pcb_dru_constraint_type_registry import (
    KICAD_10_0_CUSTOM_DRC_DISALLOW_OBJECT_TYPES,
    supports_kicad_10_0_constraint_registry,
)
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def unknown_custom_drc_disallowed_object_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruUnknownDisallowedObjectCandidate, ...]:
    """Review literal disallow operands outside the KiCad 10.0 vocabulary."""
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

    candidates: list[PcbDruUnknownDisallowedObjectCandidate] = []
    for rule in rules:
        for constraint_ordinal, object_types in enumerate(
            rule.constraint_disallow_object_types, start=1
        ):
            if object_types is None:
                continue
            for object_ordinal, object_type in enumerate(object_types, start=1):
                if object_type in KICAD_10_0_CUSTOM_DRC_DISALLOW_OBJECT_TYPES:
                    continue
                source_evidence = PcbDruUnknownDisallowedObjectFindingEvidence(
                    source_file=source_file,
                    rule_name=rule.name,
                    rule_ordinal=rule.ordinal,
                    constraint_ordinal=constraint_ordinal,
                    object_ordinal=object_ordinal,
                    object_type=object_type,
                )
                candidates.append(
                    PcbDruUnknownDisallowedObjectCandidate.from_source_evidence(
                        source_evidence,
                        message=(
                            f"Custom DRC rule {rule.name!r} disallows object type "
                            f"{object_type!r}, which is not in KiCad 10.0's documented "
                            "disallow vocabulary. KiCad may silently skip this operand; "
                            "verify its spelling and intended object type. This prompt "
                            "does not establish a board defect."
                        ),
                    )
                )
    return tuple(candidates)
