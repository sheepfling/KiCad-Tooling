"""Review split named power-input assignments across connector aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_connector_footprint_named_divergence_evidence import (
    ConnectorFootprintNamedDivergenceCandidate,
    connector_footprint_named_divergence_candidate,
)

RULE_ID: Literal["connector.footprint_named_power_input_assignment_divergence"] = (
    "connector.footprint_named_power_input_assignment_divergence"
)


@dataclass(frozen=True, slots=True)
class NamedPowerInputDivergenceEvaluation:
    """Candidates and coverage counts for split named power-input contacts."""

    candidates: tuple[ConnectorFootprintNamedDivergenceCandidate, ...]
    candidate_count: int
    unanchored_count: int


def evaluate_footprint_named_power_input_assignment_divergence(
    scan: ConnectorFootprintPeerPinScan,
) -> NamedPowerInputDivergenceEvaluation:
    """Review explicit power-input contacts split across comparable connector aliases."""
    eligible = tuple(
        item
        for item in scan.named_divergences
        if item.pin_electrical_type.strip().casefold() == "power_in"
        and not pin_function_is_generic(item.pin_function)
        and not is_named_supply_function(item.pin_function)
        and not is_return_function(item.pin_function)
        and len(item.assignments) >= 2
        and all(len(nets) == 1 for nets in item.assignments.values())
        and len({nets for nets in item.assignments.values()}) >= 2
    )
    reviewable = tuple(
        item
        for item in eligible
        if item.common_anchor_pin_numbers or item.peer_assignment_group is not None
    )
    candidates = tuple(
        connector_footprint_named_divergence_candidate(
            item,
            RULE_ID,
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function})",
            message=(
                "Fitted connectors with distinct native symbols share the same value, footprint, "
                "complete pin inventory, and matching per-pin metadata. This explicitly named "
                "power-input contact is assigned to different nets. "
                + (
                    "A separate contact has one common assigned net. "
                    if item.common_anchor_pin_numbers
                    else "A current source-matched peer-assignment group scopes the comparison, "
                    "but no common-net anchor is present. "
                )
                + "Review the approved pinout and intended power-domain separation; similarity "
                "does not prove the assignments are wrong or should be joined."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
        )
        for item in reviewable
    )
    return NamedPowerInputDivergenceEvaluation(
        candidates=candidates,
        candidate_count=len(eligible),
        unanchored_count=len(eligible) - len(reviewable),
    )
