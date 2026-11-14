"""Project-authored external-protection requirements and source-bound coverage."""

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
    maximum_channel_capacitance_pf: CapacitancePf | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    capacitance_basis: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def distinct_component_pins(self) -> ExternalProtectionChannelRequirement:
        if self.signal_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("Protection channel signal and reference pins must differ")
        if (
            self.signal_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
            or self.reference_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
        ):
            raise ValueError("Protection channel pins must belong to the declared device")
        if (self.maximum_channel_capacitance_pf is None) != (self.capacitance_basis is None):
            raise ValueError(
                "Protection channel capacitance and its source basis must be declared together"
            )
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
    maximum_signal_capacitance_pf: CapacitancePf | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    capacitance_limit_basis: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def complete_protection_disposition(self) -> ExternalProtectionInterfaceRequirement:
        if not self.connector_pin.casefold().startswith(f"{self.connector_reference}.".casefold()):
            raise ValueError("External interface pin must belong to its connector")
        if self.disposition == "required" and not self.channels:
            raise ValueError("Required external protection needs at least one mapped channel")
        if self.disposition == "not_required" and self.channels:
            raise ValueError("Not-required external protection cannot map device channels")
        has_capacitance_limit = self.maximum_signal_capacitance_pf is not None
        if has_capacitance_limit != (self.capacitance_limit_basis is not None):
            raise ValueError(
                "Signal capacitance limit and its project basis must be declared together"
            )
        channel_capacitance = tuple(
            channel.maximum_channel_capacitance_pf is not None for channel in self.channels
        )
        if any(channel_capacitance) != has_capacitance_limit or (
            has_capacitance_limit and not all(channel_capacitance)
        ):
            raise ValueError(
                "A capacitance-reviewed interface needs a limit and a maximum for every channel"
            )
        if has_capacitance_limit and self.disposition != "required":
            raise ValueError("Only required protection channels can have a capacitance budget")
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
    expected_value: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
        cap_review_by_net: dict[
            str,
            tuple[float | None, str | None, dict[tuple[str, str], tuple[float, str]]],
        ] = {}
        for interface in self.interfaces:
            net_key = interface.signal_net
            if interface.disposition == "required":
                current = cap_review_by_net.setdefault(
                    net_key,
                    (
                        interface.maximum_signal_capacitance_pf,
                        interface.capacitance_limit_basis,
                        {},
                    ),
                )
                if current[:2] != (
                    interface.maximum_signal_capacitance_pf,
                    interface.capacitance_limit_basis,
                ):
                    raise ValueError(
                        "Protection interfaces on one signal net must share the same "
                        "capacitance-review decision, limit, and basis"
                    )
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
                if channel.maximum_channel_capacitance_pf is not None:
                    if device.expected_value is None:
                        raise ValueError(
                            "Capacitance-reviewed protection devices need an exact expected value"
                        )
                    ratings = cap_review_by_net[net_key][2]
                    channel_key = (
                        channel.device_reference.casefold(),
                        channel.signal_pin.casefold(),
                    )
                    rating = (
                        channel.maximum_channel_capacitance_pf,
                        channel.capacitance_basis or "",
                    )
                    existing = ratings.get(channel_key)
                    if existing is not None and existing != rating:
                        raise ValueError(
                            "A protection channel on one signal net must have one capacitance "
                            "rating and source basis"
                        )
                    ratings[channel_key] = rating
        if used_devices != set(device_map):
            raise ValueError("Every declared protection device must serve a mapped channel")
        return self


class ExternalProtectionCapacitanceChannelEvidence(StrictModel):
    """Project-authored maximum tied to the exact native component value."""

    device_reference: Identifier
    signal_pin: Reference
    expected_value: NonEmptyText
    observed_value: NonEmptyText
    maximum_channel_capacitance_pf: CapacitancePf
    capacitance_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_value_is_source_matched(self) -> ExternalProtectionCapacitanceChannelEvidence:
        if self.expected_value != self.observed_value:
            raise ValueError("Capacitance evidence requires an exact native component value match")
        return self


