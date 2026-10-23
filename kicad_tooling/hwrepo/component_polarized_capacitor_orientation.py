"""Review exact polarized-capacitor symbols reversed across named rails."""

from __future__ import annotations

from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.polarized_capacitor_reversed_on_named_rails"
_SUPPORTED_SYMBOLS = frozenset(
    {
        "device:c_polarized",
        "device:c_polarized_small",
        "device:c_polarized_us",
        "device:c_polarized_small_us",
    }
)
_COMPLETE_PIN_NUMBERS = frozenset({"1", "2"})


def polarized_capacitors_on_reversed_named_rails(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
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
    nets_by_pin: dict[str, list[str]] = {}
    for net_name, members in observed.nets.items():
        for pin in members:
            nets_by_pin.setdefault(pin.casefold(), []).append(net_name)

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        if (
            reference_key not in fitted
            or reference_key in dnp
            or symbol.casefold() not in _SUPPORTED_SYMBOLS
            or frozenset(inventories.get(reference_key, ())) != _COMPLETE_PIN_NUMBERS
            or len(inventories.get(reference_key, ())) != 2
        ):
            continue

        positive_pin, negative_pin = f"{reference}.1", f"{reference}.2"
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
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: polarized capacitor pin 1 is below pin 2",
                message=(
                    "This supported polarized-capacitor symbol assigns pin 1 to its positive "
                    "terminal, but the connected net has a lower explicitly named potential "
                    "than pin 2. Review the symbol orientation and rail labels. These names "
                    "are review evidence, not proof of actual voltage, polarity, or hardware "
                    "behavior."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "positive_terminal_pin": (positive_pin,),
                    "negative_terminal_pin": (negative_pin,),
                    "positive_terminal_net": (positive_net,),
                    "negative_terminal_net": (negative_net,),
                    "positive_terminal_potential_evidence": positive_potential.evidence,
                    "negative_terminal_potential_evidence": negative_potential.evidence,
                },
            )
        )
    return tuple(findings)
