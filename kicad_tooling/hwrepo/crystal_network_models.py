"""Project-authored crystal-network requirements and native coverage records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    CapacitancePf,
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCapacitancePf,
    Reference,
    StrictModel,
)


class CrystalLoadCapRequirement(StrictModel):
    """Exact identity, pins, and accepted nominal value for one crystal load capacitor."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    signal_pin: Reference
    reference_pin: Reference
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf

    @model_validator(mode="after")
    def exact_component_pins_and_range(self) -> CrystalLoadCapRequirement:
        prefix = f"{self.reference}.".casefold()
        if not self.signal_pin.casefold().startswith(
            prefix
        ) or not self.reference_pin.casefold().startswith(prefix):
            raise ValueError("Crystal load-capacitor pins must belong to the declared component")
        if self.signal_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("Crystal load-capacitor signal and reference pins must differ")
        if self.minimum_nominal_capacitance_pf > self.maximum_nominal_capacitance_pf:
            raise ValueError("Crystal load-capacitor nominal capacitance range is reversed")
        return self


class CrystalNetworkRequirement(StrictModel):
    """Reviewed Pierce crystal topology and nominal effective-load requirement."""

    oscillator_reference: Identifier
    expected_oscillator_value: NonEmptyText
    expected_oscillator_symbol: NonEmptyText
    expected_oscillator_footprint: NonEmptyText
    oscillator_input_pin: Reference
    oscillator_output_pin: Reference
    resonator_reference: Identifier
    expected_resonator_value: NonEmptyText
    expected_resonator_symbol: NonEmptyText
    expected_resonator_footprint: NonEmptyText
    resonator_input_pin: Reference
    resonator_output_pin: Reference
    load_capacitors: Annotated[
        tuple[CrystalLoadCapRequirement, ...], Field(min_length=2, max_length=2)
    ]
    reference_net: NetName
    minimum_target_load_pf: CapacitancePf
    maximum_target_load_pf: CapacitancePf
    minimum_stray_capacitance_pf: NonNegativeCapacitancePf
    maximum_stray_capacitance_pf: NonNegativeCapacitancePf
    basis: NonEmptyText

    @model_validator(mode="after")
    def unique_roles_and_ordered_ranges(self) -> CrystalNetworkRequirement:
        if self.oscillator_reference.casefold() == self.resonator_reference.casefold():
            raise ValueError("Crystal oscillator and resonator references must differ")
        if self.oscillator_input_pin.casefold() == self.oscillator_output_pin.casefold():
            raise ValueError("Crystal oscillator input and output pins must differ")
        if self.resonator_input_pin.casefold() == self.resonator_output_pin.casefold():
            raise ValueError("Crystal resonator pins must differ")
        pins = (
            self.oscillator_input_pin,
            self.oscillator_output_pin,
            self.resonator_input_pin,
            self.resonator_output_pin,
            *(pin for cap in self.load_capacitors for pin in (cap.signal_pin, cap.reference_pin)),
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Crystal network pin mappings must be unique")
        if any(
            not pin.casefold().startswith(f"{self.oscillator_reference}.".casefold())
            for pin in (self.oscillator_input_pin, self.oscillator_output_pin)
        ):
            raise ValueError("Crystal oscillator pins must belong to the declared oscillator")
        if any(
            not pin.casefold().startswith(f"{self.resonator_reference}.".casefold())
            for pin in (self.resonator_input_pin, self.resonator_output_pin)
        ):
            raise ValueError("Crystal resonator pins must belong to the declared resonator")
        references = (
            self.oscillator_reference,
            self.resonator_reference,
            *(item.reference for item in self.load_capacitors),
        )
        if len({reference.casefold() for reference in references}) != len(references):
            raise ValueError("Crystal network component references must be unique")
        if self.minimum_target_load_pf > self.maximum_target_load_pf:
            raise ValueError("Crystal target load capacitance range is reversed")
        if self.minimum_stray_capacitance_pf > self.maximum_stray_capacitance_pf:
            raise ValueError("Crystal stray capacitance range is reversed")
        return self


class CrystalNetworkMap(StrictModel):
    """Project-authored scope for deterministic crystal load-network checks."""

    basis: NonEmptyText
    networks: Annotated[tuple[CrystalNetworkRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_network_references(self) -> CrystalNetworkMap:
        references = [item.oscillator_reference.casefold() for item in self.networks]
        if len(set(references)) != len(references):
            raise ValueError("Crystal network oscillator references must be unique")
        all_components = [
            reference.casefold()
            for item in self.networks
            for reference in (
                item.oscillator_reference,
                item.resonator_reference,
                *(cap.reference for cap in item.load_capacitors),
            )
        ]
        if len(set(all_components)) != len(all_components):
            raise ValueError("A component can belong to only one mapped crystal network")
        return self


class CrystalNetworkCoverageEntry(StrictModel):
    """One mapped oscillator network compared with native netlist assignments."""

    oscillator_reference: Identifier
    resonator_reference: Identifier
    load_capacitor_references: tuple[Identifier, ...]
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    target_minimum_load_pf: CapacitancePf
    target_maximum_load_pf: CapacitancePf
    minimum_stray_capacitance_pf: NonNegativeCapacitancePf
    maximum_stray_capacitance_pf: NonNegativeCapacitancePf
    basis: NonEmptyText
    extra_capacitor_references: tuple[Identifier, ...] = ()
    extra_capacitor_pin_nets: Mapping[Identifier, tuple[NonEmptyText, ...]] = Field(
        default_factory=dict
    )
    formula: Literal["C1*C2/(C1+C2) + Cstray"] = "C1*C2/(C1+C2) + Cstray"
    node_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    capacitance_pf: Mapping[Identifier, CapacitancePf] = Field(default_factory=dict)
    calculated_minimum_load_pf: CapacitancePf | None = None
    calculated_maximum_load_pf: CapacitancePf | None = None
    issues: tuple[NonEmptyText, ...] = ()


class CrystalNetworkCoverageReport(StrictModel):
    """Coverage of authored crystal load-network requirements against native evidence."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped Pierce networks are compared. The nominal load estimate does "
        "not establish oscillator startup, frequency accuracy, drive level, ESR margin, "
        "parasitics, layout quality, or environmental performance."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[CrystalNetworkCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> CrystalNetworkCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured crystal network coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked crystal network coverage must explain the evidence gap")
        return self
