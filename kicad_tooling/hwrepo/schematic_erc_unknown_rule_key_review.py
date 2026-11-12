"""Source-bound review of ERC severity keys unknown to the configured KiCad release."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    ERC_RULE_KEYS_BY_KICAD_VERSION,
    SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS,
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
)
from .schematic_erc_project_settings_evidence import (
    read_source_bound_schematic_erc_settings,
    verify_source_bound_schematic_erc_settings_unchanged,
)
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.erc_unknown_rule_key"


@dataclass(frozen=True, slots=True)
class SchematicErcUnknownRuleKeyEvidence:
    """One saved severity entry absent from the exact KiCad rule-key catalog."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_rule: SchematicErcRuleSeverity

    def __post_init__(self) -> None:
        if self.project_kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
            raise ValueError("Unknown schematic ERC keys require a schematic-capable project")
        recognized_keys = ERC_RULE_KEYS_BY_KICAD_VERSION.get(self.kicad_version)
        if recognized_keys is None:
            raise ValueError("Unknown schematic ERC keys require an audited KiCad 10.0 patch")
        if self.configured_rule.rule_key in recognized_keys:
            raise ValueError("Known schematic ERC keys are not review candidates")


def project_schematic_erc_unknown_rule_key_evidence(
    source: SchematicErcUnknownRuleKeyEvidence,
) -> CandidateEvidenceProjection:
    """Project exact source identity and configured unknown key into report evidence."""
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


def _candidate_subject(source: SchematicErcUnknownRuleKeyEvidence) -> str:
    return f"{source.source_path}#erc/rule_severities/{source.configured_rule.rule_key}"


def _candidate_message(source: SchematicErcUnknownRuleKeyEvidence) -> str:
    return (
        f"KiCad {source.kicad_version} does not recognize ERC severity key "
        f"{source.configured_rule.rule_key!r}; check for a typo or version mismatch because "
        "the configured severity may not affect native ERC."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcUnknownRuleKeyCandidate(Candidate):
    """A candidate whose public fields derive from source-bound settings."""

    source_evidence: SchematicErcUnknownRuleKeyEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcUnknownRuleKeyEvidence,
    ) -> SchematicErcUnknownRuleKeyCandidate:
        projection = project_schematic_erc_unknown_rule_key_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_unknown_rule_key_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC unknown-key fields must match source evidence")


def source_bound_schematic_erc_unknown_rule_key_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review configured ERC keys absent from an exact, audited KiCad 10.0 catalog."""
    if config.kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
        return ()
    recognized_keys = ERC_RULE_KEYS_BY_KICAD_VERSION.get(config.kicad_version)
    if recognized_keys is None:
        return ()

    relative = str(config.project)
    source = read_source_bound_schematic_erc_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        configured_rules = configured_schematic_erc_rule_severities(
            source.document, allow_unrecognized_severity_strings=True
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC rule severities: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)

    return tuple(
        SchematicErcUnknownRuleKeyCandidate.from_source_evidence(
            SchematicErcUnknownRuleKeyEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                configured_rule=rule,
            )
        )
        for rule in configured_rules
        if rule.rule_key not in recognized_keys
    )
