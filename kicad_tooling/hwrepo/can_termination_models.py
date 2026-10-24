"""Project-authored CAN termination requirements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    CapacitancePf,
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    ResistorReference,
    StrictModel,
)


class CanTerminationResistorRequirement(StrictModel):
    """One project-authored resistor path in a local CAN termination network."""

    reference: ResistorReference
    first_net: NetName
    second_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_resistor_path(self) -> CanTerminationResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("A CAN termination resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("CAN termination maximum resistance is below its minimum")
        return self


class CanTerminationResistorArrayChannelRequirement(StrictModel):
    """One project-reviewed pin and net mapping within a resistor-array channel."""

    id: Identifier
    first_pin: Reference
    second_pin: Reference
    first_net: NetName
    second_net: NetName

    @model_validator(mode="after")
    def distinct_channel_endpoints(self) -> CanTerminationResistorArrayChannelRequirement:
        if self.first_pin.casefold() == self.second_pin.casefold():
            raise ValueError("CAN resistor-array channel pins must differ")
        if self.first_net == self.second_net:
            raise ValueError("CAN resistor-array channel nets must differ")
        return self


class CanTerminationResistorArrayRequirement(StrictModel):
    """Exact identity and complete pin map for a CAN termination resistor array."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    expected_part_id: Identifier | None = None
    basis: NonEmptyText
    channels: Annotated[
        tuple[CanTerminationResistorArrayChannelRequirement, ...], Field(min_length=1)
    ]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def complete_pin_map(self) -> CanTerminationResistorArrayRequirement:
        prefix = f"{self.reference}.".casefold()
        mapped = [
            (pin, net)
            for channel in self.channels
            for pin, net in (
                (channel.first_pin, channel.first_net),
                (channel.second_pin, channel.second_net),
            )
        ]
        all_pins = (*[pin for pin, _ in mapped], *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix) for pin in all_pins):
            raise ValueError("CAN resistor-array pins must belong to their component")
        if len({channel.id.casefold() for channel in self.channels}) != len(self.channels):
            raise ValueError("CAN resistor-array channel IDs must be unique")
        if len({pin.casefold() for pin in self.unmapped_pin_reasons}) != len(
            self.unmapped_pin_reasons
        ):
            raise ValueError("CAN resistor-array unmapped pins must be unique")
        if {pin.casefold() for pin in self.unmapped_pin_reasons} & {
            pin.casefold() for pin, _ in mapped
        }:
            raise ValueError("Mapped CAN resistor-array pins cannot also be listed as unmapped")

        pin_nets: dict[str, str] = {}
        for pin, net in mapped:
            previous = pin_nets.setdefault(pin.casefold(), net.casefold())
            if previous != net.casefold():
                raise ValueError("A shared CAN resistor-array pin must map to one exact net")
        return self


