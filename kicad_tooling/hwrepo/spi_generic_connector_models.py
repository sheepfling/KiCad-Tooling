"""Typed source observations for generic connector SPI review."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SpiGenericEndpointTriad:
    """One fitted IC and one exact native SPI clock/data role triad."""

    reference: str
    channel: str
    clock_pin: str
    clock_net: str
    data_input_pin: str
    data_input_net: str
    data_output_pin: str
    data_output_net: str


@dataclass(frozen=True, slots=True)
class SpiGenericConnectorTriad:
    """Generic connector contacts assigned to one recognized SPI role triad."""

    connector_reference: str
    connector_pin_count: int
    role_connector_pins: Mapping[str, tuple[str, ...]]
    role_connector_functions: Mapping[str, tuple[str, ...]]
    role_nets: Mapping[str, str]
    endpoint_triads: tuple[SpiGenericEndpointTriad, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "role_connector_pins",
            MappingProxyType({key: tuple(value) for key, value in self.role_connector_pins.items()}),
        )
        object.__setattr__(
            self,
            "role_connector_functions",
            MappingProxyType(
                {key: tuple(value) for key, value in self.role_connector_functions.items()}
            ),
        )
        object.__setattr__(self, "role_nets", MappingProxyType(dict(self.role_nets)))
