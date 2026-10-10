"""Project-authored external-protection requirements and source-bound coverage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class ExternalProtectionChannelRequirement(StrictModel):
    """Reviewed TVS or clamp channel between one interface signal and its reference."""

    device_reference: Identifier
    signal_pin: Reference
    reference_pin: Reference
    reference_net: NetName

    @model_validator(mode="after")
    def distinct_component_pins(self) -> ExternalProtectionChannelRequirement:
        if self.signal_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("Protection channel signal and reference pins must differ")
        if (
            self.signal_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
            or self.reference_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
        ):
            raise ValueError("Protection channel pins must belong to the declared device")
        return self


class ExternalProtectionInterfaceRequirement(StrictModel):
    """Project-authored protection disposition for one reviewed connector signal pin."""

    connector_reference: Identifier
    expected_connector_symbol: NonEmptyText
    expected_connector_footprint: NonEmptyText
    connector_pin: Reference
    signal_net: NetName
    disposition: Literal["required", "not_required"]
    basis: NonEmptyText
    channels: tuple[ExternalProtectionChannelRequirement, ...] = ()

    @model_validator(mode="after")
    def complete_protection_disposition(self) -> ExternalProtectionInterfaceRequirement:
        if not self.connector_pin.casefold().startswith(f"{self.connector_reference}.".casefold()):
            raise ValueError("External interface pin must belong to its connector")
        if self.disposition == "required" and not self.channels:
            raise ValueError("Required external protection needs at least one mapped channel")
        if self.disposition == "not_required" and self.channels:
            raise ValueError("Not-required external protection cannot map device channels")
        channel_keys = [
            (item.device_reference.casefold(), item.signal_pin.casefold()) for item in self.channels
        ]
        if len(set(channel_keys)) != len(channel_keys):
            raise ValueError("External protection channels must be unique per device signal pin")
        return self


class ExternalProtectionDeviceRequirement(StrictModel):
    """Exact device identity and native pin-net disposition for mapped protection parts."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    pin_nets: Mapping[Reference, NetName]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_component_pin_disposition(self) -> ExternalProtectionDeviceRequirement:
        prefix = f"{self.reference}.".casefold()
        pins = (*self.pin_nets, *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix) for pin in pins):
            raise ValueError("Protection device pins must belong to the declared component")
        normalized = [pin.casefold() for pin in pins]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Protection device pins must have one unique disposition")
        if len(self.pin_nets) < 2:
            raise ValueError("A mapped protection device needs at least two assigned pins")
        return self


class ExternalProtectionMap(StrictModel):
    """Explicit requirements for protection or reviewed non-applicability at interfaces."""

    basis: NonEmptyText
    interfaces: Annotated[tuple[ExternalProtectionInterfaceRequirement, ...], Field(min_length=1)]
    devices: tuple[ExternalProtectionDeviceRequirement, ...] = ()

    @model_validator(mode="after")
    def map_devices_and_interfaces(self) -> ExternalProtectionMap:
        interface_pins = [item.connector_pin.casefold() for item in self.interfaces]
        if len(set(interface_pins)) != len(interface_pins):
            raise ValueError("External protection interface pins must be unique")
        device_map = {item.reference.casefold(): item for item in self.devices}
        if len(device_map) != len(self.devices):
            raise ValueError("External protection device references must be unique")
        used_devices: set[str] = set()
        for interface in self.interfaces:
            for channel in interface.channels:
                key = channel.device_reference.casefold()
                device = device_map.get(key)
                if device is None:
                    raise ValueError("Protection channel references an undeclared device")
                used_devices.add(key)
                if device.pin_nets.get(channel.signal_pin) != interface.signal_net:
                    raise ValueError("Protection signal pin must map to the interface signal net")
                if device.pin_nets.get(channel.reference_pin) != channel.reference_net:
                    raise ValueError(
                        "Protection reference pin must map to its declared reference net"
                    )
        if used_devices != set(device_map):
            raise ValueError("Every declared protection device must serve a mapped channel")
        return self


class ExternalProtectionCoverageEntry(StrictModel):
    connector_reference: Identifier
    connector_pin: Reference
    interface_signal: NonEmptyText | None = None
    signal_net: NetName | None = None
    observed_nets: tuple[NetName, ...] = ()
    status: Literal[
        "PROTECTED",
        "NOT_REQUIRED",
        "HANDLED_BY_EXISTING_CONTRACT",
        "UNDECLARED",
        "INCOMPLETE",
        "STALE",
    ]
    basis: NonEmptyText | None = None
    device_references: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class ExternalProtectionCoverageReport(StrictModel):
    """Coverage and exact pin checks for reviewed external-interface protection."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "UNDECLARED", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    scope: NonEmptyText = (
        "Only project-reviewed connector interface pins and explicitly mapped protector channels "
        "are compared; this does not infer a protection requirement from a signal name."
    )
    netlist_sha256: Digest | None = None
    electrical_contract_path: RepositoryPath | None = None
    electrical_contract_sha256: Digest | None = None
    entries: tuple[ExternalProtectionCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def evidence_is_source_bound(self) -> ExternalProtectionCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE", "UNDECLARED"} and (
            self.netlist_sha256 is None
        ):
            raise ValueError("Configured external-protection coverage needs a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked external-protection coverage must explain the evidence gap")
        if (self.electrical_contract_path is None) != (self.electrical_contract_sha256 is None):
            raise ValueError("Electrical contract path and digest must be bound together")
        return self
