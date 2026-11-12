"""Source-bound review of malformed PCB netclass inventory shapes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_malformed_netclass_inventory import (
    PcbMalformedNetClassInventory,
    configured_pcb_malformed_netclass_inventory,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_malformed_netclass_inventory"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassInventoryEvidence:
    """Malformed class inventory tied to exact KiCad project settings bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    inventory: PcbMalformedNetClassInventory

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Malformed netclass inventory evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Malformed netclass inventory evidence requires KiCad 10.0.8")


def project_pcb_malformed_netclass_inventory_evidence(
    source: PcbMalformedNetClassInventoryEvidence,
) -> CandidateEvidenceProjection:
    """Project the source digest and malformed inventory location/type."""
    evidence: dict[str, tuple[str, ...]] = {
        "source_path": (source.source_path,),
        "source_sha256": (source.source_sha256,),
        "kicad_version": (source.kicad_version,),
        "project_kind": (source.project_kind.value,),
        "location": (source.inventory.location,),
        "problem": (source.inventory.problem,),
        "observed_json_type": (source.inventory.observed_json_type,),
    }
    if source.inventory.entry_index is not None:
        evidence["entry_index"] = (str(source.inventory.entry_index),)
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


def _subject(source: PcbMalformedNetClassInventoryEvidence) -> str:
    return f"{source.source_path}#{source.inventory.location}"


def _message(source: PcbMalformedNetClassInventoryEvidence) -> str:
    inventory = source.inventory
    if inventory.problem == "classes_not_array":
        detail = f"net_settings.classes is JSON {inventory.observed_json_type}"
    elif inventory.problem == "entry_not_object":
        detail = (
            f"net_settings.classes[{inventory.entry_index}] is JSON {inventory.observed_json_type}"
        )
    else:
        detail = f"net_settings.classes[{inventory.entry_index}] has no name member"
    return (
        f"KiCad {source.kicad_version} does not load this netclass inventory shape: "
        f"{detail}; review the class definitions and assignments."
    )


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassInventoryCandidate(Candidate):
    """Review candidate from a malformed, source-bound class inventory."""

    source_evidence: PcbMalformedNetClassInventoryEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbMalformedNetClassInventoryEvidence,
    ) -> PcbMalformedNetClassInventoryCandidate:
        projection = project_pcb_malformed_netclass_inventory_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_malformed_netclass_inventory_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Malformed inventory candidate must match source evidence")


def source_bound_pcb_malformed_netclass_inventory_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review unloaded PCB netclass definitions for exact KiCad 10.0.8 projects."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        inventory_items = configured_pcb_malformed_netclass_inventory(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbMalformedNetClassInventoryCandidate.from_source_evidence(
            PcbMalformedNetClassInventoryEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                inventory=inventory,
            )
        )
        for inventory in inventory_items
    )
