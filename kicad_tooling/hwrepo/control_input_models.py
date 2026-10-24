"""Project-owned control-input requirements and source-bound review coverage."""

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
    Reference,
    RepositoryPath,
    ResistorReference,
    StrictModel,
)


class ControlInputBiasHeuristicEntry(StrictModel):
    """One connected-control heuristic candidate and its authored-contract coverage."""

    net: NetName
    control_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    status: Literal["COVERED", "OPEN"]
    signal_id: Identifier | None = None
    bias_mode: Literal["local", "internal", "external", "not_required"] | None = None
    bias_basis: NonEmptyText | None = None
    bias_reason: NonEmptyText | None = None
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def coverage_has_exact_intent(self) -> ControlInputBiasHeuristicEntry:
        if self.status == "COVERED" and (
            self.signal_id is None
            or self.bias_mode is None
            or self.bias_basis is None
            or self.issues
        ):
            raise ValueError("Covered control-bias candidates need a clean authored requirement")
        if self.status == "OPEN" and not self.issues:
            raise ValueError("Open control-bias candidates must explain why coverage is incomplete")
        return self


class ControlInputBiasHeuristicCoverage(StrictModel):
    """Source-bound accounting for control-bias prompts resolved by reviewed requirements."""

    status: Literal[
        "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
    ] = "NOT_CONFIGURED"
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[ControlInputBiasHeuristicEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_coverage(self) -> ControlInputBiasHeuristicCoverage:
        if (self.source_path is None) != (self.source_sha256 is None):
            raise ValueError("Control-input contract path and hash must be recorded together")
        if self.entries and self.netlist_sha256 is None:
            raise ValueError("Control-bias candidate coverage needs its native netlist hash")
        nets = [item.net.casefold() for item in self.entries]
        if len(nets) != len(set(nets)):
            raise ValueError("Control-bias coverage entries need unique nets")
        if self.status == "COMPLETE" and any(item.status != "COVERED" for item in self.entries):
            raise ValueError("Complete control-bias coverage cannot contain open candidates")
        if self.status == "OPEN" and not any(item.status == "OPEN" for item in self.entries):
            raise ValueError("Open control-bias coverage needs an open candidate")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked control-bias coverage must explain the evidence gap")
        return self


ControlElectricalType = Literal[
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "passive",
    "free",
    "unspecified",
    "power_in",
    "power_out",
    "open_collector",
    "open_emitter",
    "no_connect",
]


class ControlPinRequirement(StrictModel):
    """One exact control-signal endpoint and its KiCad library pin type."""

    role: Literal["controlled_input", "approved_driver", "external_interface"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    electrical_type: ControlElectricalType

    @model_validator(mode="after")
    def pin_belongs_to_reference(self) -> ControlPinRequirement:
        if self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
            raise ValueError("Control-signal pin must belong to its declared component")
        if self.role == "controlled_input" and self.electrical_type not in {
            "input",
            "bidirectional",
            "tri_state",
            "passive",
            "unspecified",
            "power_in",
        }:
            raise ValueError("A controlled input cannot use a power/output-only pin type")
        if self.role == "approved_driver" and self.electrical_type not in {
            "output",
            "bidirectional",
            "tri_state",
            "power_out",
            "open_collector",
            "open_emitter",
        }:
            raise ValueError("An approved control driver needs an output-capable pin type")
        return self


class ControlBiasResistorRequirement(StrictModel):
    """One exact fitted resistor path used to bias a declared control signal."""

    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    signal_net: NetName
    bias_net: NetName
    direction: Literal["pull_up", "pull_down"]
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_bias_path(self) -> ControlBiasResistorRequirement:
        if self.signal_net == self.bias_net:
            raise ValueError("A control-bias resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("Control-bias maximum resistance is below its minimum")
        return self


class ControlBiasArrayChannelRequirement(StrictModel):
    """One reviewed control-bias channel within an exact resistor-array part."""

    id: Identifier
    signal_pin: Reference
    bias_pin: Reference
    bias_net: NetName
    direction: Literal["pull_up", "pull_down"]
    nominal_ohms: ElectricalPositive
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def valid_bias_channel(self) -> ControlBiasArrayChannelRequirement:
        if self.signal_pin.casefold() == self.bias_pin.casefold():
            raise ValueError("Control-bias array channel pins must differ")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("Control-bias array maximum resistance is below its minimum")
        if not self.minimum_ohms <= self.nominal_ohms <= self.maximum_ohms:
            raise ValueError("Control-bias array nominal resistance is outside its reviewed range")
        return self


class ControlBiasResistorArrayRequirement(StrictModel):
    """Exact array identity and pin map for one or more local control-bias paths."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    expected_part_id: Identifier | None = None
    basis: NonEmptyText
    channels: Annotated[tuple[ControlBiasArrayChannelRequirement, ...], Field(min_length=1)]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def complete_pin_map(self) -> ControlBiasResistorArrayRequirement:
        prefix = f"{self.reference}."
        signal_pins = [channel.signal_pin for channel in self.channels]
        bias_pins = [channel.bias_pin for channel in self.channels]
        unique_bias_pins = tuple({pin.casefold(): pin for pin in bias_pins}.values())
        channel_pins = (*signal_pins, *unique_bias_pins)
        all_pins = (*channel_pins, *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix.casefold()) for pin in all_pins):
            raise ValueError("Control-bias array pins must belong to their component")
        if len({pin.casefold() for pin in signal_pins}) != len(signal_pins):
            raise ValueError("Control-bias array signal pins must be unique")
        if {pin.casefold() for pin in signal_pins} & {pin.casefold() for pin in bias_pins}:
            raise ValueError("A control-bias array pin cannot be both a signal and bias endpoint")
        if len({pin.casefold() for pin in all_pins}) != len(all_pins):
            raise ValueError("Control-bias array channel and unmapped pins must be unique")
        if len({channel.id.casefold() for channel in self.channels}) != len(self.channels):
            raise ValueError("Control-bias array channel IDs must be unique")
        shared_bias_map: dict[str, tuple[str, str]] = {}
        for channel in self.channels:
            pin = channel.bias_pin.casefold()
            assignment = (channel.bias_net.casefold(), channel.direction)
            prior = shared_bias_map.setdefault(pin, assignment)
            if prior != assignment:
                raise ValueError("A shared control-bias array pin needs one net and direction")
        return self


class ControlLocalBiasRequirement(StrictModel):
    mode: Literal["local"]
    basis: NonEmptyText
    resistors: tuple[ControlBiasResistorRequirement, ...] = ()
    arrays: tuple[ControlBiasResistorArrayRequirement, ...] = ()

    @model_validator(mode="after")
    def valid_local_bias_paths(self) -> ControlLocalBiasRequirement:
        if not self.resistors and not self.arrays:
            raise ValueError("Local control bias needs at least one resistor or mapped array")
        references = [item.reference.casefold() for item in self.resistors]
        references.extend(item.reference.casefold() for item in self.arrays)
        if len(set(references)) != len(references):
            raise ValueError("Control-bias component references must be unique")
        return self


class ControlInternalBiasRequirement(StrictModel):
    mode: Literal["internal"]
    basis: NonEmptyText
    reason: NonEmptyText


class ControlExternalBiasRequirement(StrictModel):
    mode: Literal["external"]
    basis: NonEmptyText
    reason: NonEmptyText


class ControlNoBiasRequirement(StrictModel):
    mode: Literal["not_required"]
    basis: NonEmptyText
    reason: NonEmptyText


ControlBiasRequirement = Annotated[
    ControlLocalBiasRequirement
    | ControlInternalBiasRequirement
    | ControlExternalBiasRequirement
    | ControlNoBiasRequirement,
    Field(discriminator="mode"),
]


class ControlSignalRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    signal_net: NetName
    driver_policy: Literal["none", "single", "shared_open_drain", "reviewed_multiple"]
    driver_basis: NonEmptyText | None = None
    endpoints: Annotated[tuple[ControlPinRequirement, ...], Field(min_length=1)]
    bias: ControlBiasRequirement

    @model_validator(mode="after")
    def valid_endpoints_and_policy(self) -> ControlSignalRequirement:
        pins = [item.pin.casefold() for item in self.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Control-signal endpoint pins must be unique")
        if not any(item.role == "controlled_input" for item in self.endpoints):
            raise ValueError("A control signal needs at least one controlled input endpoint")
        drivers = [item for item in self.endpoints if item.role == "approved_driver"]
        if self.driver_policy == "none" and drivers:
            raise ValueError("A no-driver control signal cannot list approved drivers")
        if self.driver_policy == "single" and len(drivers) != 1:
            raise ValueError("A single-driver control signal needs exactly one approved driver")
        if self.driver_policy == "shared_open_drain":
            if len(drivers) < 2:
                raise ValueError("Shared open-drain control needs at least two approved drivers")
            if any(
                item.electrical_type not in {"open_collector", "open_emitter"} for item in drivers
            ):
                raise ValueError("Shared open-drain drivers need open-collector/emitter pin types")
        if self.driver_policy == "reviewed_multiple" and len(drivers) < 2:
            raise ValueError("Reviewed multiple-driver control needs at least two approved drivers")
        if self.driver_policy in {"shared_open_drain", "reviewed_multiple"}:
            if self.driver_basis is None:
                raise ValueError("A shared or multiple-driver control needs a review basis")
        elif self.driver_basis is not None:
            raise ValueError("A driver basis is only valid for shared or reviewed multiple drivers")
        if isinstance(self.bias, ControlLocalBiasRequirement) and any(
            item.signal_net != self.signal_net for item in self.bias.resistors
        ):
            raise ValueError("Local control-bias resistor signal nets must match the control net")
        return self


class ControlInputsAnalysis(StrictModel):
    """Project-authored reset, enable, and boot-strap connectivity requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    signals: Annotated[tuple[ControlSignalRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_signals_and_bias_components(self) -> ControlInputsAnalysis:
        if len({item.id.casefold() for item in self.signals}) != len(self.signals):
            raise ValueError("Control-signal IDs must be unique")
        if len({item.signal_net for item in self.signals}) != len(self.signals):
            raise ValueError("Each control-signal net must have one requirement group")
        pins = [endpoint.pin.casefold() for signal in self.signals for endpoint in signal.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Control-signal endpoint pins cannot be reused")
        resistor_refs = [
            resistor.reference.casefold()
            for signal in self.signals
            if isinstance(signal.bias, ControlLocalBiasRequirement)
            for resistor in (*signal.bias.resistors, *signal.bias.arrays)
        ]
        if len(set(resistor_refs)) != len(resistor_refs):
            raise ValueError("Control-bias component references cannot be reused")
        return self
