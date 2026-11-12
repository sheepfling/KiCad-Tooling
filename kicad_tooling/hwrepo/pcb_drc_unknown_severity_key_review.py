"""Source-bound review of PCB DRC severity keys unknown to KiCad 10.0.8."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_project_settings import (
    PcbDrcRuleSeveritySetting,
    configured_pcb_drc_rule_severity_settings,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .pcb_drc_severity_key_catalog import PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_unknown_severity_key"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbDrcUnknownSeverityKeyEvidence:
    """One saved severity entry absent from the exact KiCad key catalog."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    configured_setting: PcbDrcRuleSeveritySetting

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Unknown PCB DRC keys require a PCB-capable project")
        recognized_keys = PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION.get(self.kicad_version)
        if recognized_keys is None:
            raise ValueError("Unknown PCB DRC keys require an audited exact KiCad version")
        if self.configured_setting.check_id in recognized_keys:
            raise ValueError("Known PCB DRC keys are not review candidates")


def project_pcb_drc_unknown_severity_key_evidence(
    source: PcbDrcUnknownSeverityKeyEvidence,
) -> CandidateEvidenceProjection:
    """Project exact settings identity and unknown key into report evidence."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "drc_severity_key": (source.configured_setting.check_id,),
            "configured_value_json": (source.configured_setting.configured_value_json,),
        },
    )


def _candidate_subject(source: PcbDrcUnknownSeverityKeyEvidence) -> str:
    return (
        f"{source.source_path}#board/design_settings/rule_severities/"
        f"{source.configured_setting.check_id}"
    )


def _candidate_message(source: PcbDrcUnknownSeverityKeyEvidence) -> str:
    return (
        f"KiCad {source.kicad_version} does not recognize DRC severity key "
        f"{source.configured_setting.check_id!r}; check for a typo or version mismatch "
        "because the configured setting may not affect native DRC."
    )


@dataclass(frozen=True, slots=True)
class PcbDrcUnknownSeverityKeyCandidate(Candidate):
    """A candidate whose public fields derive from source-bound settings."""

    source_evidence: PcbDrcUnknownSeverityKeyEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDrcUnknownSeverityKeyEvidence,
    ) -> PcbDrcUnknownSeverityKeyCandidate:
        projection = project_pcb_drc_unknown_severity_key_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_unknown_severity_key_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("PCB DRC unknown-key fields must match source evidence")


def source_bound_pcb_drc_unknown_severity_key_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review unknown saved DRC severity keys for exactly audited KiCad 10.0.8."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    recognized_keys = PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION.get(config.kicad_version)
    if recognized_keys is None:
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
            allow_duplicate_board_section=config.kicad_version == "10.0.8",
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbDrcUnknownSeverityKeyCandidate.from_source_evidence(
            PcbDrcUnknownSeverityKeyEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                configured_setting=setting,
            )
        )
        for setting in configured_settings
        if setting.check_id not in recognized_keys
    )
