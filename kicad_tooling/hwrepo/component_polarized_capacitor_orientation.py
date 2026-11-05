"""Review exact polarized-capacitor symbols reversed across named rails."""

from __future__ import annotations

from .component_named_rail_terminal import NamedRailTerminalEvidence
from .component_polarized_capacitor_symbols import polarized_capacitor_terminal_numbers
from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_component_polarity_candidate_evidence import (
    POLARIZED_CAPACITOR_RAIL_ORIENTATION_RULE_ID,
    ComponentPolarityCandidate,
    PolarizedCapacitorRailOrientationEvidence,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_assignments

RULE_ID = POLARIZED_CAPACITOR_RAIL_ORIENTATION_RULE_ID


def polarized_capacitors_on_reversed_named_rails(
    observed: NetlistContract,
) -> tuple[ComponentPolarityCandidate, ...]:
    """Prompt when a supported fitted capacitor's pin 1 is clearly below pin 2.

    KiCad's four supported Device:C_Polarized symbols assign pin 1 to the
    positive terminal. This check requires a complete two-pin inventory and
    exactly one distinct net assignment per pin. It compares signed numeric
    rail labels, or a clearly named return against a positive symbolic rail;
    other role conflicts and unresolved potentials are excluded.
    """
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(number.casefold() for number in numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): function.strip() for pin, function in observed.pin_functions.items()
    }
    nets_by_pin = netlist_pin_net_assignments(observed)

    findings: list[ComponentPolarityCandidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        if reference_key not in fitted or reference_key in dnp:
            continue

        roles = polarized_capacitor_terminal_numbers(
            symbol,
            inventories.get(reference_key, ()),
        )
        if roles is None:
            continue

        positive_pin = f"{reference}.{roles.positive}"
        negative_pin = f"{reference}.{roles.negative}"
        positive_nets = nets_by_pin.get(positive_pin.casefold(), ())
        negative_nets = nets_by_pin.get(negative_pin.casefold(), ())
        if len(positive_nets) != 1 or len(negative_nets) != 1:
            continue
        positive_net, negative_net = positive_nets[0], negative_nets[0]
        if positive_net.casefold() == negative_net.casefold():
            continue

        positive_potential = named_net_potential(
            positive_net,
            observed.nets[positive_net],
            functions,
        )
        negative_potential = named_net_potential(
            negative_net,
            observed.nets[negative_net],
            functions,
        )
        if (
            positive_potential is None
            or negative_potential is None
            or not potential_is_lower(positive_potential, negative_potential)
        ):
            continue

        findings.append(
            ComponentPolarityCandidate.from_source_evidence(
                PolarizedCapacitorRailOrientationEvidence(
                    observed=observed,
                    reference=reference,
                    symbol=symbol,
                    positive=NamedRailTerminalEvidence(
                        pin=positive_pin,
                        net=positive_net,
                        potential=positive_potential,
                    ),
                    negative=NamedRailTerminalEvidence(
                        pin=negative_pin,
                        net=negative_net,
                        potential=negative_potential,
                    ),
                ),
                subject=f"{reference}: polarized capacitor pin 1 is below pin 2",
                message=(
                    "This supported polarized-capacitor symbol assigns pin 1 to its positive "
                    "terminal, but the connected net has a lower explicitly named potential "
                    "than pin 2. Review the symbol orientation and rail labels. These names "
                    "are review evidence, not proof of actual voltage, polarity, or hardware "
                    "behavior."
                ),
            )
        )
    return tuple(findings)
