"""Review a supported transformer winding whose terminals share one net."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_types import Candidate
from .models import NetlistContract

_WindingGroup = tuple[str, tuple[str, str]]
_SUPPORTED_WINDINGS = {
    "transformer:transf1": (("winding_1", ("1", "2")), ("winding_2", ("3", "4")))
}


@dataclass(frozen=True)
class _SupportedTransformer:
    reference: str
    symbol: str
    value: str
    winding_groups: tuple[_WindingGroup, ...]
    pin_nets: tuple[tuple[str, str], ...]


def _supported_transformers(observed: NetlistContract) -> tuple[_SupportedTransformer, ...]:
    """Return exact, fitted TRANSF1 records with complete unambiguous pin nets."""
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

    transformers: list[_SupportedTransformer] = []
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        winding_groups = _SUPPORTED_WINDINGS.get(symbol.casefold())
        component = component_by_reference.get(reference_key)
        pin_numbers = pins_by_reference.get(reference_key)
        if (
            winding_groups is None
            or reference_key in dnp
            or component is None
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
        transformers.append(
            _SupportedTransformer(
                reference=reference,
                symbol=symbol,
                value=component.value,
                winding_groups=winding_groups,
                pin_nets=tuple(
                    (number, next(iter(assigned_nets[number]))) for number in ("1", "2", "3", "4")
                ),
            )
        )
    return tuple(transformers)


def transformer_winding_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Return review candidates for complete TRANSF1 windings assigned to one net.

    The allowlist is deliberately exact. KiCad 10.0.5 defines TRANSF1 as a
    four-terminal symbol with winding pin groups 1/2 and 3/4; other symbols
    need their own reviewed pin-group definition.
    """
    found: list[Candidate] = []
    for transformer in _supported_transformers(observed):
        pin_nets = dict(transformer.pin_nets)
        for winding, numbers in transformer.winding_groups:
            first_net = pin_nets[numbers[0]]
            second_net = pin_nets[numbers[1]]
            if first_net != second_net:
                continue
            found.append(
                Candidate(
                    rule_id="component.transformer_winding_same_net",
                    subject=(
                        f"{transformer.reference}: {winding.replace('_', ' ')} pins "
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
                        "symbol": (transformer.symbol,),
                        "value": (transformer.value,),
                        "winding": (winding,),
                        "net": (first_net,),
                        "pin_assignments": tuple(
                            f"{transformer.reference}.{number} -> {first_net}" for number in numbers
                        ),
                    },
                )
            )
    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))


def transformer_winding_groups_share_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review a native schematic net shared by both exact TRANSF1 winding groups."""
    found: list[Candidate] = []
    for transformer in _supported_transformers(observed):
        first_group = transformer.winding_groups[0]
        second_group = transformer.winding_groups[1]
        pin_nets = dict(transformer.pin_nets)
        first_nets = {pin_nets[number] for number in first_group[1]}
        second_nets = {pin_nets[number] for number in second_group[1]}
        for net in sorted(first_nets & second_nets, key=str.casefold):
            first_pins = tuple(
                f"{transformer.reference}.{number}"
                for number in first_group[1]
                if pin_nets[number] == net
            )
            second_pins = tuple(
                f"{transformer.reference}.{number}"
                for number in second_group[1]
                if pin_nets[number] == net
            )
            found.append(
                Candidate(
                    rule_id="component.transformer_winding_groups_share_net",
                    subject=(f"{transformer.reference}: winding groups share {net}"),
                    message=(
                        "Both supported TRANSF1 winding groups touch this native schematic net, "
                        "so those sides are not isolated in the netlist. Review whether the "
                        "cross-winding connection is intentional. This prompt does not infer "
                        "whether isolation is required or approved, or establish transformer "
                        "operation, physical connectivity, copper continuity, or assembly state."
                    ),
                    evidence={
                        "symbol": (transformer.symbol,),
                        "value": (transformer.value,),
                        "shared_net": (net,),
                        "first_winding_pins": first_pins,
                        "second_winding_pins": second_pins,
                    },
                )
            )
    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))
