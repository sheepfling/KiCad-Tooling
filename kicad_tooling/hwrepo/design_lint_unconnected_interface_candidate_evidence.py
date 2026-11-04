"""Typed protocol-pin sources and their stable finding projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .bus_signal_roles import UnconnectedInterfacePin
from .can_unconnected_direction_pins import UnconnectedCanDirectionPin
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_unconnected_pins import UnconnectedI2cSignalPin
from .serial_unconnected_pins import UnconnectedSerialFunctionPin
from .spi_unconnected_clock_pin import UnconnectedSpiClockPin
from .spi_unconnected_data_pins import UnconnectedSpiDataPin
from .usb_unconnected_data import UnconnectedUsbDataPin

UnconnectedInterfaceEvidence: TypeAlias = (
    UnconnectedI2cSignalPin
    | UnconnectedCanDirectionPin
    | UnconnectedInterfacePin
    | UnconnectedUsbDataPin
    | UnconnectedSpiDataPin
    | UnconnectedSpiClockPin
    | UnconnectedSerialFunctionPin
)


def unconnected_interface_pin_description(source: UnconnectedInterfacePin) -> str:
    """Describe the protocol identity used in the existing generic pin prompt."""
    if source.protocol == "spi":
        return "SPI chip-select"
    if source.protocol == "usb_c":
        return "USB-C configuration-channel"
    return "CANH/CANL line"


def project_unconnected_interface_evidence(
    source: UnconnectedInterfaceEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed pin-scan record to its established report fields."""
    if isinstance(source, UnconnectedI2cSignalPin):
        return CandidateEvidenceProjection(
            rule_id="bus.i2c_unconnected_pin",
            evidence={
                source.pin: (),
                "function": (source.function,),
                "i2c_role": (source.role,),
                "paired_pin": (source.paired_pin,),
                "paired_net": (source.paired_net,),
            },
        )
    if isinstance(source, UnconnectedCanDirectionPin):
        return CandidateEvidenceProjection(
            rule_id="bus.can_unconnected_direction_pin",
            evidence={
                source.pin: (),
                "function": (source.function,),
                "can_role": (source.role.upper(),),
                "can_channel": (source.channel,),
                "paired_pin": (source.paired_pin,),
                "paired_net": (source.paired_net,),
            },
        )
    if isinstance(source, UnconnectedInterfacePin):
        rule_id: DesignLintRuleId
        if source.protocol == "spi":
            rule_id = "bus.spi_unconnected_chip_select"
        elif source.protocol == "usb_c":
            rule_id = "bus.usb_c_unconnected_cc_pin"
        else:
            rule_id = "bus.can_unconnected_line"
        return CandidateEvidenceProjection(
            rule_id=rule_id,
            evidence={source.pin: (), "function": (source.function,)},
        )
    if isinstance(source, UnconnectedUsbDataPin):
        side = "D+" if source.side == "positive" else "D−"
        evidence: dict[str, tuple[str, ...]] = {
            source.pin: (),
            "function": (source.function,),
            "USB_data_side": (side,),
            "paired_pin": (source.paired_pin,),
            "paired_function": (source.paired_function,),
            "paired_net": (source.paired_net,),
        }
        if source.port_index is not None:
            evidence["USB_data_port_index"] = (source.port_index,)
        return CandidateEvidenceProjection(
            rule_id="bus.usb_unconnected_data_pin",
            evidence=evidence,
        )
    if isinstance(source, UnconnectedSpiDataPin):
        family = "MOSI-family" if source.role == "input" else "MISO-family"
        return CandidateEvidenceProjection(
            rule_id="bus.spi_unconnected_data_pin",
            evidence={
                source.pin: (),
                "function": (source.function,),
                "spi_data_family": (family,),
                "spi_channel": (source.channel,),
            },
        )
    if isinstance(source, UnconnectedSpiClockPin):
        return CandidateEvidenceProjection(
            rule_id="bus.spi_unconnected_clock_pin",
            evidence={
                source.pin: (),
                "function": (source.function,),
                "spi_channel": (source.channel,),
                "active_peer_pins": source.active_peer_pins,
            },
        )
    return CandidateEvidenceProjection(
        rule_id="bus.serial_unconnected_pin",
        evidence={
            source.pin: (),
            "function": (source.function,),
            "serial_role": (source.role.upper(),),
            "serial_channel": (source.channel,),
        },
    )


@dataclass(frozen=True, slots=True)
class UnconnectedInterfaceCandidate(Candidate):
    """Internal protocol-pin candidate retaining its typed scan record."""

    source_evidence: UnconnectedInterfaceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UnconnectedInterfaceEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnconnectedInterfaceCandidate:
        projection = project_unconnected_interface_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_unconnected_interface_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Unconnected-interface rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Unconnected-interface evidence must match its typed projection")
