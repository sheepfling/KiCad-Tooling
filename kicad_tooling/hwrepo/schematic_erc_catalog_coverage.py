"""Report explicit ERC overrides outside the audited KiCad rule catalog."""

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

_RULE_ID: DesignLintRuleId = "schematic.erc_catalog_unverified"


@dataclass(frozen=True, slots=True)
class SchematicErcCatalogCoverageEvidence:
    """Exact saved ERC overrides whose KiCad patch catalog is not audited."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_rules: tuple[SchematicErcRuleSeverity, ...]

    def __post_init__(self) -> None:
        if self.project_kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
            raise ValueError("ERC catalog coverage requires a schematic-capable project")
        if self.kicad_version in ERC_RULE_KEYS_BY_KICAD_VERSION:
            raise ValueError("Audited KiCad patches do not have an ERC catalog coverage gap")
        if not self.configured_rules:
            raise ValueError("ERC catalog coverage evidence requires explicit severity overrides")
        if self.configured_rules != tuple(
            sorted(self.configured_rules, key=lambda item: item.rule_key)
        ):
            raise ValueError("ERC catalog coverage overrides must be in stable key order")


def project_schematic_erc_catalog_coverage_evidence(
    source: SchematicErcCatalogCoverageEvidence,
) -> CandidateEvidenceProjection:
    """Project the source identity and all explicit overrides into report evidence."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "erc_rule_key": tuple(item.rule_key for item in source.configured_rules),
            "configured_severity": tuple(item.severity for item in source.configured_rules),
        },
    )


def _candidate_subject(source: SchematicErcCatalogCoverageEvidence) -> str:
    return f"{source.source_path}#erc/rule_severities/catalog"


def _candidate_message(source: SchematicErcCatalogCoverageEvidence) -> str:
    keys = ", ".join(item.rule_key for item in source.configured_rules)
    return (
        f"KiCad {source.kicad_version} has no audited ERC rule catalog in this tooling; "
        f"the saved severity overrides ({keys}) could not be checked against native rule "
        "names or defaults. Review the exact release's ERC behavior before relying on them."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcCatalogCoverageCandidate(Candidate):
    """A review candidate whose fields are derived from source-bound settings."""

    source_evidence: SchematicErcCatalogCoverageEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcCatalogCoverageEvidence,
    ) -> SchematicErcCatalogCoverageCandidate:
        projection = project_schematic_erc_catalog_coverage_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_catalog_coverage_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC catalog coverage fields must match source evidence")


def source_bound_schematic_erc_catalog_coverage_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review explicit ERC settings when no exact KiCad patch catalog is audited."""
    if config.kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version in ERC_RULE_KEYS_BY_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_schematic_erc_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        configured_rules = configured_schematic_erc_rule_severities(
            source.document,
            allow_unrecognized_severity_strings=True,
            skip_nonstring_values=True,
            allow_duplicate_severity_keys=True,
            allow_duplicate_board_section=config.kicad_version == "10.0.8",
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read ERC catalog coverage settings: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)
    if not configured_rules:
        return ()

    evidence = SchematicErcCatalogCoverageEvidence(
        source_path=source.source_path,
        source_sha256=source.source_sha256,
        kicad_version=config.kicad_version,
        project_kind=config.kind,
        configured_rules=configured_rules,
    )
    return (SchematicErcCatalogCoverageCandidate.from_source_evidence(evidence),)
