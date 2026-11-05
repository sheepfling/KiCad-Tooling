"""Typed source projections for protocol signal pins assigned to named rails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .bus_signal_pairs import (
    ethernet_data_pair_function_role,
    ethernet_management_function_role,
    usb_signal_family_and_side,
)
from .bus_signal_roles import i2c_signal_role, i3c_signal_identity, usb_c_sbu_role
from .can_signal_functions import can_signal_role_and_channel
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    named_rail_pin_evidence_matches_source,
)
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role
from .serial_participants import serial_function_role_and_channel
from .spi_participants import spi_signal_role_and_channel

CAN_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.can_signal_on_named_rail"
I2C_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.i2c_signal_on_named_rail"
I3C_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.i3c_signal_on_named_rail"
SPI_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.spi_signal_on_named_rail"
SERIAL_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.serial_signal_on_named_rail"
ETHERNET_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.ethernet_signal_on_named_rail"
ETHERNET_MANAGEMENT_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = (
    "bus.ethernet_management_signal_on_named_rail"
)
USB_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.usb_signal_on_named_rail"
RS485_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.rs485_signal_on_named_rail"
USB_C_SBU_SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.usb_c_sbu_signal_on_named_rail"


def _current_pin_function(source: NamedRailPinSource) -> str:
    if not named_rail_pin_evidence_matches_source(source.observed, source.evidence):
        raise ValueError("Named-rail source pin must match its current native netlist")
    return source.evidence.function


@dataclass(frozen=True, slots=True)
class CanSignalNamedRailEvidence:
    """One CAN/FDCAN controller TX/RX signal pin on a named rail."""

    pin: NamedRailPinSource
    role: str
    channel: str

    def __post_init__(self) -> None:
        if can_signal_role_and_channel(_current_pin_function(self.pin)) != (
            self.role,
            self.channel,
        ):
            raise ValueError("CAN named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class I2cSignalNamedRailEvidence:
    """One I2C SDA/SCL signal pin on a named rail."""

    pin: NamedRailPinSource
    role: str

    def __post_init__(self) -> None:
        if i2c_signal_role(_current_pin_function(self.pin)) != self.role:
            raise ValueError("I2C named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class I3cSignalNamedRailEvidence:
    """One channel-specific I3C SDA/SCL signal pin on a named rail."""

    pin: NamedRailPinSource
    role: str
    channel: str | None

    def __post_init__(self) -> None:
        identity = i3c_signal_identity(_current_pin_function(self.pin))
        if identity is None or (identity.role, identity.channel) != (self.role, self.channel):
            raise ValueError("I3C named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class SpiSignalNamedRailEvidence:
    """One channel-specific SPI role pin on a named rail."""

    pin: NamedRailPinSource
    role: str
    channel: str

    def __post_init__(self) -> None:
        if spi_signal_role_and_channel(_current_pin_function(self.pin)) != (
            self.role,
            self.channel,
        ):
            raise ValueError("SPI named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class SerialSignalNamedRailEvidence:
    """One channel-specific UART/USART TX/RX pin on a named rail."""

    pin: NamedRailPinSource
    role: str
    channel: str

    def __post_init__(self) -> None:
        if serial_function_role_and_channel(_current_pin_function(self.pin)) != (
            self.role,
            self.channel,
        ):
            raise ValueError("Serial named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class EthernetSignalNamedRailEvidence:
    """One Ethernet TX/RX pair-side pin on a named rail."""

    pin: NamedRailPinSource
    direction: str
    side: str

    def __post_init__(self) -> None:
        if ethernet_data_pair_function_role(_current_pin_function(self.pin)) != (
            self.direction,
            self.side,
        ):
            raise ValueError("Ethernet named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class EthernetManagementSignalNamedRailEvidence:
    """One Ethernet MDC/MDIO management pin on a named rail."""

    pin: NamedRailPinSource
    role: str

    def __post_init__(self) -> None:
        if ethernet_management_function_role(_current_pin_function(self.pin)) != self.role:
            raise ValueError("Ethernet management evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class UsbSignalNamedRailEvidence:
    """One USB 2.0 or SuperSpeed differential pin on a named rail."""

    pin: NamedRailPinSource
    family: str
    side: str

    def __post_init__(self) -> None:
        if usb_signal_family_and_side(_current_pin_function(self.pin)) != (
            self.family,
            self.side,
        ):
            raise ValueError("USB named-rail evidence must match its current pin function")


@dataclass(frozen=True, slots=True)
class Rs485SignalNamedRailEvidence:
    """One explicitly identified RS-485 data function on a named rail."""

    pin: NamedRailPinSource
    role: Literal["tx", "rx"]
    identity_basis: str

    def __post_init__(self) -> None:
        observed = self.pin.observed
        reference = self.pin.evidence.reference
        if (
            rs485_data_pin_role(_current_pin_function(self.pin)) != self.role
            or explicit_rs485_transceiver_identity(observed, reference) != self.identity_basis
        ):
            raise ValueError("RS-485 named-rail evidence must match its current transceiver")


def usb_c_sbu_pair_is_complete(pin_source: NamedRailPinSource) -> bool:
    """Check that one source pin belongs to the complete native SBU pair."""
    if not named_rail_pin_evidence_matches_source(pin_source.observed, pin_source.evidence):
        return False
    evidence = pin_source.evidence
    sbu_pins: dict[str, list[str]] = {"SBU1": [], "SBU2": []}
    for pin, function in pin_source.observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = usb_c_sbu_role(function)
        if (
            separator
            and number
            and reference.casefold() == evidence.reference.casefold()
            and role in sbu_pins
        ):
            sbu_pins[role].append(pin)

    inventory = set(evidence.inventory)
    return all(len(sbu_pins[role]) == 1 for role in ("SBU1", "SBU2")) and all(
        pin.rpartition(".")[2].casefold() in inventory for pins in sbu_pins.values() for pin in pins
    )


@dataclass(frozen=True, slots=True)
class UsbCSbuSignalNamedRailEvidence:
    """One USB-C SBU function on a named rail with its complete peer pair."""

    pin: NamedRailPinSource
    role: str

    def __post_init__(self) -> None:
        if usb_c_sbu_role(_current_pin_function(self.pin)) != self.role:
            raise ValueError("USB-C SBU evidence must match its current pin function")
        if not usb_c_sbu_pair_is_complete(self.pin):
            raise ValueError("USB-C SBU evidence must match its complete native pin pair")


NamedRailSignalEvidence: TypeAlias = (
    CanSignalNamedRailEvidence
    | I2cSignalNamedRailEvidence
    | I3cSignalNamedRailEvidence
    | SpiSignalNamedRailEvidence
    | SerialSignalNamedRailEvidence
    | EthernetSignalNamedRailEvidence
    | EthernetManagementSignalNamedRailEvidence
    | UsbSignalNamedRailEvidence
    | Rs485SignalNamedRailEvidence
    | UsbCSbuSignalNamedRailEvidence
)


def _common_evidence(source: NamedRailSignalEvidence) -> dict[str, tuple[str, ...]]:
    pin = source.pin.evidence
    return {
        "pin": (pin.pin,),
        "pin_function": (pin.function,),
        "assigned_net": (pin.net_name,),
        "net_label_role_clue": (pin.rail_role,),
        "component_pin_inventory": pin.inventory,
    }


def project_named_rail_signal_evidence(
    source: NamedRailSignalEvidence,
) -> CandidateEvidenceProjection:
    """Project a protocol-specific source into its established report schema."""
    source.__post_init__()
    evidence = _common_evidence(source)
    if isinstance(source, CanSignalNamedRailEvidence):
        rule_id = CAN_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "pin_role": (source.role,),
                "can_channel": (source.channel,),
            }
        )
    elif isinstance(source, I2cSignalNamedRailEvidence):
        rule_id = I2C_SIGNAL_NAMED_RAIL_RULE_ID
        evidence["pin_role"] = (source.role,)
    elif isinstance(source, I3cSignalNamedRailEvidence):
        rule_id = I3C_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "i3c_role": (source.role,),
                "i3c_channel": (source.channel or "unindexed",),
            }
        )
    elif isinstance(source, SpiSignalNamedRailEvidence):
        rule_id = SPI_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "pin_role": (source.role,),
                "spi_channel": (source.channel,),
            }
        )
    elif isinstance(source, SerialSignalNamedRailEvidence):
        rule_id = SERIAL_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "pin_role": (source.role,),
                "serial_channel": (source.channel,),
            }
        )
    elif isinstance(source, EthernetSignalNamedRailEvidence):
        rule_id = ETHERNET_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "ethernet_direction": (source.direction,),
                "ethernet_pair_side": (source.side,),
            }
        )
    elif isinstance(source, EthernetManagementSignalNamedRailEvidence):
        rule_id = ETHERNET_MANAGEMENT_SIGNAL_NAMED_RAIL_RULE_ID
        evidence["ethernet_management_role"] = (source.role,)
    elif isinstance(source, UsbSignalNamedRailEvidence):
        rule_id = USB_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "usb_signal_family": (source.family,),
                "usb_pair_side": (source.side,),
            }
        )
    elif isinstance(source, Rs485SignalNamedRailEvidence):
        rule_id = RS485_SIGNAL_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "rs485_data_role": (source.role,),
                "identity_basis": (source.identity_basis,),
            }
        )
    else:
        rule_id = USB_C_SBU_SIGNAL_NAMED_RAIL_RULE_ID
        evidence["usb_c_sbu_role"] = (source.role,)
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class NamedRailSignalCandidate(Candidate):
    """Candidate whose protocol role and rail pin remain source-bound."""

    source_evidence: NamedRailSignalEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: NamedRailSignalEvidence,
        *,
        subject: str,
        message: str,
    ) -> NamedRailSignalCandidate:
        projection = project_named_rail_signal_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_named_rail_signal_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named-rail fields must match their typed source projection")
