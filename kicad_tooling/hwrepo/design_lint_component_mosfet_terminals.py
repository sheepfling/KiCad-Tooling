"""Review supported MOSFETs whose main terminals share one schematic net."""

from __future__ import annotations

from .component_mosfet_symbols import mosfet_channel_type, mosfet_terminal_role_numbers
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.mosfet_drain_source_same_net"


def mosfets_with_drain_source_on_same_net(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, supported MOSFETs with drain and source on one native net."""
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, list[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append(net)

    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        channel_type = mosfet_channel_type(symbol)
        if reference_key not in fitted or reference_key in dnp or channel_type is None:
            continue
        roles = mosfet_terminal_role_numbers(
            reference,
            symbol,
            inventories.get(reference_key, ()),
            observed.pin_functions,
        )
        if roles is None:
            continue

        drain_pin = f"{reference}.{roles['drain']}"
        source_pin = f"{reference}.{roles['source']}"
        drain_nets = nets_by_pin.get(drain_pin.casefold(), ())
        source_nets = nets_by_pin.get(source_pin.casefold(), ())
        if len(drain_nets) != 1 or len(source_nets) != 1:
            continue
        drain_net, source_net = drain_nets[0], source_nets[0]
        if drain_net.casefold() != source_net.casefold():
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: MOSFET drain and source share one schematic net",
                message=(
                    "The native schematic assigns this supported MOSFET's drain and source to "
                    "the same net, bypassing its controllable conduction path in the netlist. "
                    "Review whether the assignment is intentional. This prompt does not prove "
                    "a defect or establish PCB copper continuity or physical behavior."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "channel_type": (channel_type,),
                    "drain_pin": (drain_pin,),
                    "drain_net": (drain_net,),
                    "source_pin": (source_pin,),
                    "source_net": (source_net,),
                },
            )
        )
    return tuple(findings)
