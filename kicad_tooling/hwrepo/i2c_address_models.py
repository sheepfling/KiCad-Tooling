"""Project-owned I2C address maps and source-bound address coverage records."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NetName, NonEmptyText, Reference, StrictModel


class I2cAddressBitRequirement(StrictModel):
    """Reviewed mapping from one 7-bit responder-address bit to a symbol pin."""

    bit: Annotated[int, Field(ge=0, le=6)]
    pin: Reference
    function: NonEmptyText
    low_net: NetName
    high_net: NetName

    @model_validator(mode="after")
    def distinct_logic_nets(self) -> I2cAddressBitRequirement:
        if self.low_net == self.high_net:
            raise ValueError("I2C address bit low_net and high_net must differ")
        return self


class I2cResponderAddressRequirement(StrictModel):
    """Project-owned identity and static-address basis for one bus responder."""

    reference: Identifier
    expected_symbol: NonEmptyText
    sda_pin: Reference
    scl_pin: Reference
    mode: Literal["fixed", "strapped", "dynamic"]
    address: Annotated[int, Field(ge=0, le=127)] | None = None
    address_bits: tuple[I2cAddressBitRequirement, ...] = ()
    basis: NonEmptyText

    @model_validator(mode="after")
    def address_source_is_explicit(self) -> I2cResponderAddressRequirement:
        prefix = f"{self.reference}."
        pins = (self.sda_pin, self.scl_pin, *(item.pin for item in self.address_bits))
        if self.sda_pin == self.scl_pin:
            raise ValueError("I2C responder SDA and SCL pins must differ")
        if any(not pin.casefold().startswith(prefix.casefold()) for pin in pins):
            raise ValueError("I2C responder pins must belong to its declared component")
        normalized_pins = [pin.casefold() for pin in pins]
        if len(set(normalized_pins)) != len(normalized_pins):
            raise ValueError("I2C responder signal and address pins must be unique")
        if len({item.pin.casefold() for item in self.address_bits}) != len(self.address_bits):
            raise ValueError("I2C address pin mappings must be unique")
        if len({item.bit for item in self.address_bits}) != len(self.address_bits):
            raise ValueError("I2C address bit positions must be unique")
        if self.mode == "fixed" and (self.address is None or self.address_bits):
            raise ValueError("Fixed I2C addresses need one authored address and no strap pins")
        if self.mode == "strapped" and (self.address is None or not self.address_bits):
            raise ValueError("Strapped I2C addresses need a base address and mapped address pins")
        if self.mode == "dynamic" and (self.address is not None or self.address_bits):
            raise ValueError("Dynamic I2C addresses cannot declare a static value or strap pins")
        return self


class I2cAddressSegmentRequirement(StrictModel):
    """One project-declared arbitration domain, such as a mux output segment."""

    id: Identifier
    sda_net: NetName
    scl_net: NetName
    responders: Annotated[tuple[I2cResponderAddressRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_signal_nets_and_responders(self) -> I2cAddressSegmentRequirement:
        if self.sda_net == self.scl_net:
            raise ValueError("I2C address segment SDA and SCL nets must differ")
        references = [item.reference.casefold() for item in self.responders]
        if len(set(references)) != len(references):
            raise ValueError("I2C responder references must be unique within a segment")
        return self


class I2cAddressMap(StrictModel):
    """Reviewed scope for deterministic static responder-address checks."""

    basis: NonEmptyText
    segments: Annotated[tuple[I2cAddressSegmentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_segments_and_responders(self) -> I2cAddressMap:
        if len({item.id.casefold() for item in self.segments}) != len(self.segments):
            raise ValueError("I2C address segment IDs must be unique")
        signal_pairs = [(item.sda_net, item.scl_net) for item in self.segments]
        if len(set(signal_pairs)) != len(signal_pairs):
            raise ValueError("I2C address segments must use unique SDA/SCL net pairs")
        signal_nets = [net for item in self.segments for net in (item.sda_net, item.scl_net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("I2C address segments cannot share signal nets")
        references = [
            responder.reference.casefold()
            for segment in self.segments
            for responder in segment.responders
        ]
        if len(set(references)) != len(references):
            raise ValueError("An I2C responder can be assigned to only one declared segment")
        return self


class I2cAddressBitEvidence(StrictModel):
    bit: Annotated[int, Field(ge=0, le=6)]
    pin: Reference
    expected_function: NonEmptyText
    observed_function: NonEmptyText | None = None
    nets: tuple[NetName, ...] = ()
    resolved_value: Literal[0, 1] | None = None


class I2cResponderAddressCoverageEntry(StrictModel):
    reference: Identifier
    segment_id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "DYNAMIC", "NOT_FITTED"]
    mode: Literal["fixed", "strapped", "dynamic"]
    expected_symbol: NonEmptyText
    observed_symbol: NonEmptyText | None = None
    sda_pin: Reference
    scl_pin: Reference
    sda_nets: tuple[NetName, ...] = ()
    scl_nets: tuple[NetName, ...] = ()
    expected_address: Annotated[int, Field(ge=0, le=127)] | None = None
    observed_address: Annotated[int, Field(ge=0, le=127)] | None = None
    address_bits: tuple[I2cAddressBitEvidence, ...] = ()
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class I2cAddressCoverageReport(StrictModel):
    """Coverage of an authored responder map against the native netlist."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only project-declared responders and segments are compared; this does not enumerate "
        "off-board, unlisted, or firmware-addressed devices."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[I2cResponderAddressCoverageEntry, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> I2cAddressCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured I2C address coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked I2C address coverage must explain the evidence gap")
        return self
