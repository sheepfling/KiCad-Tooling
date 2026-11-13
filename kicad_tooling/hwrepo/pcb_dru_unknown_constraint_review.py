"""Review source-bound custom DRC constraints outside the KiCad 10.0 registry."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_pcb_dru_unknown_constraint_evidence import (
    PcbDruUnknownConstraintCandidate,
    PcbDruUnknownConstraintFindingEvidence,
)
from .evidence import digest
from .pcb_drc_rule_parser import native_rule_declarations
from .pcb_dru_constraint_type_registry import (
    KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES,
    supports_kicad_10_0_constraint_registry,
)
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def unknown_custom_drc_constraint_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruUnknownConstraintCandidate, ...]:
    """Review direct constraint names not listed for the configured KiCad 10.0.x."""
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

    candidates: list[PcbDruUnknownConstraintCandidate] = []
    for rule in rules:
        for ordinal, name in enumerate(rule.constraint_types, start=1):
            if name is None or name in KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES:
                continue
            source_evidence = PcbDruUnknownConstraintFindingEvidence(
                source_file=source_file,
                rule_name=rule.name,
                rule_ordinal=rule.ordinal,
                constraint_ordinal=ordinal,
                constraint_type=name,
            )
            candidates.append(
                PcbDruUnknownConstraintCandidate.from_source_evidence(
                    source_evidence,
                    message=(
                        f"Custom DRC rule {rule.name!r} uses constraint type {name!r}, "
                        "which is not in the KiCad 10.0 custom-rule registry. KiCad may "
                        "silently skip this clause; verify the spelling and intended "
                        "constraint. This prompt does not establish a board defect."
                    ),
                )
            )
    return tuple(candidates)
