"""Review split named power-output assignments across connector aliases."""

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

RULE_ID: Literal["connector.footprint_named_power_output_assignment_divergence"] = (
    "connector.footprint_named_power_output_assignment_divergence"
)


@dataclass(frozen=True, slots=True)
class NamedPowerOutputDivergenceEvaluation:
    """Candidates and coverage counts for split named power-output contacts."""

    candidates: tuple[ConnectorFootprintNamedDivergenceCandidate, ...]
    candidate_count: int
    unanchored_count: int


def evaluate_footprint_named_power_output_assignment_divergence(
    scan: ConnectorFootprintPeerPinScan,
) -> NamedPowerOutputDivergenceEvaluation:
    """Review explicit power-output contacts split across comparable connector aliases."""
    eligible = tuple(
        item
        for item in scan.named_divergences
        if item.pin_electrical_type.strip().casefold() == "power_out"
        and not pin_function_is_generic(item.pin_function)
        and not is_named_supply_function(item.pin_function)
        and not is_return_function(item.pin_function)
        and len(item.assignments) >= 2
        and all(len(nets) == 1 for nets in item.assignments.values())
        and len({nets for nets in item.assignments.values()}) >= 2
    )
    anchored = tuple(item for item in eligible if item.common_anchor_pin_numbers)
    candidates = tuple(
        connector_footprint_named_divergence_candidate(
            item,
            RULE_ID,
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function})",
            message=(
                "Fitted connectors with distinct native symbols share the same value, footprint, "
                "complete pin inventory, and matching per-pin metadata. This explicitly named "
                "power-output contact is assigned to different nets while a separate contact has "
                "one common assigned net. Review the approved pinout and intended output-domain "
                "separation; similarity does not prove the assignments are wrong or should be "
                "joined."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
        )
        for item in anchored
    )
    return NamedPowerOutputDivergenceEvaluation(
        candidates=candidates,
        candidate_count=len(eligible),
        unanchored_count=len(eligible) - len(anchored),
    )
