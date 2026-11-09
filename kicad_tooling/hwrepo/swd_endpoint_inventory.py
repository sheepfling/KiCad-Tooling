"""Source-bound native SWD endpoint inventory and role recognition."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .swd_generic_connector_models import SwdDebugEndpoint

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_FUNCTION_TOKENS = re.compile(r"[A-Z0-9]+", re.IGNORECASE)


def swd_function_role(function: str) -> str | None:
    """Return one bounded native SWD role, including the historical SWDCLK alias."""
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    roles: set[str] = set()
    if "swdio" in tokens:
        roles.add("swdio")
    if tokens & {"swclk", "swdclk"}:
        roles.add("swclk")
    return next(iter(roles)) if len(roles) == 1 else None


@dataclass(frozen=True, slots=True)
class SwdEndpointInventory:
    """Native pin assignments needed to recognize one complete fitted SWD pair."""

    symbols: Mapping[str, str]
    reference_spellings: Mapping[str, str]
    components: Mapping[str, ComponentContract]
    inventories: Mapping[str, tuple[str, ...]]
    functions: Mapping[str, str]
    electrical_types: Mapping[str, str]
    assignments: Mapping[str, AbstractSet[str]]
    dnp_references: AbstractSet[str]

    @classmethod
    def from_netlist(cls, observed: NetlistContract) -> SwdEndpointInventory:
        """Build the case-folded source indexes from one normalized native netlist."""
        return cls(
            symbols=casefolded_unique_index(observed.component_symbols),
            reference_spellings=casefolded_unique_index(
                {reference: reference for reference in observed.component_symbols}
            ),
            components=casefolded_unique_index(observed.components),
            inventories=casefolded_unique_index(observed.component_pin_numbers),
            functions=casefolded_unique_index(observed.pin_functions),
            electrical_types=casefolded_unique_index(observed.pin_electrical_types),
            assignments=netlist_pin_net_index(observed),
            dnp_references=frozenset(reference.casefold() for reference in observed.dnp_components),
        )

    def endpoint_pairs(
        self,
        *,
        include_same_net: bool = False,
    ) -> tuple[SwdDebugEndpoint, ...]:
        """Return unique fitted SWDIO/SWCLK pairs with complete pin evidence.

        By default, pairs sharing one net remain excluded for the existing
        connector-association rule. The same-net lint opts in so that it can
        report this distinct condition without weakening that existing rule.
        """
        endpoints: list[SwdDebugEndpoint] = []
        for reference_key in sorted(self.symbols):
            reference = self.reference_spellings.get(reference_key)
            if (
                reference is None
                or not _IC_REFERENCE.fullmatch(reference)
                or reference_key in self.dnp_references
                or reference_key not in self.components
            ):
                continue
            numbers = self.inventories.get(reference_key)
            if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
                continue
            if not connector_pin_metadata_matches_inventory(
                reference_key, numbers, self.functions, self.electrical_types
            ):
                continue

            by_role: dict[str, list[tuple[str, str, str, AbstractSet[str]]]] = {
                "swdio": [],
                "swclk": [],
            }
            for number in numbers:
                pin = f"{reference}.{number}"
                function = self.functions[f"{reference_key}.{number.casefold()}"]
                role = swd_function_role(function)
                if role is not None:
                    by_role[role].append(
                        (
                            pin,
                            function,
                            self.electrical_types[f"{reference_key}.{number.casefold()}"],
                            self.assignments.get(pin.casefold(), frozenset()),
                        )
                    )

            if any(len(by_role[role]) != 1 for role in by_role):
                continue
            swdio_pin, swdio_function, swdio_type, swdio_nets = by_role["swdio"][0]
            swclk_pin, swclk_function, swclk_type, swclk_nets = by_role["swclk"][0]
            if len(swdio_nets) != 1 or len(swclk_nets) != 1:
                continue
            swdio_net = next(iter(swdio_nets))
            swclk_net = next(iter(swclk_nets))
            if not include_same_net and swdio_net.casefold() == swclk_net.casefold():
                continue
            endpoints.append(
                SwdDebugEndpoint(
                    reference=reference,
                    swdio_pin=swdio_pin,
                    swdio_function=swdio_function,
                    swdio_electrical_type=swdio_type,
                    swdio_net=swdio_net,
                    swclk_pin=swclk_pin,
                    swclk_function=swclk_function,
                    swclk_electrical_type=swclk_type,
                    swclk_net=swclk_net,
                )
            )
        return tuple(endpoints)
