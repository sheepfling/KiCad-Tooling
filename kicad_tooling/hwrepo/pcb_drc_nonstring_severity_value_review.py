"""Source-bound review of non-string PCB DRC severity settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .json_value_support import json_value_type_name
from .pcb_drc_project_settings import (
    PcbDrcRuleSeveritySetting,
    configured_pcb_drc_rule_severity_settings,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .pcb_drc_severity_key_catalog import PCB_DRC_STRING_RULE_SEVERITY_KEYS_BY_KICAD_VERSION
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_nonstring_severity_value"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbDrcNonStringSeverityValueEvidence:
    """One recognized DRC severity key configured with a non-string JSON value."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_setting: PcbDrcRuleSeveritySetting

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Non-string PCB DRC severity values require a PCB-capable project")
        string_keys = PCB_DRC_STRING_RULE_SEVERITY_KEYS_BY_KICAD_VERSION.get(self.kicad_version)
        if string_keys is None:
            raise ValueError(
                "Non-string PCB DRC severity values require an audited exact KiCad version"
            )
        if self.configured_setting.check_id not in string_keys:
            raise ValueError("Unknown or non-string PCB DRC settings are not candidates")
        value = json.loads(self.configured_setting.configured_value_json)
        if isinstance(value, str):
            raise TypeError("String PCB DRC severity values are not non-string candidates")


def project_pcb_drc_nonstring_severity_value_evidence(
    source: PcbDrcNonStringSeverityValueEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity, key, JSON type, and saved value."""
    value = json.loads(source.configured_setting.configured_value_json)
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "drc_severity_key": (source.configured_setting.check_id,),
            "configured_value_type": (json_value_type_name(value),),
            "configured_value_json": (source.configured_setting.configured_value_json,),
        },
    )


def _candidate_subject(source: PcbDrcNonStringSeverityValueEvidence) -> str:
    return (
        f"{source.source_path}#board/design_settings/rule_severities/"
        f"{source.configured_setting.check_id}"
    )


def _candidate_message(source: PcbDrcNonStringSeverityValueEvidence) -> str:
    value = json.loads(source.configured_setting.configured_value_json)
    return (
        f"KiCad {source.kicad_version} DRC severity key "
        f"{source.configured_setting.check_id!r} has a JSON {json_value_type_name(value)} value, "
        "not a severity string; review the saved setting."
    )


@dataclass(frozen=True, slots=True)
class PcbDrcNonStringSeverityValueCandidate(Candidate):
    """A candidate whose public fields derive from source-bound settings."""

    source_evidence: PcbDrcNonStringSeverityValueEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDrcNonStringSeverityValueEvidence,
    ) -> PcbDrcNonStringSeverityValueCandidate:
        projection = project_pcb_drc_nonstring_severity_value_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_nonstring_severity_value_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("PCB DRC non-string-severity fields must match source evidence")


def source_bound_pcb_drc_nonstring_severity_value_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review non-string values on known PCB DRC severity keys for KiCad 10.0.8."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    string_keys = PCB_DRC_STRING_RULE_SEVERITY_KEYS_BY_KICAD_VERSION.get(config.kicad_version)
    if string_keys is None:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        configured_settings = configured_pcb_drc_rule_severity_settings(
            source.document,
            allow_duplicate_erc_severity_keys=True,
            allow_duplicate_drc_severity_keys=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    candidates: list[Candidate] = []
    for setting in configured_settings:
        if setting.check_id not in string_keys:
            continue
        value = json.loads(setting.configured_value_json)
        if isinstance(value, str):
            continue
        evidence = PcbDrcNonStringSeverityValueEvidence(
            source_path=source.source_path,
            source_sha256=source.source_sha256,
            kicad_version=config.kicad_version,
            project_kind=config.kind,
            configured_setting=setting,
        )
        candidates.append(PcbDrcNonStringSeverityValueCandidate.from_source_evidence(evidence))
    return tuple(candidates)
