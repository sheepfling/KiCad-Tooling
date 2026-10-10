"""Find fitted supported two-pin passives whose schematic pins share one net."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ComponentRoleBinding, ComponentRoleMap, NetlistContract
from .two_pin_components import two_pin_components_on_same_net


@dataclass(frozen=True)
class TwoPinPassiveOnSameNet:
    """A complete, fitted supported passive with both pins on one native net."""

    reference: str
    symbol: str
    value: str
    kind: str
    pin_numbers: tuple[str, str]
    net: str
    role_binding: ComponentRoleBinding | None = None


def two_pin_passives_on_same_net(
    observed: NetlistContract,
    component_role_map: ComponentRoleMap | None = None,
) -> tuple[TwoPinPassiveOnSameNet, ...]:
    """Return only resistor, capacitor, and inductor same-net candidates."""
    return tuple(
        TwoPinPassiveOnSameNet(
            reference=item.reference,
            symbol=item.symbol,
            value=item.value,
            kind=item.kind,
            pin_numbers=item.pin_numbers,
            net=item.net,
            role_binding=item.role_binding,
        )
        for item in two_pin_components_on_same_net(observed, component_role_map)
        if item.kind in {"resistor", "capacitor", "inductor"}
    )
