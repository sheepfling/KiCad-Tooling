"""Project-authored CAN termination requirements."""

from __future__ import annotations

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
    midpoint_net: NetName | None = None
    midpoint_capacitor: CanTerminationMidpointCapacitorRequirement | None = None
    expected_dnp_resistors: tuple[ResistorReference, ...] = ()

    @model_validator(mode="after")
    def topology_has_matching_parts(self) -> CanTerminationEndpointRequirement:
        references = [item.reference.casefold() for item in self.resistors]
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
            if len(self.resistors) != 1 or self.midpoint_net is not None:
                raise ValueError("Direct CAN termination needs one resistor and no midpoint net")
            if self.midpoint_capacitor is not None:
                raise ValueError("Only split CAN termination can declare a midpoint capacitor")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted direct termination cannot require DNP resistors")
        elif self.topology == "split":
            if len(self.resistors) != 2 or self.midpoint_net is None:
                raise ValueError("Split CAN termination needs two resistors and a midpoint net")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted split termination cannot require DNP resistors")
            if (
                self.midpoint_capacitor is not None
                and self.midpoint_capacitor.reference_net == self.midpoint_net
            ):
                raise ValueError("CAN midpoint capacitor must connect distinct nets")
        elif self.resistors or self.midpoint_net is not None:
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
