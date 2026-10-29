"""Review unanchored connector power-input peers split across equal-voltage labels."""

from __future__ import annotations

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import is_return_function
from .design_lint_types import Candidate
from .power_rails import explicit_voltage_rail_value

RULE_ID = "connector.footprint_same_voltage_power_input_unanchored"


def unanchored_same_voltage_power_input_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Find comparable connector power-input pins split across equal-voltage rails.

    Explicit rail labels and matching native peer metadata are clues for review;
    they do not establish a common power domain or a requirement to join nets.
    """
    candidates: list[Candidate] = []
    for item in scan.named_divergences:
        if (
            item.pin_electrical_type.strip().casefold() != "power_in"
            or is_return_function(item.pin_function)
            or item.common_anchor_pin_numbers
            or len(item.assignments) < 2
            or any(len(nets) != 1 for nets in item.assignments.values())
        ):
            continue
        assignments = tuple(
            (pin, nets[0], explicit_voltage_rail_value(nets[0]))
            for pin, nets in item.assignments.items()
        )
        voltages = {voltage for _, _, voltage in assignments}
        net_names = {net for _, net, _ in assignments}
        if None in voltages or len(voltages) != 1 or len(net_names) < 2:
            continue
        voltage = next(iter(voltages))
        assert voltage is not None
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{item.value} [{item.footprint}] pin {item.pin_number} "
                    f"({item.pin_function})"
                ),
                message=(
                    "Fitted connector peers have matching native pin metadata and explicit "
                    "different net labels that indicate the same nominal voltage, without "
                    "another shared pin to anchor the comparison. Review whether separate "
                    "sources, filtering, or isolation are intentional; matching voltage labels "
                    "do not prove these domains should be joined."
                ),
                evidence={
                    "value": (item.value,),
                    "footprint": (item.footprint,),
                    "pin_number": (item.pin_number,),
                    "pin_function": (item.pin_function,),
                    "pin_electrical_type": (item.pin_electrical_type.strip().casefold(),),
                    "nominal_voltage_v": (str(voltage),),
                    "assignments": tuple(
                        f"{pin}={net}" for pin, net, _ in assignments
                    ),
                    "symbols": item.symbols,
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
        )
    return tuple(candidates)
