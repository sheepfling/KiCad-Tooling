"""Source-bound review of ERC checks changed from Error to Warning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    ERC_DEFAULT_ERROR_RULE_KEYS,
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
)
from .schematic_erc_project_settings_evidence import (
    read_source_bound_schematic_erc_settings,
    verify_source_bound_schematic_erc_settings_unchanged,
)
from .source_state_models import SourceHashInventory

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")
_RULE_ID: DesignLintRuleId = "schematic.erc_error_downgraded"
_SUPPORTED_PROJECT_KINDS = frozenset(
    {
        ProjectKind.PCB,
        ProjectKind.SCHEMATIC,
        ProjectKind.SYSTEM_WIRING,
        ProjectKind.HARNESS_INTERFACE,
    }
)


@dataclass(frozen=True, slots=True)
class SchematicErcWarningDowngradeEvidence:
    """One Error-default ERC key explicitly set to Warning in saved settings."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_rule: SchematicErcRuleSeverity

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("ERC severity downgrade evidence requires a schematic-capable project")
        if _SUPPORTED_KICAD_VERSION.fullmatch(self.kicad_version) is None:
            raise ValueError("ERC severity downgrade evidence requires KiCad 10.0.x")
        if self.configured_rule.rule_key not in ERC_DEFAULT_ERROR_RULE_KEYS:
            raise ValueError("ERC downgrade evidence must name a known Error-default rule")
        if self.configured_rule.severity != "warning":
            raise ValueError("ERC downgrade evidence must have Warning severity")


def project_schematic_erc_warning_downgrade_evidence(
    source: SchematicErcWarningDowngradeEvidence,
) -> CandidateEvidenceProjection:
    """Project the key's exact settings and default severity into report evidence."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "erc_rule_key": (source.configured_rule.rule_key,),
            "configured_severity": (source.configured_rule.severity,),
            "default_severity": ("error",),
        },
    )


def _candidate_subject(source: SchematicErcWarningDowngradeEvidence) -> str:
    return f"{source.source_path}#erc/rule_severities/{source.configured_rule.rule_key}"


def _candidate_message(source: SchematicErcWarningDowngradeEvidence) -> str:
    return (
        f"Schematic ERC rule {source.configured_rule.rule_key!r} has changed from its "
        "KiCad Error default to Warning; confirm that this reduction is intentional."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcWarningDowngradeCandidate(Candidate):
    """A review candidate whose public fields derive from settings evidence."""

    source_evidence: SchematicErcWarningDowngradeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcWarningDowngradeEvidence,
    ) -> SchematicErcWarningDowngradeCandidate:
        projection = project_schematic_erc_warning_downgrade_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_warning_downgrade_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC downgrade candidate fields must match source evidence")


def source_bound_schematic_erc_warning_downgrade_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review explicit Warning overrides of named KiCad 10.0.x Error defaults."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if _SUPPORTED_KICAD_VERSION.fullmatch(config.kicad_version) is None:
        return ()

    relative = str(config.project)
    source = read_source_bound_schematic_erc_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        configured_rules = configured_schematic_erc_rule_severities(source.document)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC rule severities: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)

    return tuple(
        SchematicErcWarningDowngradeCandidate.from_source_evidence(
            SchematicErcWarningDowngradeEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                configured_rule=rule,
            )
        )
        for rule in configured_rules
        if rule.severity == "warning" and rule.rule_key in ERC_DEFAULT_ERROR_RULE_KEYS
    )
