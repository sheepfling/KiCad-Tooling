"""Review signal-pin net divergence across bounded footprint-alias connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_connector_footprint_named_divergence_evidence import (
    ConnectorFootprintNamedDivergenceCandidate,
    connector_footprint_named_divergence_candidate,
)

RULE_ID: Literal["connector.footprint_named_signal_assignment_divergence"] = (
    "connector.footprint_named_signal_assignment_divergence"
)


@dataclass(frozen=True, slots=True)
class NamedSignalDivergenceEvaluation:
    """Candidates and coverage counts for the bounded signal-pin predicate."""

    candidates: tuple[ConnectorFootprintNamedDivergenceCandidate, ...]
    candidate_count: int
    unanchored_count: int


def evaluate_footprint_named_signal_assignment_divergence(
    scan: ConnectorFootprintPeerPinScan,
) -> NamedSignalDivergenceEvaluation:
    """Review exact named signal contacts split across comparable connector aliases."""
    eligible = tuple(
        item
        for item in scan.named_divergences
        if item.pin_electrical_type.strip().casefold() in SIGNAL_ELECTRICAL_TYPES
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
                "signal contact is assigned to different nets while a separate contact has one "
                "common assigned net. Review the approved pinout and intended isolation; these "
                "similarity clues do not prove the assignments are wrong or should be joined."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
        )
        for item in anchored
    )
    return NamedSignalDivergenceEvaluation(
        candidates=candidates,
        candidate_count=len(eligible),
        unanchored_count=len(eligible) - len(anchored),
    )
