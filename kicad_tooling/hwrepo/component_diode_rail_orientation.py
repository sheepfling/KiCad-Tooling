"""Review exact diode symbols reversed across explicitly ordered voltage rails."""

from __future__ import annotations

from .component_rail_potentials import named_net_potential, potential_is_lower
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.diode_anode_below_cathode_on_named_rails"
_SUPPORTED_SYMBOLS = frozenset({"device:d", "device:d_schottky"})


def diodes_with_anode_below_cathode_on_named_rails(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
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
    nets_by_pin: dict[str, list[str]] = {}
    for net_name, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append(net_name)

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        pin_numbers = inventories.get(reference_key, ())
        if (
            reference_key not in fitted
            or reference_key in dnp
            or symbol.casefold() not in _SUPPORTED_SYMBOLS
            or len(pin_numbers) != 2
            or len({number.casefold() for number in pin_numbers}) != 2
        ):
            continue

        role_to_number: dict[str, str] = {}
        for number in pin_numbers:
            role = functions.get(f"{reference}.{number}".casefold())
            role_key = None if role is None else role.casefold()
            if role_key in {"a", "k"}:
                if role_key in role_to_number:
                    break
                role_to_number[role_key] = number
        if set(role_to_number) != {"a", "k"}:
            continue

        anode_pin = f"{reference}.{role_to_number['a']}"
        cathode_pin = f"{reference}.{role_to_number['k']}"
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

        ordering_evidence: dict[str, tuple[str, ...]] = {
            "anode_potential_basis": anode_potential.evidence,
            "cathode_potential_basis": cathode_potential.evidence,
        }
        if anode_potential.value is not None:
            ordering_evidence["anode_ordering_value_volts"] = (str(anode_potential.value),)
        if cathode_potential.value is not None:
            ordering_evidence["cathode_ordering_value_volts"] = (str(cathode_potential.value),)

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: diode anode is below its cathode on named rails",
                message=(
                    "This supported diode's native anode pin resolves to a lower potential than "
                    "its cathode from named rail or return evidence. Review whether the direction "
                    "and assignments are intentional. Reverse-biased clamp and isolation uses can "
                    "be valid; labels and pin roles do not prove actual voltage, required current "
                    "direction, device behavior, or PCB connectivity."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "anode_pin": (anode_pin,),
                    "anode_net": (anode_net,),
                    "cathode_pin": (cathode_pin,),
                    "cathode_net": (cathode_net,),
                    **ordering_evidence,
                },
            )
        )
    return tuple(findings)
