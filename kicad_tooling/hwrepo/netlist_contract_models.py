"""Authored component and observed netlist contracts."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, ValidationInfo, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel
from .netlist_contract_inputs import NetlistRawValue, normalize_native_unconnected_nets


class ComponentContract(StrictModel):
    value: NonEmptyText
    footprint: str
    part_id: Identifier | None = None


class NetlistContract(StrictModel):
    components: Mapping[Identifier, ComponentContract]
    nets: Mapping[NetName, tuple[Reference, ...]]
    unconnected_nets: Mapping[NetName, tuple[Reference, ...]] = Field(default_factory=dict)
    dnp_components: tuple[Identifier, ...] = ()
    component_symbols: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)
    pin_functions: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    pin_electrical_types: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    component_pin_numbers: Mapping[Identifier, tuple[NonEmptyText, ...]] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def separate_native_unconnected_nets(
        cls, value: NetlistRawValue, info: ValidationInfo
    ) -> object:
        return normalize_native_unconnected_nets(value, info)
