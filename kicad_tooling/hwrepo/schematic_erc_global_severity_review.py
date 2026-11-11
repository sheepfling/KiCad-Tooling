"""Source-bound review of globally ignored schematic ERC rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    ERC_DEFAULT_IGNORED_RULE_KEYS,
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
)
from .schematic_erc_project_settings_evidence import (
    read_source_bound_schematic_erc_settings,
    verify_source_bound_schematic_erc_settings_unchanged,
)
from .source_state_models import SourceHashInventory

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")
_RULE_ID: DesignLintRuleId = "schematic.erc_rule_ignored"
_SUPPORTED_PROJECT_KINDS = frozenset(
    {
        ProjectKind.PCB,
        ProjectKind.SCHEMATIC,
        ProjectKind.SYSTEM_WIRING,
        ProjectKind.HARNESS_INTERFACE,
    }
)


@dataclass(frozen=True, slots=True)
class SchematicErcIgnoredRuleEvidence:
    """One explicit non-default ERC ignore bound to exact project settings."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_rule: SchematicErcRuleSeverity

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Ignored schematic ERC rules require a schematic-capable project")
        if _SUPPORTED_KICAD_VERSION.fullmatch(self.kicad_version) is None:
            raise ValueError("Ignored schematic ERC rules require KiCad 10.0.x")
        if self.configured_rule.severity != "ignore":
            raise ValueError("Schematic ERC ignored-rule evidence must have Ignore severity")
        if self.configured_rule.rule_key in ERC_DEFAULT_IGNORED_RULE_KEYS:
            raise ValueError("KiCad default-ignore ERC rules are not review candidates")


def project_schematic_erc_ignored_rule_evidence(
    source: SchematicErcIgnoredRuleEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact ignored rule and source identity into report evidence."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "erc_rule_key": (source.configured_rule.rule_key,),
            "configured_severity": (source.configured_rule.severity,),
        },
    )


def _candidate_subject(source: SchematicErcIgnoredRuleEvidence) -> str:
    return f"{source.source_path}#erc/rule_severities/{source.configured_rule.rule_key}"


def _candidate_message(source: SchematicErcIgnoredRuleEvidence) -> str:
    return (
        f"Schematic ERC rule {source.configured_rule.rule_key!r} is configured as Ignore; "
        "confirm that suppressing this check is intentional."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcIgnoredRuleCandidate(Candidate):
    """A review candidate whose public fields derive from typed settings evidence."""

    source_evidence: SchematicErcIgnoredRuleEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcIgnoredRuleEvidence,
    ) -> SchematicErcIgnoredRuleCandidate:
        projection = project_schematic_erc_ignored_rule_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_ignored_rule_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC severity candidate fields must match source evidence")


def source_bound_schematic_erc_ignored_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review explicit KiCad 10.0.x ERC ignores other than documented defaults."""
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
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC rule severities: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)

    return tuple(
        SchematicErcIgnoredRuleCandidate.from_source_evidence(
            SchematicErcIgnoredRuleEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                configured_rule=rule,
            )
        )
        for rule in configured_rules
        if rule.severity == "ignore" and rule.rule_key not in ERC_DEFAULT_IGNORED_RULE_KEYS
    )
