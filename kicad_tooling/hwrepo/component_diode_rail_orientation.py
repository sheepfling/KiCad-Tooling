"""Review exact diode symbols reversed across explicitly ordered voltage rails."""

from __future__ import annotations

from .component_diode_symbols import diode_terminal_numbers
from .component_named_rail_terminal import NamedRailTerminalEvidence
from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_component_polarity_candidate_evidence import (
    DIODE_RAIL_ORIENTATION_RULE_ID,
    ComponentPolarityCandidate,
    DiodeRailOrientationEvidence,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_assignments

RULE_ID = DIODE_RAIL_ORIENTATION_RULE_ID


def diodes_with_anode_below_cathode_on_named_rails(
    observed: NetlistContract,
) -> tuple[ComponentPolarityCandidate, ...]:
    """Prompt when a supported fitted diode's anode label is below its cathode.

    Only exact two-pin KiCad Device diode identities, native A/K function
    metadata, unambiguous assignments, and comparable named rail/return roles
    participate. Rail labels are a review clue; this check does not assert the
    diode's intended current direction or whether reverse bias is wrong.
    """
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): function.strip()
        for pin, function in observed.pin_functions.items()
        if function.strip()
    }
    nets_by_pin = netlist_pin_net_assignments(observed)

    findings: list[ComponentPolarityCandidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        pin_numbers = inventories.get(reference_key, ())
        if (
            reference_key not in fitted
            or reference_key in dnp
            or len(pin_numbers) != 2
            or len({number.casefold() for number in pin_numbers}) != 2
        ):
            continue

        roles = diode_terminal_numbers(reference, symbol, pin_numbers, functions)
        if roles is None:
            continue

        anode_pin = f"{reference}.{roles.anode}"
        cathode_pin = f"{reference}.{roles.cathode}"
        anode_nets = nets_by_pin.get(anode_pin.casefold(), ())
        cathode_nets = nets_by_pin.get(cathode_pin.casefold(), ())
        if len(anode_nets) != 1 or len(cathode_nets) != 1:
            continue
        anode_net, cathode_net = anode_nets[0], cathode_nets[0]
        if anode_net.casefold() == cathode_net.casefold():
            continue

        anode_potential = named_net_potential(anode_net, observed.nets[anode_net], functions)
        cathode_potential = named_net_potential(cathode_net, observed.nets[cathode_net], functions)
        if (
            anode_potential is None
            or cathode_potential is None
            or not potential_is_lower(anode_potential, cathode_potential)
        ):
            continue

        findings.append(
            ComponentPolarityCandidate.from_source_evidence(
                DiodeRailOrientationEvidence(
                    observed=observed,
                    reference=reference,
                    symbol=symbol,
                    anode=NamedRailTerminalEvidence(
                        pin=anode_pin,
                        net=anode_net,
                        potential=anode_potential,
                    ),
                    cathode=NamedRailTerminalEvidence(
                        pin=cathode_pin,
                        net=cathode_net,
                        potential=cathode_potential,
                    ),
                ),
                subject=f"{reference}: diode anode is below its cathode on named rails",
                message=(
                    "This supported diode's native anode pin resolves to a lower potential than "
                    "its cathode from named rail or return evidence. Review whether the direction "
                    "and assignments are intentional. Reverse-biased clamp and isolation uses can "
                    "be valid; labels and pin roles do not prove actual voltage, required current "
                    "direction, device behavior, or PCB connectivity."
                ),
            )
        )
    return tuple(findings)
