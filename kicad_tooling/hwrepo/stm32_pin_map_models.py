"""Typed project contracts and coverage records for STM32/CubeMX pin maps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    RepositoryPath,
    Stm32PortPin,
    Stm32SymbolPin,
    StrictModel,
)


class Stm32PinRequirement(StrictModel):
    """Reviewed package-pad to KiCad-pin assignment and accepted CubeMX functions."""

    port_pin: Stm32PortPin
    symbol_pin: Stm32SymbolPin
    expected_net: NetName
    accepted_ioc_signals: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    accepted_ioc_gpio_labels: tuple[NonEmptyText | None, ...] | None

    @model_validator(mode="after")
    def explicit_gpio_label_scope(self) -> Stm32PinRequirement:
        if len({item.casefold() for item in self.accepted_ioc_signals}) != len(
            self.accepted_ioc_signals
        ):
            raise ValueError("Accepted CubeMX signals must be unique")
        if self.accepted_ioc_gpio_labels is not None and len(
            {
                "<absent>" if item is None else item.casefold()
                for item in self.accepted_ioc_gpio_labels
            }
        ) != len(self.accepted_ioc_gpio_labels):
            raise ValueError("Accepted CubeMX GPIO labels must be unique")
        if any(item.upper().startswith("GPIO_") for item in self.accepted_ioc_signals) and (
            self.accepted_ioc_gpio_labels is None
        ):
            raise ValueError(
                "Generic CubeMX GPIO signals require an explicit label expectation, including an absent-label expectation"
            )
        return self


class Stm32PinExclusion(StrictModel):
    """Reasoned package pin outside the project's CubeMX signal comparison."""

    port_pin: Stm32PortPin
    reason: NonEmptyText


class Stm32CubeMxPinMap(StrictModel):
    """Project-authored full package-pad map for one exact MCU and CubeMX file."""

    id: Identifier
    basis: NonEmptyText
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_part: NonEmptyText
    ioc_path: RepositoryPath
    package_pins: Annotated[tuple[Stm32PortPin, ...], Field(min_length=1)]
    pins: Annotated[tuple[Stm32PinRequirement, ...], Field(min_length=1)]
    exclusions: tuple[Stm32PinExclusion, ...] = ()

    @model_validator(mode="after")
    def complete_unique_package_coverage(self) -> Stm32CubeMxPinMap:
        if not self.ioc_path.casefold().endswith(".ioc"):
            raise ValueError("CubeMX pin maps must name a repository-local .ioc file")
        package = [item.casefold() for item in self.package_pins]
        mapped = [item.port_pin.casefold() for item in self.pins]
        excluded = [item.port_pin.casefold() for item in self.exclusions]
        if len(set(package)) != len(package):
            raise ValueError("CubeMX package-pin inventory must be unique")
        if len(set(mapped)) != len(mapped):
            raise ValueError("CubeMX mapped package pins must be unique")
        if len(set(excluded)) != len(excluded):
            raise ValueError("CubeMX excluded package pins must be unique")
        if set(mapped) & set(excluded):
            raise ValueError("A CubeMX package pin cannot be mapped and excluded")
        if set(mapped) | set(excluded) != set(package):
            raise ValueError("Every CubeMX package pin must be mapped or explicitly excluded")
        symbol_pins = [item.symbol_pin.casefold() for item in self.pins]
        if len(set(symbol_pins)) != len(symbol_pins):
            raise ValueError("CubeMX package pins must map to unique KiCad symbol pins")
        return self


class Stm32PinMapMismatch(StrictModel):
    """One exact package pin whose CubeMX or schematic evidence differs from contract."""

    map_id: Identifier
    reference: Identifier
    port_pin: Stm32PortPin
    symbol_pin: NonEmptyText
    expected_net: NetName
    observed_nets: tuple[NetName, ...]
    accepted_ioc_signals: tuple[NonEmptyText, ...]
    observed_ioc_signal: NonEmptyText | None
    accepted_ioc_gpio_labels: tuple[NonEmptyText | None, ...] | None
    observed_ioc_gpio_label: NonEmptyText | None
    ioc_path: RepositoryPath
    ioc_sha256: Digest
    map_sha256: Digest
    netlist_sha256: Digest
    issues: tuple[NonEmptyText, ...]


class Stm32UnmappedDevice(StrictModel):
    """Likely STM32 component found in the native netlist without a pin-map contract."""

    reference: Identifier
    observed_symbol: NonEmptyText | None = None
    observed_part: NonEmptyText
    netlist_sha256: Digest


class Stm32PinMapCoverageReport(StrictModel):
    """Coverage and source hashes for project-authored CubeMX pin-map comparisons."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    ioc_source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    mapped_pin_count: NonNegativeCount = 0
    excluded_pin_count: NonNegativeCount = 0
    mismatches: tuple[Stm32PinMapMismatch, ...] = ()
    unmapped_devices: tuple[Stm32UnmappedDevice, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def coverage_has_source_evidence(self) -> Stm32PinMapCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Evaluated STM32 pin-map coverage must bind a native netlist hash")
        if self.status == "COMPLETE" and self.map_sha256 is None:
            raise ValueError("Complete STM32 pin-map coverage requires an authored map hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked STM32 pin-map coverage must explain the evidence gap")
        if self.status == "DISABLED" and self.mode != "off":
            raise ValueError("Disabled STM32 pin-map coverage must record the off policy")
        return self
