"""Review named positive-supply pins assigned to explicitly negative rails."""

from __future__ import annotations

from .connector_identity import power_function_key
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_power_pin_role_evidence import NamedSupplyPinNegativeRailEvidence
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .power_rails import negative_voltage_rail_key


def positive_supply_pins_on_negative_rails(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Prompt review for a named supply pin assigned to an explicitly minus-prefixed rail."""
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin = netlist_pin_net_index(observed)

    candidates: list[PowerCandidate] = []
    for pin, function in sorted(observed.pin_functions.items()):
        reference = pin.rsplit(".", 1)[0]
        if reference.startswith("#") or reference.casefold() in dnp:
            continue
        function_key = power_function_key(function)
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if function_key is None or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        negative_rail_key = negative_voltage_rail_key(net)
        if negative_rail_key is None:
            continue
        source = NamedSupplyPinNegativeRailEvidence(
            observed=observed,
            pin=pin,
            function=function,
            net=net,
        )
        candidates.append(
            PowerCandidate.from_source_evidence(
                source,
                subject=f"{pin}: {function} pin assigned to {net}",
                message=(
                    "This named supply pin is assigned to a net whose label has an explicit "
                    "negative-voltage form. Review the symbol pinout and the rail naming; "
                    "these names do not prove electrical potential or project intent."
                ),
            )
        )
    return tuple(candidates)
