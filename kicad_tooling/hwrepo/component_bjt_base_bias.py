"""Review supported BJT bases without a visible direct emitter-bias resistor."""

from __future__ import annotations

from .component_bjt_symbols import basic_bjt_role_numbers
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_types import Candidate
from .models import NetlistContract
from .resistor_paths import direct_resistors

RULE_ID = "component.bjt_base_without_visible_emitter_bias"


def bjts_without_visible_emitter_bias(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Prompt when a connected supported BJT base lacks a direct base-emitter resistor.

    This is an opt-in review question about a possible off-state path. A driven
    base can be intentional without an external emitter resistor, so the rule
    never makes that relationship a default requirement.
    """
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_functions.items()
        if value.strip()
    }
    nets_by_pin: dict[str, list[str]] = {}
    net_members = {name.casefold(): (name, tuple(pins)) for name, pins in observed.nets.items()}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), []).append(net)

    resistor_pairs = {
        frozenset((item.first_net.casefold(), item.second_net.casefold()))
        for item in direct_resistors(observed)
    }
    findings: list[Candidate] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference_key = reference.casefold()
        if reference_key not in fitted or reference_key in dnp:
            continue
        role_numbers = basic_bjt_role_numbers(
            reference,
            symbol,
            inventories.get(reference_key, ()),
            functions,
        )
        if role_numbers is None:
            continue

        base_pin = f"{reference}.{role_numbers['base']}"
        emitter_pin = f"{reference}.{role_numbers['emitter']}"
        base_assignments = nets_by_pin.get(base_pin.casefold(), ())
        emitter_assignments = nets_by_pin.get(emitter_pin.casefold(), ())
        if len(base_assignments) != 1 or len(emitter_assignments) != 1:
            continue
        base_net, emitter_net = base_assignments[0], emitter_assignments[0]
        base_key, emitter_key = base_net.casefold(), emitter_net.casefold()
        if base_key == emitter_key or frozenset((base_key, emitter_key)) in resistor_pairs:
            continue

        _, assigned_base_pins = net_members.get(base_key, (base_net, ()))
        peers = tuple(
            sorted(
                (
                    pin
                    for pin in assigned_base_pins
                    if pin.casefold() != base_pin.casefold()
                    and "." in pin
                    and pin.rsplit(".", 1)[0].casefold() in fitted
                    and pin.rsplit(".", 1)[0].casefold() not in dnp
                ),
                key=str.casefold,
            )
        )
        if not peers:
            continue
        if fitted_output_pins_on_net(observed, base_net, excluded_references=(reference,)):
            # The direct-drive rule owns the higher-specificity output-pin case.
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{base_pin}: BJT base has no visible base-emitter bias resistor",
                message=(
                    "This fitted, supported BJT base has a fitted peer but no recognized nonzero "
                    "two-terminal resistor directly between its base and emitter nets. Review "
                    "whether the intended drive source leaves the base defined when disabled or "
                    "unpowered. Active drive, internal bias, or another topology can be valid; "
                    "this prompt does not establish that a resistor is required or adequate."
                ),
                evidence={
                    "component": (reference,),
                    "symbol": (symbol,),
                    "base_pin": (base_pin,),
                    "base_net": (base_net,),
                    "emitter_pin": (emitter_pin,),
                    "emitter_net": (emitter_net,),
                    "fitted_base_net_peers": peers,
                    "visible_base_emitter_bias_resistors": (),
                },
            )
        )
    return tuple(findings)
