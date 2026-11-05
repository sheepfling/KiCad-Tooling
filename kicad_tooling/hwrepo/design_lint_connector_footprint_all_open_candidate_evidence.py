"""Typed report projections for named connector contacts open across aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinNamedAllOpen,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorFootprintAllOpenKind: TypeAlias = Literal["power_input", "power_output", "signal"]

_RULE_IDS: dict[ConnectorFootprintAllOpenKind, DesignLintRuleId] = {
    "power_input": "connector.footprint_named_power_input_all_open",
    "power_output": "connector.footprint_named_power_output_all_open",
    "signal": "connector.footprint_named_signal_all_open",
}


@dataclass(frozen=True, slots=True)
class ConnectorFootprintAllOpenEvidence:
    """One named all-open record retained inside its source peer scan."""

    scan: ConnectorFootprintPeerPinScan
    item: ConnectorFootprintPeerPinNamedAllOpen
    kind: ConnectorFootprintAllOpenKind

    def __post_init__(self) -> None:
        if self.item not in self.scan.named_all_open:
            raise ValueError("Named all-open evidence must belong to its current peer scan")
        if (
            not self.item.common_anchor_pin_numbers
            or len(self.item.assignments) < 2
            or any(self.item.assignments.values())
        ):
            raise ValueError("Named all-open evidence requires an anchored open peer group")
        if pin_function_is_generic(self.item.pin_function):
            raise ValueError("Named all-open evidence requires a specific native function")
        if is_named_supply_function(self.item.pin_function) or is_return_function(
            self.item.pin_function
        ):
            raise ValueError("Named all-open evidence cannot classify supply or return pins")
        electrical_type = self.item.pin_electrical_type.strip().casefold()
        if self.kind == "power_input" and electrical_type != "power_in":
            raise ValueError("Power-input evidence requires a native power_in pin")
        if self.kind == "power_output" and electrical_type != "power_out":
            raise ValueError("Power-output evidence requires a native power_out pin")
        if self.kind == "signal" and electrical_type not in SIGNAL_ELECTRICAL_TYPES:
            raise ValueError("Signal evidence requires a supported native signal pin type")
        if self.item.peer_assignment_group is None and self.item.peer_assignment_basis:
            raise ValueError("Unscoped peer evidence cannot retain a review basis")
        if self.item.peer_assignment_group is not None and not self.item.peer_assignment_basis:
            raise ValueError("Scoped peer evidence requires its review basis")


def project_connector_footprint_all_open_evidence(
    source: ConnectorFootprintAllOpenEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed scan record into the existing serialized evidence fields."""
    source.__post_init__()
    item = source.item
    evidence: dict[str, tuple[str, ...]] = {
        "value": (item.value,),
        "footprint": (item.footprint,),
        "pin_number": (item.pin_number,),
        "pin_function": (item.pin_function,),
        "pin_electrical_type": (item.pin_electrical_type.strip().casefold(),),
        "assignments": tuple(f"{pin}=<unassigned>" for pin in item.assignments),
        "open_pins": tuple(item.assignments),
        "symbols": item.symbols,
        "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
    }
    if item.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (item.peer_assignment_group,)
        evidence["peer_assignment_basis"] = item.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=_RULE_IDS[source.kind], evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorFootprintAllOpenCandidate(Candidate):
    """Candidate projected from one named all-open source scan record."""

    source_evidence: ConnectorFootprintAllOpenEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintAllOpenEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorFootprintAllOpenCandidate:
        projection = project_connector_footprint_all_open_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_footprint_all_open_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Footprint all-open fields must match their typed source projection")
