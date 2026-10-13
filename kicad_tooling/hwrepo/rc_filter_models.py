"""Typed project requirements for first-order RC filter checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    CapacitancePf,
    Digest,
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    ResistorReference,
    StrictModel,
)


class RcFilterCoverageEntry(StrictModel):
    """One explicitly mapped first-order RC filter checked against the native netlist."""

    id: Identifier
    resistor_reference: ResistorReference
    capacitor_reference: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    input_net: NetName
    filtered_net: NetName
    reference_net: NetName
    formula: Literal["1/(2*pi*R*C)"] = "1/(2*pi*R*C)"
    resistance_ohms: ElectricalPositive | None = None
    capacitance_pf: CapacitancePf | None = None
    calculated_corner_hz: ElectricalPositive | None = None
    target_minimum_corner_hz: ElectricalPositive
    target_maximum_corner_hz: ElectricalPositive
    nominal_resistance_range_ohms: tuple[ElectricalPositive, ElectricalPositive]
    nominal_capacitance_range_pf: tuple[CapacitancePf, CapacitancePf]
    pin_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    unlisted_parallel_components: tuple[Identifier, ...] = ()
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class RcFilterCoverageReport(StrictModel):
    """Coverage of authored RC filter requirements against source-bound netlists."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped first-order series-resistor/shunt-capacitor low-pass networks "
        "are checked. Nominal cutoff estimates do not model source/load impedance, tolerances, "
        "transient behavior, or higher-order filters."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[RcFilterCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> RcFilterCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured RC filter coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked RC filter coverage must explain the evidence gap")
        return self


class RcFilterRequirement(StrictModel):
    """Reviewed identity, topology, values, and corner range for one RC low-pass."""

    id: Identifier
    resistor_reference: ResistorReference
    expected_resistor_symbol: NonEmptyText
    expected_resistor_footprint: NonEmptyText
    resistor_first_pin: Reference
    resistor_second_pin: Reference
    capacitor_reference: Identifier
    expected_capacitor_symbol: NonEmptyText
    expected_capacitor_footprint: NonEmptyText
    capacitor_signal_pin: Reference
    capacitor_reference_pin: Reference
    input_net: NetName
    filtered_net: NetName
    reference_net: NetName
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf
    minimum_target_corner_hz: ElectricalPositive
    maximum_target_corner_hz: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def complete_first_order_map(self) -> RcFilterRequirement:
        resistor_prefix = f"{self.resistor_reference}.".casefold()
        capacitor_prefix = f"{self.capacitor_reference}.".casefold()
        if any(
            not pin.casefold().startswith(resistor_prefix)
            for pin in (self.resistor_first_pin, self.resistor_second_pin)
        ):
            raise ValueError("RC filter resistor pins must belong to the declared resistor")
        if any(
            not pin.casefold().startswith(capacitor_prefix)
            for pin in (self.capacitor_signal_pin, self.capacitor_reference_pin)
        ):
            raise ValueError("RC filter capacitor pins must belong to the declared capacitor")
        pins = (
            self.resistor_first_pin,
            self.resistor_second_pin,
            self.capacitor_signal_pin,
            self.capacitor_reference_pin,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("RC filter pin mappings must be unique")
        if (
            len(
                {
                    self.input_net.casefold(),
                    self.filtered_net.casefold(),
                    self.reference_net.casefold(),
                }
            )
            != 3
        ):
            raise ValueError("RC filter input, filtered, and reference nets must be distinct")
        if self.resistor_reference.casefold() == self.capacitor_reference.casefold():
            raise ValueError("RC filter resistor and capacitor references must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("RC filter resistance range is reversed")
        if self.minimum_nominal_capacitance_pf > self.maximum_nominal_capacitance_pf:
            raise ValueError("RC filter capacitance range is reversed")
        if self.minimum_target_corner_hz > self.maximum_target_corner_hz:
            raise ValueError("RC filter target corner range is reversed")
        return self


class RcFilterMap(StrictModel):
    """Project-authored scope for deterministic first-order RC filter checks."""

    filters: Annotated[tuple[RcFilterRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_filter_parts(self) -> RcFilterMap:
        if len({item.id.casefold() for item in self.filters}) != len(self.filters):
            raise ValueError("RC filter IDs must be unique")
        references = [
            reference.casefold()
            for item in self.filters
            for reference in (item.resistor_reference, item.capacitor_reference)
        ]
        if len(set(references)) != len(references):
            raise ValueError("A component can belong to only one mapped RC filter")
        return self
