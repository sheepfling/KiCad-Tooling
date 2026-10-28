"""Review split named power-input assignments across connector aliases."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_named_power_input_assignment_divergence"


@dataclass(frozen=True, slots=True)
class NamedPowerInputDivergenceEvaluation:
    """Candidates and coverage counts for split named power-input contacts."""

    candidates: tuple[Candidate, ...]
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
    anchored = tuple(item for item in eligible if item.common_anchor_pin_numbers)
    candidates = tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function})",
            message=(
                "Fitted connectors with distinct native symbols share the same value, footprint, "
                "complete pin inventory, and matching per-pin metadata. This explicitly named "
                "power-input contact is assigned to different nets while a separate contact has "
                "one common assigned net. Review the approved pinout and intended power-domain "
                "separation; similarity does not prove the assignments are wrong or should be "
                "joined."
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
                "assignments": tuple(f"{pin}={nets[0]}" for pin, nets in item.assignments.items()),
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
    return NamedPowerInputDivergenceEvaluation(
        candidates=candidates,
        candidate_count=len(eligible),
        unanchored_count=len(eligible) - len(anchored),
    )
