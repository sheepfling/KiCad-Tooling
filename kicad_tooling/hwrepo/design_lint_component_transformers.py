"""Review a supported transformer winding whose terminals share one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract

_SUPPORTED_WINDINGS = {
    "transformer:transf1": (("winding_1", ("1", "2")), ("winding_2", ("3", "4")))
}


def transformer_winding_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Return review candidates for complete TRANSF1 windings assigned to one net.

    The allowlist is deliberately exact. KiCad 10.0.5 defines TRANSF1 as a
    four-terminal symbol with winding pin groups 1/2 and 3/4; other symbols
    need their own reviewed pin-group definition.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    component_by_reference = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    pins_by_reference = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    found: list[Candidate] = []
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        winding_groups = _SUPPORTED_WINDINGS.get(symbol.casefold())
        if winding_groups is None or reference_key in dnp:
            continue
        pin_numbers = pins_by_reference.get(reference_key)
        component = component_by_reference.get(reference_key)
        if (
            component is None
            or pin_numbers is None
            or len(pin_numbers) != 4
            or {number.casefold() for number in pin_numbers} != {"1", "2", "3", "4"}
        ):
            continue

        assigned_nets = {
            number: nets_by_pin.get(f"{reference}.{number}".casefold(), set())
            for number in ("1", "2", "3", "4")
        }
        if any(len(nets) != 1 for nets in assigned_nets.values()):
            continue

        for winding, numbers in winding_groups:
            first_net = next(iter(assigned_nets[numbers[0]]))
            second_net = next(iter(assigned_nets[numbers[1]]))
            if first_net != second_net:
                continue
            found.append(
                Candidate(
                    rule_id="component.transformer_winding_same_net",
                    subject=(
                        f"{reference}: {winding.replace('_', ' ')} pins "
                        f"{numbers[0]}/{numbers[1]} "
                        f"share {first_net}"
                    ),
                    message=(
                        f"The supported TRANSF1 {winding.replace('_', ' ')} terminals are assigned to "
                        "one native schematic net, leaving no netlist voltage across that "
                        "winding. Review whether this is intentional or a connection is missing. "
                        "This prompt does not establish transformer operation, isolation rating, "
                        "winding polarity, physical connectivity, copper continuity, or assembly "
                        "state."
                    ),
                    evidence={
                        "symbol": (symbol,),
                        "value": (component.value,),
                        "winding": (winding,),
                        "net": (first_net,),
                        "pin_assignments": tuple(
                            f"{reference}.{number} -> {first_net}" for number in numbers
                        ),
                    },
                )
            )
    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))
