"""Typed source records and stable evidence projections for open connector pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .connector_return_pins import (
    UnconnectedGenericPowerInputConnectorPin,
    UnconnectedGenericPowerOutputConnectorPin,
    UnconnectedNamedConnectorPin,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

UnconnectedConnectorPinEvidence: TypeAlias = (
    UnconnectedNamedConnectorPin
    | UnconnectedGenericPowerInputConnectorPin
    | UnconnectedGenericPowerOutputConnectorPin
)


def project_unconnected_connector_pin_evidence(
    source: UnconnectedConnectorPinEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed connector-pin observation into its established report fields."""
    if isinstance(source, UnconnectedNamedConnectorPin):
        if source.category == "supply":
            rule_id = "connector.unconnected_supply_pin"
        elif source.category == "return":
            rule_id = "connector.unconnected_return_pin"
        else:
            raise ValueError("Named connector pin evidence requires a supply or return category")
        if source.role_source == "native_symbol":
            evidence = {source.pin: ()}
        elif source.role_source == "project_interface":
            evidence = {
                source.pin: (),
                "role_source": ("project interface catalog",),
            }
        else:
            raise ValueError("Named connector pin evidence has an unsupported role source")
        return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)

    if isinstance(source, UnconnectedGenericPowerInputConnectorPin):
        if source.electrical_type != "power_in":
            raise ValueError("Generic connector input evidence requires the power_in role")
        rule_id = "connector.unconnected_power_input"
    else:
        if source.electrical_type != "power_out":
            raise ValueError("Generic connector output evidence requires the power_out role")
        rule_id = "connector.unconnected_power_output"

    evidence = {
        "symbol": (source.symbol,),
        "pin_electrical_type": (source.electrical_type,),
        source.pin: (),
    }
    if source.function is not None:
        evidence["native_pin_function"] = (source.function,)
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UnconnectedConnectorPinCandidate(Candidate):
    """Internal connector finding retaining its exact unconnected-pin scan record."""

    source_evidence: UnconnectedConnectorPinEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UnconnectedConnectorPinEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnconnectedConnectorPinCandidate:
        projection = project_unconnected_connector_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_unconnected_connector_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Connector pin candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Connector pin evidence must match its typed source projection")
