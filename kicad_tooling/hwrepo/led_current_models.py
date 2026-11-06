"""Project-authored LED operating-current requirements and evidence records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    Reference,
    ResistorReference,
    StrictModel,
)

LedTolerancePercent = Annotated[float, Field(ge=0, lt=100, allow_inf_nan=False)]


class LedCurrentResistorRequirement(StrictModel):
    """Exact fitted series resistor and reviewed nominal/tolerance bounds."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    outer_pin: Reference
    led_side_pin: Reference
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive
    maximum_tolerance_percent: LedTolerancePercent
    tolerance_basis: NonEmptyText

    @model_validator(mode="after")
    def pins_and_range_are_valid(self) -> LedCurrentResistorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(
            not pin.casefold().startswith(prefix) for pin in (self.outer_pin, self.led_side_pin)
        ):
            raise ValueError("LED current-limit resistor pins must belong to its component")
        if self.outer_pin.casefold() == self.led_side_pin.casefold():
            raise ValueError("LED current-limit resistor terminal pins must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("LED current-limit resistor nominal range is reversed")
        return self


class LedCurrentRequirement(StrictModel):
    """One exact two-pin LED and single-series-resistor DC current envelope."""

    id: Identifier
    led_reference: Identifier
    expected_led_value: NonEmptyText
    expected_led_symbol: NonEmptyText
    expected_led_footprint: NonEmptyText
    anode_pin: Reference
    cathode_pin: Reference
    expected_anode_function: NonEmptyText = "A"
    expected_cathode_function: NonEmptyText = "K"
    source_net: NetName
    return_net: NetName
    led_side_net: NetName
    resistor_leg: Literal["anode", "cathode"]
    resistor: LedCurrentResistorRequirement
    minimum_source_voltage_v: NonNegativeMeasure
    maximum_source_voltage_v: NonNegativeMeasure
    minimum_forward_voltage_v: NonNegativeMeasure
    maximum_forward_voltage_v: NonNegativeMeasure
    minimum_target_current_ma: NonNegativeMeasure
    maximum_target_current_ma: NonNegativeMeasure
    source_voltage_basis: NonEmptyText
    forward_voltage_basis: NonEmptyText
    target_current_basis: NonEmptyText

    @model_validator(mode="after")
    def mapped_topology_and_ranges_are_valid(self) -> LedCurrentRequirement:
        led_prefix = f"{self.led_reference}.".casefold()
        if any(
            not pin.casefold().startswith(led_prefix) for pin in (self.anode_pin, self.cathode_pin)
        ):
            raise ValueError("LED anode and cathode pins must belong to the declared LED")
        if self.anode_pin.casefold() == self.cathode_pin.casefold():
            raise ValueError("LED anode and cathode pins must differ")
        if self.led_reference.casefold() == self.resistor.reference.casefold():
            raise ValueError("LED and current-limit resistor references must differ")
        if self.source_net.casefold() == self.return_net.casefold():
            raise ValueError("LED source and return nets must differ")
        if self.led_side_net.casefold() in {
            self.source_net.casefold(),
            self.return_net.casefold(),
        }:
            raise ValueError("LED series-element, source, and return nets must differ")
        if self.minimum_source_voltage_v > self.maximum_source_voltage_v:
            raise ValueError("LED source-voltage range is reversed")
        if self.minimum_forward_voltage_v > self.maximum_forward_voltage_v:
            raise ValueError("LED forward-voltage range is reversed")
        if self.minimum_target_current_ma > self.maximum_target_current_ma:
            raise ValueError("LED target-current range is reversed")
        return self


class LedCurrentMap(StrictModel):
    """Explicit project scope for deterministic LED-current envelope checks."""

    basis: NonEmptyText
    leds: Annotated[tuple[LedCurrentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def mapped_components_are_unique(self) -> LedCurrentMap:
        if len({item.id.casefold() for item in self.leds}) != len(self.leds):
            raise ValueError("LED current-map IDs must be unique")
        references = [
            reference.casefold()
            for item in self.leds
            for reference in (item.led_reference, item.resistor.reference)
        ]
        if len(set(references)) != len(references):
            raise ValueError("A component can belong to only one LED current-map entry")
        return self


class LedCurrentRangeEntry(StrictModel):
    """One authored LED path compared with exact native schematic evidence."""

    id: Identifier
    status: Literal["MATCHED", "OUT_OF_RANGE", "INCOMPLETE"]
    led_reference: Identifier
    resistor_reference: ResistorReference
    map_sha256: Digest
    netlist_sha256: Digest | None
    source_net: NetName
    return_net: NetName
    led_side_net: NetName
    map_basis: NonEmptyText
    source_voltage_basis: NonEmptyText
    forward_voltage_basis: NonEmptyText
    target_current_basis: NonEmptyText
    source_minimum_v: NonNegativeMeasure
    source_maximum_v: NonNegativeMeasure
    forward_voltage_minimum_v: NonNegativeMeasure
    forward_voltage_maximum_v: NonNegativeMeasure
    target_current_minimum_ma: NonNegativeMeasure
    target_current_maximum_ma: NonNegativeMeasure
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive
    maximum_tolerance_percent: LedTolerancePercent
    tolerance_basis: NonEmptyText
    resistance_ohms: ElectricalPositive | None = None
    calculated_current_minimum_ma: NonNegativeMeasure | None = None
    calculated_current_maximum_ma: NonNegativeMeasure | None = None
    pin_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def status_matches_evidence(self) -> LedCurrentRangeEntry:
        if self.status == "MATCHED" and (
            self.issues
            or self.calculated_current_minimum_ma is None
            or self.calculated_current_maximum_ma is None
        ):
            raise ValueError("Matched LED current evidence needs complete, clear calculations")
        if self.status == "OUT_OF_RANGE" and (
            not self.issues
            or self.calculated_current_minimum_ma is None
            or self.calculated_current_maximum_ma is None
        ):
            raise ValueError("Out-of-range LED current evidence needs calculated bounds and issues")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete LED current evidence needs an issue")
        if (self.calculated_current_minimum_ma is None) != (
            self.calculated_current_maximum_ma is None
        ):
            raise ValueError("Calculated LED current bounds must be supplied together")
        return self
