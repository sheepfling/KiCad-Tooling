"""Review named signal contacts left open across footprint-alias connectors."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_named_signal_all_open"


@dataclass(frozen=True, slots=True)
class NamedSignalAllOpenEvaluation:
    """Candidates and coverage counts for named signal pins open on every peer."""

    candidates: tuple[Candidate, ...]
    candidate_count: int
    unanchored_count: int


def evaluate_footprint_named_signal_all_open(
    scan: ConnectorFootprintPeerPinScan,
) -> NamedSignalAllOpenEvaluation:
    """Review explicit signal contacts unassigned across eligible connector aliases."""
    eligible = tuple(
        item
        for item in scan.named_all_open
        if item.pin_electrical_type.strip().casefold() in SIGNAL_ELECTRICAL_TYPES
        and not pin_function_is_generic(item.pin_function)
        and not is_named_supply_function(item.pin_function)
        and not is_return_function(item.pin_function)
        and len(item.assignments) >= 2
        and all(not nets for nets in item.assignments.values())
    )
    anchored = tuple(item for item in eligible if item.common_anchor_pin_numbers)
    candidates = tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function})",
            message=(
                "Fitted connectors with distinct native symbols share the same value, footprint, "
                "complete pin inventory, and matching per-pin metadata. This explicitly named "
                "signal contact is unassigned on every compared peer while a separate pin has "
                "one common assigned net. Review the approved pinout and intended port use; an "
                "unused or isolated signal may be intentional, and similarity does not prove "
                "that it must connect."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
            evidence={
                "value": (item.value,),
                "footprint": (item.footprint,),
                "pin_number": (item.pin_number,),
                "pin_function": (item.pin_function,),
                "pin_electrical_type": (item.pin_electrical_type.strip().casefold(),),
                "assignments": tuple(f"{pin}=<unassigned>" for pin in item.assignments),
                "open_pins": tuple(item.assignments),
                "symbols": item.symbols,
                "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
                **(
                    {}
                    if item.peer_assignment_group is None
                    else {
                        "peer_assignment_group": (item.peer_assignment_group,),
                        "peer_assignment_basis": item.peer_assignment_basis,
                    }
                ),
            },
        )
        for item in anchored
    )
    return NamedSignalAllOpenEvaluation(
        candidates=candidates,
        candidate_count=len(eligible),
        unanchored_count=len(eligible) - len(anchored),
    )
