"""Project-authored requirements and coverage for signal-input dividers."""

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


class SignalDividerCoverageEntry(StrictModel):
    """One mapped divider compared with the exact exported native netlist."""

    id: Identifier
    receiver_reference: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    source_net: NetName
    input_net: NetName
    reference_net: NetName
    formula: Literal["Vsource*Rbottom/(Rtop+Rbottom)"] = "Vsource*Rbottom/(Rtop+Rbottom)"
    nominal_resistance_ohms: Mapping[Identifier, ElectricalPositive] = Field(default_factory=dict)
    calculated_input_minimum_v: NonNegativeMeasure | None = None
    calculated_input_maximum_v: NonNegativeMeasure | None = None
    source_minimum_v: NonNegativeMeasure
    source_maximum_v: NonNegativeMeasure
    target_input_minimum_v: NonNegativeMeasure
    target_input_maximum_v: NonNegativeMeasure
    pin_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class SignalDividerCoverageReport(StrictModel):
    """Coverage of explicitly mapped ADC/sensor divider requirements."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped, positive-source, two-resistor divider networks are checked. "
        "The nominal calculation assumes an unloaded high-impedance input and does not establish "
        "component tolerance, transient response, protection, or PCB behavior."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[SignalDividerCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> SignalDividerCoverageReport:
        if self.status == "NOT_REQUESTED" and self.entries:
            raise ValueError("Not-requested signal-divider coverage cannot contain entries")
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured signal-divider coverage must bind a native netlist hash")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            has_incomplete_entry = any(entry.status == "INCOMPLETE" for entry in self.entries)
            status_matches_entries = (
                bool(self.entries) and not has_incomplete_entry
                if self.status == "COMPLETE"
                else has_incomplete_entry
            )
            if not status_matches_entries:
                raise ValueError("Signal-divider coverage status must match its entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked signal-divider coverage must explain the evidence gap")
        return self


class SignalDividerResistorRequirement(StrictModel):
    """Exact resistor identity, terminal roles, and accepted nominal value range."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    divider_pin: Reference
    outer_pin: Reference
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive

    @model_validator(mode="after")
    def pins_and_range_are_valid(self) -> SignalDividerResistorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not pin.casefold().startswith(prefix) for pin in (self.divider_pin, self.outer_pin)):
            raise ValueError("Divider resistor pins must belong to their declared component")
        if self.divider_pin.casefold() == self.outer_pin.casefold():
            raise ValueError("Divider resistor terminal pins must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("Divider resistor nominal range is reversed")
        return self


class SignalDividerRequirement(StrictModel):
    """One exact single-ended divider and its independently reviewed voltage window."""

    id: Identifier
    receiver_reference: Identifier
    expected_receiver_value: NonEmptyText
    expected_receiver_symbol: NonEmptyText
    expected_receiver_footprint: NonEmptyText
    receiver_pin: Reference
    expected_receiver_pin_function: NonEmptyText
    expected_receiver_electrical_type: Literal["input"] = "input"
    source_net: NetName
    input_net: NetName
    reference_net: NetName
    upper_resistor: SignalDividerResistorRequirement
    lower_resistor: SignalDividerResistorRequirement
    minimum_source_voltage_v: NonNegativeMeasure
    maximum_source_voltage_v: NonNegativeMeasure
    minimum_input_voltage_v: NonNegativeMeasure
    maximum_input_voltage_v: NonNegativeMeasure
    basis: NonEmptyText

    @model_validator(mode="after")
    def mapped_topology_is_unique(self) -> SignalDividerRequirement:
        if not self.receiver_pin.casefold().startswith(f"{self.receiver_reference}.".casefold()):
            raise ValueError("Signal-divider receiver pin must belong to its declared component")
        components = (
            self.receiver_reference,
            self.upper_resistor.reference,
            self.lower_resistor.reference,
        )
        if len({reference.casefold() for reference in components}) != len(components):
            raise ValueError("Signal-divider receiver and resistor references must be unique")
        pins = (
            self.receiver_pin,
            self.upper_resistor.divider_pin,
            self.upper_resistor.outer_pin,
            self.lower_resistor.divider_pin,
            self.lower_resistor.outer_pin,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Signal-divider mapped pins must be unique")
        nets = (self.source_net, self.input_net, self.reference_net)
        if len({net.casefold() for net in nets}) != len(nets):
            raise ValueError("Signal-divider source, input, and reference nets must differ")
        for minimum, maximum, description in (
            (self.minimum_source_voltage_v, self.maximum_source_voltage_v, "source"),
            (self.minimum_input_voltage_v, self.maximum_input_voltage_v, "input"),
        ):
            if minimum > maximum:
                raise ValueError(f"Signal-divider {description} voltage range is reversed")
        if self.minimum_source_voltage_v < 0 or self.minimum_input_voltage_v < 0:
            raise ValueError("This signal-divider check supports non-negative voltage ranges only")
        if self.upper_resistor.outer_pin.casefold() == self.lower_resistor.outer_pin.casefold():
            raise ValueError("Signal-divider outer resistor pins must terminate on separate nets")
        return self


class SignalDividerMap(StrictModel):
    """Project-owned scope for deterministic single-ended input-divider checks."""

    basis: NonEmptyText
    dividers: Annotated[tuple[SignalDividerRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_dividers_and_components(self) -> SignalDividerMap:
        if len({item.id.casefold() for item in self.dividers}) != len(self.dividers):
            raise ValueError("Signal-divider IDs must be unique")
        components = [
            reference.casefold()
            for item in self.dividers
            for reference in (
                item.receiver_reference,
                item.upper_resistor.reference,
                item.lower_resistor.reference,
            )
        ]
        if len(set(components)) != len(components):
            raise ValueError("A component can belong to only one signal-divider map")
        return self
