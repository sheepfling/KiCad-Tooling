"""Review supported BJTs whose collector and emitter share one schematic net."""

from __future__ import annotations

from .component_bjt_symbols import basic_bjt_role_numbers
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "component.bjt_collector_emitter_same_net"


def bjts_with_collector_emitter_on_same_net(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, supported basic BJTs with collector and emitter on one net."""
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): function.strip().casefold()
        for pin, function in observed.pin_functions.items()
        if function.strip()
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
        if reference_key not in fitted or reference_key in dnp:
            continue
        roles = basic_bjt_role_numbers(
            reference,
            symbol,
            inventories.get(reference_key, ()),
            functions,
        )
        if roles is None:
            continue

        collector_pin = f"{reference}.{roles['collector']}"
        emitter_pin = f"{reference}.{roles['emitter']}"
        collector_nets = nets_by_pin.get(collector_pin.casefold(), ())
        emitter_nets = nets_by_pin.get(emitter_pin.casefold(), ())
        if len(collector_nets) != 1 or len(emitter_nets) != 1:
            continue
        collector_net, emitter_net = collector_nets[0], emitter_nets[0]
        if collector_net.casefold() != emitter_net.casefold():
            continue

        family = symbol.casefold().rsplit(":", 1)[-1].removeprefix("q_").split("_", 1)[0]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: BJT collector and emitter share one schematic net",
                message=(
                    "The native schematic assigns this supported BJT's collector and emitter to "
                    "the same net, bypassing its controllable conduction path in the netlist. "
                    "Review whether the assignment is intentional. This prompt does not prove "
                    "a defect or establish PCB copper continuity or physical behavior."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "transistor_family": (family,),
                    "collector_pin": (collector_pin,),
                    "collector_net": (collector_net,),
                    "emitter_pin": (emitter_pin,),
                    "emitter_net": (emitter_net,),
                },
            )
        )
    return tuple(findings)
