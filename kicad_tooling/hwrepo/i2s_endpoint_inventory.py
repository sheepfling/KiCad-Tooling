"""Source-bound fitted-IC I2S bit-clock and word-select inventory."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_FUNCTION_TOKENS = re.compile(r"[A-Z0-9]+", re.IGNORECASE)
_BIT_CLOCK_TOKENS = frozenset({"bclk", "bck", "bitclk", "bitclock", "sck"})
_WORD_SELECT_TOKENS = frozenset(
    {"lrck", "lrclk", "wclk", "wordclock", "wordsel", "wordselect", "ws"}
)
_DATA_TOKENS = frozenset({"data", "din", "dout", "sd", "sdata", "sdi", "sdo", "sdin", "sdout"})
_STRONG_BIT_CLOCK_TOKENS = frozenset({"bclk", "bck", "bitclk", "bitclock"})


def _i2s_function_roles(function: str) -> frozenset[str]:
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    roles: set[str] = set()
    if tokens & _BIT_CLOCK_TOKENS:
        roles.add("bit_clock")
    if tokens & _WORD_SELECT_TOKENS:
        roles.add("word_select")
    return frozenset(roles)


def i2s_function_role(function: str) -> str | None:
    """Classify one bounded native I2S bit-clock or word-select function."""
    roles = _i2s_function_roles(function)
    return next(iter(roles)) if len(roles) == 1 else None


def _i2s_data_function(function: str) -> bool:
    """Recognize bounded serial-data names used by native I2S pin functions."""
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    if not tokens & _DATA_TOKENS:
        return False
    # Generic DIN/SDI names overlap with unrelated interfaces. Accept them only
    # beside a distinctive I2S marker, supplied by the caller's clock pin.
    return "i2s" in tokens or bool(tokens & {"sd", "sdata", "sdin", "sdout"})


@dataclass(frozen=True, slots=True)
class I2sClockFrameEndpoint:
    """One fitted IC's unique native I2S clock pair and exact net assignments."""

    reference: str
    bit_clock_pin: str
    bit_clock_function: str
    bit_clock_electrical_type: str
    bit_clock_net: str
    word_select_pin: str
    word_select_function: str
    word_select_electrical_type: str
    word_select_net: str


@dataclass(frozen=True, slots=True)
class I2sClockDataEndpoint:
    """One fitted IC's native bit-clock and serial-data pins and exact nets."""

    reference: str
    bit_clock_pin: str
    bit_clock_function: str
    bit_clock_electrical_type: str
    bit_clock_net: str
    data_pin: str
    data_function: str
    data_electrical_type: str
    data_net: str


@dataclass(frozen=True, slots=True)
class I2sEndpointInventory:
    """Native pin metadata and assignment indexes for fitted audio ICs."""

    symbols: Mapping[str, str]
    reference_spellings: Mapping[str, str]
    components: Mapping[str, ComponentContract]
    inventories: Mapping[str, tuple[str, ...]]
    functions: Mapping[str, str]
    electrical_types: Mapping[str, str]
    assignments: Mapping[str, AbstractSet[str]]
    dnp_references: AbstractSet[str]

    @classmethod
    def from_netlist(cls, observed: NetlistContract) -> I2sEndpointInventory:
        """Build case-folded indexes from a normalized native netlist."""
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

    def clock_frame_endpoints(self) -> tuple[I2sClockFrameEndpoint, ...]:
        """Return only complete fitted endpoints with one unique pin per I2S role."""
        endpoints: list[I2sClockFrameEndpoint] = []
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
                "bit_clock": [],
                "word_select": [],
            }
            ambiguous_role = False
            for number in numbers:
                pin = f"{reference}.{number}"
                pin_key = f"{reference_key}.{number.casefold()}"
                function = self.functions[pin_key]
                roles = _i2s_function_roles(function)
                if len(roles) > 1:
                    ambiguous_role = True
                elif roles:
                    role = next(iter(roles))
                    by_role[role].append(
                        (
                            pin,
                            function,
                            self.electrical_types[pin_key],
                            self.assignments.get(pin.casefold(), frozenset()),
                        )
                    )

            if ambiguous_role or any(len(by_role[role]) != 1 for role in by_role):
                continue
            bit_clock_pin, bit_clock_function, bit_clock_type, bit_clock_nets = by_role[
                "bit_clock"
            ][0]
            word_select_pin, word_select_function, word_select_type, word_select_nets = by_role[
                "word_select"
            ][0]
            if len(bit_clock_nets) != 1 or len(word_select_nets) != 1:
                continue
            endpoints.append(
                I2sClockFrameEndpoint(
                    reference=reference,
                    bit_clock_pin=bit_clock_pin,
                    bit_clock_function=bit_clock_function,
                    bit_clock_electrical_type=bit_clock_type,
                    bit_clock_net=next(iter(bit_clock_nets)),
                    word_select_pin=word_select_pin,
                    word_select_function=word_select_function,
                    word_select_electrical_type=word_select_type,
                    word_select_net=next(iter(word_select_nets)),
                )
            )
        return tuple(endpoints)

    def clock_data_endpoints(self) -> tuple[I2sClockDataEndpoint, ...]:
        """Return complete fitted endpoints with one unambiguous I2S clock role."""
        endpoints: list[I2sClockDataEndpoint] = []
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

            clocks: list[tuple[str, str, str, AbstractSet[str]]] = []
            data_pins: list[tuple[str, str, str, AbstractSet[str]]] = []
            ambiguous_clock = False
            for number in numbers:
                pin = f"{reference}.{number}"
                pin_key = f"{reference_key}.{number.casefold()}"
                function = self.functions[pin_key]
                roles = _i2s_function_roles(function)
                is_data_function = _i2s_data_function(function)
                if len(roles) > 1 or (roles and is_data_function):
                    ambiguous_clock = True
                elif roles == frozenset({"bit_clock"}):
                    clocks.append(
                        (
                            pin,
                            function,
                            self.electrical_types[pin_key],
                            self.assignments.get(pin.casefold(), frozenset()),
                        )
                    )
                if is_data_function:
                    data_pins.append(
                        (
                            pin,
                            function,
                            self.electrical_types[pin_key],
                            self.assignments.get(pin.casefold(), frozenset()),
                        )
                    )

            if ambiguous_clock or len(clocks) != 1 or not data_pins:
                continue
            clock_pin, clock_function, clock_type, clock_nets = clocks[0]
            clock_tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(clock_function)}
            explicit_i2s_context = "i2s" in clock_tokens or bool(
                clock_tokens & _STRONG_BIT_CLOCK_TOKENS
            )
            if not explicit_i2s_context or len(clock_nets) != 1:
                continue
            for data_pin, data_function, data_type, data_nets in data_pins:
                if len(data_nets) != 1:
                    continue
                endpoints.append(
                    I2sClockDataEndpoint(
                        reference=reference,
                        bit_clock_pin=clock_pin,
                        bit_clock_function=clock_function,
                        bit_clock_electrical_type=clock_type,
                        bit_clock_net=next(iter(clock_nets)),
                        data_pin=data_pin,
                        data_function=data_function,
                        data_electrical_type=data_type,
                        data_net=next(iter(data_nets)),
                    )
                )
        return tuple(endpoints)
