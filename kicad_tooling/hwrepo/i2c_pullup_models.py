"""Project-owned I2C pull-up requirements and source-bound coverage records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .model_primitives import (
    CapacitancePf,
    Digest,
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    Reference,
    RepositoryPath,
    ResistorReference,
    StrictModel,
)


class I2cPullupHeuristicEntry(StrictModel):
    """One missing-pull-up hint and the exact authored requirement used to resolve it."""

    sda_net: NetName
    scl_net: NetName
    missing_lines: Annotated[tuple[Literal["SDA", "SCL"], ...], Field(min_length=1)]
    status: Literal["COVERED", "OPEN"]
    bus_id: Identifier | None = None
    check_ids: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def exact_requirement_is_recorded(self) -> I2cPullupHeuristicEntry:
        if self.sda_net.casefold() == self.scl_net.casefold():
            raise ValueError("I2C pull-up coverage needs distinct SDA and SCL nets")
        if len(set(self.missing_lines)) != len(self.missing_lines):
            raise ValueError("I2C missing-pull-up lines must be unique")
        if len(set(self.check_ids)) != len(self.check_ids):
            raise ValueError("I2C pull-up check IDs must be unique")
        if self.status == "COVERED" and (self.bus_id is None or not self.check_ids or self.issues):
            raise ValueError("Covered I2C hints need a clean exact authored requirement")
        if self.status == "COVERED" and self.bus_id is not None:
            required_checks = {
                f"i2c-pullup/{self.bus_id}/sda",
                f"i2c-pullup/{self.bus_id}/scl",
            }
            if not required_checks.issubset(self.check_ids):
                raise ValueError("Covered I2C hints need passing checks for both bus lines")
        if self.status == "OPEN" and not self.issues:
            raise ValueError("Open I2C hints must explain why coverage is incomplete")
        return self


class I2cPullupHeuristicCoverage(StrictModel):
    """Source-bound accounting for I2C pull-up hints resolved by authored requirements."""

    status: Literal[
        "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
    ] = "NOT_CONFIGURED"
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[I2cPullupHeuristicEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_coverage(self) -> I2cPullupHeuristicCoverage:
        if (self.source_path is None) != (self.source_sha256 is None):
            raise ValueError("I2C pull-up contract path and hash must be recorded together")
        if self.entries and self.netlist_sha256 is None:
            raise ValueError("I2C pull-up candidate coverage needs its native netlist hash")
        pairs = [(item.sda_net.casefold(), item.scl_net.casefold()) for item in self.entries]
        if len(pairs) != len(set(pairs)):
            raise ValueError("I2C pull-up coverage entries need unique ordered net pairs")
        if self.status == "COMPLETE" and any(item.status != "COVERED" for item in self.entries):
            raise ValueError("Complete I2C pull-up coverage cannot contain open candidates")
        if self.status == "OPEN" and not any(item.status == "OPEN" for item in self.entries):
            raise ValueError("Open I2C pull-up coverage needs an open candidate")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked I2C pull-up coverage must explain the evidence gap")
        if self.status == "BLOCKED" and any(item.status == "COVERED" for item in self.entries):
            raise ValueError("Blocked I2C pull-up coverage cannot resolve candidate prompts")
        return self


class I2cPullupArrayChannelRequirement(StrictModel):
    """Reviewed pin and nominal resistance mapping for one array channel."""

    id: Identifier
    signal_pin: Reference
    rail_pin: Reference
    signal_net: NetName
    rail_net: NetName
    resistance_ohms: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def distinct_channel_endpoints(self) -> I2cPullupArrayChannelRequirement:
        if self.signal_pin.casefold() == self.rail_pin.casefold():
            raise ValueError("I2C resistor-array channel signal and rail pins must differ")
        if self.signal_net == self.rail_net:
            raise ValueError("I2C resistor-array channel signal and rail nets must differ")
        return self


class I2cPullupArrayRequirement(StrictModel):
    """Exact component and complete pin disposition for a mapped resistor array."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    basis: NonEmptyText
    channels: Annotated[tuple[I2cPullupArrayChannelRequirement, ...], Field(min_length=1)]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def component_pin_dispositions_are_unique(self) -> I2cPullupArrayRequirement:
        prefix = f"{self.reference}."
        channel_pins = [
            pin for channel in self.channels for pin in (channel.signal_pin, channel.rail_pin)
        ]
        all_pins = (*channel_pins, *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix.casefold()) for pin in all_pins):
            raise ValueError("I2C resistor-array pins must belong to its component")
        normalized = [pin.casefold() for pin in all_pins]
        if len(set(normalized)) != len(normalized):
            raise ValueError("I2C resistor-array channel and unlisted pins must be unique")
        if len({channel.id.casefold() for channel in self.channels}) != len(self.channels):
            raise ValueError("I2C resistor-array channel IDs must be unique")
        return self