class ExternalProtectionCapacitanceReview(StrictModel):
    """Source-bound aggregate of reviewed channel maxima against a project budget."""

    signal_net: NetName
    maximum_signal_capacitance_pf: CapacitancePf
    total_channel_capacitance_pf: CapacitancePf
    capacitance_limit_basis: NonEmptyText
    channels: Annotated[
        tuple[ExternalProtectionCapacitanceChannelEvidence, ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def aggregate_matches_channels(self) -> ExternalProtectionCapacitanceReview:
        from decimal import Decimal

        keys = [
            (item.device_reference.casefold(), item.signal_pin.casefold()) for item in self.channels
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("Capacitance review channels must be unique per device signal pin")
        total = sum(
            (Decimal(str(item.maximum_channel_capacitance_pf)) for item in self.channels),
            Decimal(0),
        )
        if total != Decimal(str(self.total_channel_capacitance_pf)):
            raise ValueError("Capacitance review total must equal its unique channel maxima")
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
    capacitance_reviews: tuple[ExternalProtectionCapacitanceReview, ...] = Field(
        default_factory=tuple,
        exclude_if=lambda value: not value,
    )
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def evidence_is_source_bound(self) -> ExternalProtectionCoverageReport:
        if self.status == "NOT_REQUESTED" and self.entries:
            raise ValueError("Not-requested external-protection coverage cannot contain entries")
        if self.status == "NOT_REQUESTED" and self.capacitance_reviews:
            raise ValueError("Not-requested external protection cannot contain capacitance reviews")
        if self.capacitance_reviews and self.status not in {
            "COMPLETE",
            "INCOMPLETE",
            "UNDECLARED",
        }:
            raise ValueError("Capacitance reviews require admitted source-bound coverage")
        reviewed_nets = [item.signal_net for item in self.capacitance_reviews]
        if len(set(reviewed_nets)) != len(reviewed_nets):
            raise ValueError(
                "External-protection capacitance reviews must be unique per signal net"
            )
        for review in self.capacitance_reviews:
            mapped_devices = {
                reference.casefold()
                for entry in self.entries
                if entry.signal_net == review.signal_net and entry.status == "PROTECTED"
                for reference in entry.device_references
            }
            if (
                not mapped_devices
                or not {item.device_reference.casefold() for item in review.channels}
                <= mapped_devices
            ):
                raise ValueError(
                    "Capacitance reviews must use channels from protected coverage entries"
                )
        if self.status in {"COMPLETE", "INCOMPLETE", "UNDECLARED"} and (
            self.netlist_sha256 is None
        ):
            raise ValueError("Configured external-protection coverage needs a native netlist hash")
        if self.status in {"COMPLETE", "INCOMPLETE", "UNDECLARED"}:
            entry_statuses = {entry.status for entry in self.entries}
            has_incomplete_entry = bool(entry_statuses & {"INCOMPLETE", "STALE"})
            has_undeclared_entry = "UNDECLARED" in entry_statuses
            if self.status == "COMPLETE":
                status_matches_entries = bool(self.entries) and not (
                    has_incomplete_entry or has_undeclared_entry
                )
            elif self.status == "INCOMPLETE":
                status_matches_entries = has_incomplete_entry
            else:
                status_matches_entries = has_undeclared_entry and not has_incomplete_entry
            if not status_matches_entries:
                raise ValueError("External-protection coverage status must match its entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked external-protection coverage must explain the evidence gap")
        if (self.electrical_contract_path is None) != (self.electrical_contract_sha256 is None):
            raise ValueError("Electrical contract path and digest must be bound together")
        return self


def external_protection_netlist_binding_issue(
    coverage: ExternalProtectionCoverageReport,
    current_netlist_sha256: Digest | None,
) -> str | None:
    """Explain when positive coverage is not bound to the current native netlist."""
    if coverage.status not in {"COMPLETE", "INCOMPLETE", "UNDECLARED"}:
        return None
    if current_netlist_sha256 is None or coverage.netlist_sha256 != current_netlist_sha256:
        return "External-protection coverage uses a different or unavailable native netlist hash."
    return None
