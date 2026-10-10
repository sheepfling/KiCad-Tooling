"""Typed project-authored MOSFET terminal-stress contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    FiniteMeasure,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    StrictModel,
)


class MosfetVoltageInterval(StrictModel):
    """Authored lower and upper net-potential bounds for one operating state."""

    minimum_v: FiniteMeasure
    maximum_v: FiniteMeasure

    @model_validator(mode="after")
    def ordered_bounds(self) -> MosfetVoltageInterval:
        if self.minimum_v > self.maximum_v:
            raise ValueError("MOSFET state-potential minimum cannot exceed its maximum")
        return self


class MosfetOperatingState(StrictModel):
    """One reviewed state and the net potentials supplied for that state."""

    id: Identifier
    net_potentials: Mapping[NetName, MosfetVoltageInterval] = Field(default_factory=dict)


class MosfetStressRequirement(StrictModel):
    """Exact three-pin MOSFET identity and sourced VDS/VGS limits."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    drain_pin: Reference
    drain_function: NonEmptyText
    drain_net: NetName
    gate_pin: Reference
    gate_function: NonEmptyText
    gate_net: NetName
    source_pin: Reference
    source_function: NonEmptyText
    source_net: NetName
    rated_maximum_vds_v: ElectricalPositive
    rated_maximum_vgs_v: ElectricalPositive
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_three_pin_terminals(self) -> MosfetStressRequirement:
        terminals = (
            ("drain", self.drain_pin, self.drain_function, self.drain_net),
            ("gate", self.gate_pin, self.gate_function, self.gate_net),
            ("source", self.source_pin, self.source_function, self.source_net),
        )
        expected_functions = (
            ("drain", {"d", "drain"}),
            ("gate", {"g", "gate"}),
            ("source", {"s", "source"}),
        )
        for (terminal_role, pin, function, _), (role, accepted) in zip(
            terminals, expected_functions, strict=True
        ):
            if function.casefold() not in accepted:
                raise ValueError(
                    f"MOSFET {role} function must be D/DRAIN, G/GATE, or S/SOURCE as appropriate"
                )
            if pin.count(".") != 1:
                raise ValueError("MOSFET terminal pins must use an exact reference.pin number")
            if pin.rsplit(".", maxsplit=1)[0].casefold() != self.reference.casefold():
                raise ValueError(
                    f"MOSFET {terminal_role} pin must belong to the declared reference"
                )
        if len({terminal[1].casefold() for terminal in terminals}) != 3:
            raise ValueError("MOSFET terminal pins must be distinct")
        if len({terminal[3].casefold() for terminal in terminals}) != 3:
            raise ValueError("MOSFET drain, gate, and source nets must be distinct")
        return self


class MosfetStressAnalysis(StrictModel):
    """Project-authored, state-aware stress bounds for exact three-pin MOSFETs."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    required_states: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    states: tuple[MosfetOperatingState, ...] = ()
    requirements: Annotated[tuple[MosfetStressRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_states_and_parts(self) -> MosfetStressAnalysis:
        required = {state.casefold() for state in self.required_states}
        state_ids = {state.id.casefold() for state in self.states}
        requirement_ids = {item.id.casefold() for item in self.requirements}
        references = {item.reference.casefold() for item in self.requirements}
        if len(required) != len(self.required_states):
            raise ValueError("Required MOSFET operating-state IDs must be unique")
        if len(state_ids) != len(self.states):
            raise ValueError("MOSFET operating-state IDs must be unique")
        if not state_ids <= required:
            raise ValueError("MOSFET states may only define declared required states")
        if len(requirement_ids) != len(self.requirements):
            raise ValueError("MOSFET stress requirement IDs must be unique")
        if len(references) != len(self.requirements):
            raise ValueError("Each MOSFET reference may have one stress requirement")
        return self