class I2cPullupInputVoltageLimit(StrictModel):
    """Reviewed maximum bus voltage for one exact native I2C input pin."""

    pin: Reference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    limit_kind: Literal["operating", "absolute_maximum"]
    maximum_bus_voltage_v: ElectricalPositive
    limit_basis: NonEmptyText

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("I2C voltage-limit pins must use COMPONENT.PIN form")
        return value


class I2cPullupVoltageCompatibilityRequirement(StrictModel):
    """Project-authored rail ceiling and exact input limits for one bus line."""

    input_scope_basis: NonEmptyText
    maximum_rail_voltage_v: ElectricalPositive
    rail_basis: NonEmptyText
    input_limits: Annotated[tuple[I2cPullupInputVoltageLimit, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_input_pins(self) -> I2cPullupVoltageCompatibilityRequirement:
        if len({item.pin.casefold() for item in self.input_limits}) != len(self.input_limits):
            raise ValueError("I2C voltage-limit input pins must be unique")
        return self


class I2cPullupElectricalWindow(StrictModel):
    """Reviewed I2C pull-up limits for sink current and RC rise time."""

    maximum_pullup_voltage_v: ElectricalPositive
    pullup_voltage_basis: NonEmptyText
    maximum_low_level_voltage_v: NonNegativeMeasure
    low_level_voltage_basis: NonEmptyText
    minimum_sink_current_ma: ElectricalPositive
    sink_current_basis: NonEmptyText
    maximum_bus_capacitance_pf: CapacitancePf
    bus_capacitance_basis: NonEmptyText
    maximum_rise_time_ns: ElectricalPositive
    rise_time_basis: NonEmptyText
    maximum_per_resistor_tolerance_percent: (
        Annotated[float, Field(gt=0, lt=100, allow_inf_nan=False)] | None
    ) = None
    resistor_tolerance_basis: NonEmptyText | None = None

    @model_validator(mode="after")
    def valid_pullup_voltage_window(self) -> I2cPullupElectricalWindow:
        if self.maximum_pullup_voltage_v <= self.maximum_low_level_voltage_v:
            raise ValueError(
                "I2C pull-up maximum voltage must exceed the maximum low-level voltage"
            )
        if (self.maximum_per_resistor_tolerance_percent is None) != (
            self.resistor_tolerance_basis is None
        ):
            raise ValueError("I2C resistor tolerance and its basis must be supplied together")
        return self


class I2cPullupLineRequirement(StrictModel):
    """Reviewed local pull-up topology and nominal equivalent range for one line."""

    net: NetName
    rail: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive
    voltage_compatibility: I2cPullupVoltageCompatibilityRequirement | None = None
    electrical_window: I2cPullupElectricalWindow | None = None

    @model_validator(mode="after")
    def valid_range(self) -> I2cPullupLineRequirement:
        if self.net == self.rail:
            raise ValueError("An I2C signal net and its pull-up rail must be distinct")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("I2C pull-up maximum resistance is below its minimum")
        if (
            self.electrical_window is not None
            and self.voltage_compatibility is not None
            and self.electrical_window.maximum_pullup_voltage_v
            != self.voltage_compatibility.maximum_rail_voltage_v
        ):
            raise ValueError(
                "I2C pull-up electrical-window and voltage-compatibility rail ceilings must match"
            )
        return self


class I2cPullupSeriesResistorRequirement(StrictModel):
    """Exact symbol, footprint, directed path, and nominal range for one chain leg."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    from_net: NetName
    to_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_series_leg(self) -> I2cPullupSeriesResistorRequirement:
        if self.from_net == self.to_net:
            raise ValueError("I2C series pull-up resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("I2C series resistor maximum is below its minimum")
        return self


class I2cPullupSeriesPathRequirement(StrictModel):
    """Reviewed ordered chain from one I2C signal net to its pull-up rail."""

    id: Identifier
    basis: NonEmptyText
    signal_net: NetName
    rail_net: NetName
    resistors: Annotated[tuple[I2cPullupSeriesResistorRequirement, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def ordered_simple_path(self) -> I2cPullupSeriesPathRequirement:
        if self.signal_net == self.rail_net:
            raise ValueError("I2C series pull-up signal and rail nets must differ")
        references = [item.reference.casefold() for item in self.resistors]
        if len(set(references)) != len(references):
            raise ValueError("I2C series pull-up resistor references must be unique")
        if self.resistors[0].from_net != self.signal_net:
            raise ValueError("I2C series pull-up path must start at its signal net")
        if self.resistors[-1].to_net != self.rail_net:
            raise ValueError("I2C series pull-up path must end at its declared rail")
        for first, second in zip(self.resistors, self.resistors[1:], strict=False):
            if first.to_net != second.from_net:
                raise ValueError("I2C series pull-up resistor legs must form one ordered path")
        path_nets = (self.signal_net, *(item.to_net for item in self.resistors))
        if len({net.casefold() for net in path_nets}) != len(path_nets):
            raise ValueError("I2C series pull-up path cannot revisit a net")
        return self


class I2cPullupBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    sda: I2cPullupLineRequirement
    scl: I2cPullupLineRequirement

    @model_validator(mode="after")
    def distinct_bus_nets(self) -> I2cPullupBusRequirement:
        if self.sda.net == self.scl.net:
            raise ValueError("I2C SDA and SCL requirements must name distinct signal nets")
        if self.sda.net == self.scl.rail or self.scl.net == self.sda.rail:
            raise ValueError("An I2C pull-up rail cannot be the other bus signal net")
        return self


class I2cPullupAnalysis(StrictModel):
    """Project-authored direct, series, and mapped-array I2C pull-up requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[I2cPullupBusRequirement, ...], Field(min_length=1)]
    arrays: tuple[I2cPullupArrayRequirement, ...] = ()
    series_paths: tuple[I2cPullupSeriesPathRequirement, ...] = ()

    @model_validator(mode="after")
    def unique_bus_ids_and_nets(self) -> I2cPullupAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("I2C pull-up bus IDs must be unique")
        signal_nets = [net for bus in self.buses for net in (bus.sda.net, bus.scl.net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("I2C pull-up signal nets must be unique across configured buses")
        line_pairs = {(line.net, line.rail) for bus in self.buses for line in (bus.sda, bus.scl)}
        array_references = [array.reference.casefold() for array in self.arrays]
        if len(set(array_references)) != len(array_references):
            raise ValueError("I2C resistor-array references must be unique")
        series_path_ids = [path.id.casefold() for path in self.series_paths]
        if len(set(series_path_ids)) != len(series_path_ids):
            raise ValueError("I2C series pull-up path IDs must be unique")
        series_references = [
            resistor.reference.casefold()
            for path in self.series_paths
            for resistor in path.resistors
        ]
        if len(set(series_references)) != len(series_references):
            raise ValueError("I2C series pull-up resistor references must be unique")
        if set(array_references) & set(series_references):
            raise ValueError("I2C resistor arrays and series paths cannot reuse a component")
        for array in self.arrays:
            for channel in array.channels:
                if (channel.signal_net, channel.rail_net) not in line_pairs:
                    raise ValueError(
                        "I2C resistor-array channels must match a configured signal/rail pair"
                    )
        for path in self.series_paths:
            if (path.signal_net, path.rail_net) not in line_pairs:
                raise ValueError(
                    "I2C series pull-up paths must match a configured signal/rail pair"
                )
        return self