class CanTerminationMidpointCapacitorRequirement(StrictModel):
    """Reviewed identity, pins, and nominal value for a split-termination capacitor."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    midpoint_pin: Reference
    reference_pin: Reference
    reference_net: NetName
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf

    @model_validator(mode="after")
    def exact_component_pins_and_range(self) -> CanTerminationMidpointCapacitorRequirement:
        prefix = f"{self.reference}.".casefold()
        if not self.midpoint_pin.casefold().startswith(
            prefix
        ) or not self.reference_pin.casefold().startswith(prefix):
            raise ValueError("CAN midpoint-capacitor pins must belong to the declared component")
        if self.midpoint_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("CAN midpoint-capacitor pins must differ")
        if self.maximum_nominal_capacitance_pf < self.minimum_nominal_capacitance_pf:
            raise ValueError("CAN midpoint-capacitor nominal capacitance range is reversed")
        return self


class CanTerminationEndpointRequirement(StrictModel):
    """Reviewed termination topology at one logical bus endpoint."""

    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "split", "external"]
    resistors: tuple[CanTerminationResistorRequirement, ...] = ()
    resistor_arrays: tuple[CanTerminationResistorArrayRequirement, ...] = ()
    midpoint_net: NetName | None = None
    midpoint_capacitor: CanTerminationMidpointCapacitorRequirement | None = None
    expected_dnp_resistors: tuple[ResistorReference, ...] = ()

    @model_validator(mode="after")
    def topology_has_matching_parts(self) -> CanTerminationEndpointRequirement:
        references = [
            *(item.reference.casefold() for item in self.resistors),
            *(item.reference.casefold() for item in self.resistor_arrays),
        ]
        if self.midpoint_capacitor is not None:
            references.append(self.midpoint_capacitor.reference.casefold())
        dnp_references = [item.casefold() for item in self.expected_dnp_resistors]
        if len(set(references)) != len(references) or len(set(dnp_references)) != len(
            dnp_references
        ):
            raise ValueError("CAN termination component references must be unique")
        if set(references) & set(dnp_references):
            raise ValueError("A CAN termination resistor cannot be both fitted and DNP")
        if self.topology == "direct":
            path_count = len(self.resistors) + sum(
                len(array.channels) for array in self.resistor_arrays
            )
            if path_count != 1 or self.midpoint_net is not None:
                raise ValueError(
                    "Direct CAN termination needs one resistor path and no midpoint net"
                )
            if self.midpoint_capacitor is not None:
                raise ValueError("Only split CAN termination can declare a midpoint capacitor")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted direct termination cannot require DNP resistors")
        elif self.topology == "split":
            path_count = len(self.resistors) + sum(
                len(array.channels) for array in self.resistor_arrays
            )
            if path_count != 2 or self.midpoint_net is None:
                raise ValueError(
                    "Split CAN termination needs two resistor paths and a midpoint net"
                )
            if self.expected_dnp_resistors:
                raise ValueError("A fitted split termination cannot require DNP resistors")
            if (
                self.midpoint_capacitor is not None
                and self.midpoint_capacitor.reference_net == self.midpoint_net
            ):
                raise ValueError("CAN midpoint capacitor must connect distinct nets")
        elif self.resistors or self.resistor_arrays or self.midpoint_net is not None:
            raise ValueError("External CAN termination cannot claim local fitted resistor paths")
        elif self.midpoint_capacitor is not None:
            raise ValueError("Only split CAN termination can declare a midpoint capacitor")
        return self


class CanTerminationBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    high_net: NetName
    low_net: NetName
    high_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    low_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    endpoints: Annotated[tuple[CanTerminationEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def endpoints_match_bus_nets(self) -> CanTerminationBusRequirement:
        if self.high_net == self.low_net:
            raise ValueError("CAN high and low nets must be distinct")
        pins = (*self.high_pins, *self.low_pins)
        if len(set(pins)) != len(pins):
            raise ValueError("CAN high/low pin assignments must be unique")
        if len({item.id for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("CAN termination endpoint IDs must be unique within a bus")
        refs = [
            reference.casefold()
            for endpoint in self.endpoints
            for reference in (
                *(item.reference for item in endpoint.resistors),
                *(item.reference for item in endpoint.resistor_arrays),
                *(
                    (endpoint.midpoint_capacitor.reference,)
                    if endpoint.midpoint_capacitor is not None
                    else ()
                ),
                *endpoint.expected_dnp_resistors,
            )
        ]
        if len(set(refs)) != len(refs):
            raise ValueError("CAN termination component references cannot be reused")
        for endpoint in self.endpoints:
            paths = tuple(
                frozenset((item.first_net, item.second_net)) for item in endpoint.resistors
            ) + tuple(
                frozenset((channel.first_net, channel.second_net))
                for array in endpoint.resistor_arrays
                for channel in array.channels
            )
            if endpoint.topology == "direct" and paths != (
                frozenset((self.high_net, self.low_net)),
            ):
                raise ValueError(
                    "Direct CAN termination must connect the declared high and low nets"
                )
            if endpoint.topology == "split":
                midpoint = endpoint.midpoint_net
                assert midpoint is not None
                if midpoint in {self.high_net, self.low_net}:
                    raise ValueError("Split CAN termination midpoint must differ from bus nets")
                expected = {
                    frozenset((self.high_net, midpoint)),
                    frozenset((self.low_net, midpoint)),
                }
                if set(paths) != expected:
                    raise ValueError(
                        "Split CAN termination resistors must connect each bus net to one midpoint"
                    )
        return self


class CanTerminationAnalysis(StrictModel):
    """Project-authored local CAN termination topology requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[CanTerminationBusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids_and_nets(self) -> CanTerminationAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("CAN termination bus IDs must be unique")
        signal_nets = [net for bus in self.buses for net in (bus.high_net, bus.low_net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("CAN termination signal nets must be unique across configured buses")
        component_references = [
            reference.casefold()
            for bus in self.buses
            for endpoint in bus.endpoints
            for reference in (
                *(item.reference for item in endpoint.resistors),
                *(item.reference for item in endpoint.resistor_arrays),
                *(
                    (endpoint.midpoint_capacitor.reference,)
                    if endpoint.midpoint_capacitor is not None
                    else ()
                ),
                *endpoint.expected_dnp_resistors,
            )
        ]
        if len(set(component_references)) != len(component_references):
            raise ValueError("CAN termination component references cannot be reused across buses")
        return self
