"""Source-bound review of non-string values in saved schematic ERC severities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .json_value_support import json_value_type_name
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS,
    SchematicErcRuleSeveritySetting,
    configured_schematic_erc_rule_severity_settings,
)
from .schematic_erc_project_settings_evidence import (
    read_source_bound_schematic_erc_settings,
    verify_source_bound_schematic_erc_settings_unchanged,
)
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.erc_nonstring_severity_value"
_SUPPORTED_KICAD_VERSION = "10.0.8"


@dataclass(frozen=True, slots=True)
class SchematicErcNonStringSeverityValueEvidence:
    """One saved ERC severity-map entry whose JSON value is not a string."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_setting: SchematicErcRuleSeveritySetting

    def __post_init__(self) -> None:
        if self.project_kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
            raise ValueError("Non-string ERC severities require a schematic-capable project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Non-string ERC severities require audited KiCad 10.0.8 behavior")
        value = json.loads(self.configured_setting.configured_value_json)
        if isinstance(value, str):
            raise TypeError("String ERC severity values are not non-string candidates")


def project_schematic_erc_nonstring_severity_value_evidence(
    source: SchematicErcNonStringSeverityValueEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity, JSON type, and canonical saved value."""
    value = json.loads(source.configured_setting.configured_value_json)
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "erc_rule_key": (source.configured_setting.rule_key,),
            "configured_value_type": (json_value_type_name(value),),
            "configured_value_json": (source.configured_setting.configured_value_json,),
        },
    )


def _candidate_subject(source: SchematicErcNonStringSeverityValueEvidence) -> str:
    return f"{source.source_path}#erc/rule_severities/{source.configured_setting.rule_key}"


def _candidate_message(source: SchematicErcNonStringSeverityValueEvidence) -> str:
    value = json.loads(source.configured_setting.configured_value_json)
    return (
        f"KiCad {source.kicad_version} ERC severity key "
        f"{source.configured_setting.rule_key!r} has a JSON {json_value_type_name(value)} value, "
        "not a severity string; review the saved setting."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcNonStringSeverityValueCandidate(Candidate):
    """A candidate whose public fields derive from source-bound settings."""

    source_evidence: SchematicErcNonStringSeverityValueEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcNonStringSeverityValueEvidence,
    ) -> SchematicErcNonStringSeverityValueCandidate:
        projection = project_schematic_erc_nonstring_severity_value_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_nonstring_severity_value_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC non-string fields must match source evidence")


def source_bound_schematic_erc_nonstring_severity_value_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review every non-string severity-map value for exact KiCad 10.0.8 projects."""
    if config.kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_schematic_erc_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        configured_settings = configured_schematic_erc_rule_severity_settings(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC severity settings: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)

    candidates: list[Candidate] = []
    for setting in configured_settings:
        value = json.loads(setting.configured_value_json)
        if isinstance(value, str):
            continue
        candidates.append(
            SchematicErcNonStringSeverityValueCandidate.from_source_evidence(
                SchematicErcNonStringSeverityValueEvidence(
                    source_path=source.source_path,
                    source_sha256=source.source_sha256,
                    kicad_version=config.kicad_version,
                    project_kind=config.kind,
                    configured_setting=setting,
                )
            )
        )
    return tuple(candidates)
