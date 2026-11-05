"""Typed evidence for bus pin functions that conflict with their net labels."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from .bus_signal_roles import can_function_role, i2c_signal_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role
from .rs485_line_functions import rs485_bus_line_label_role, rs485_bus_line_role
from .serial_participants import serial_function_role_and_channel
from .spi_participants import spi_data_label_role

I2C_SIGNAL_LABEL_RULE_ID: DesignLintRuleId = "bus.i2c_signal_label_role_mismatch"
CAN_LINE_POLARITY_LABEL_RULE_ID: DesignLintRuleId = "bus.can_line_polarity_label_mismatch"
SPI_DATA_POLARITY_LABEL_RULE_ID: DesignLintRuleId = "bus.spi_data_polarity_label_mismatch"
RS485_DATA_LABEL_RULE_ID: DesignLintRuleId = "bus.rs485_data_direction_label_mismatch"
RS485_LINE_LABEL_RULE_ID: DesignLintRuleId = "bus.rs485_line_label_mismatch"
SERIAL_TX_RX_LABEL_RULE_ID: DesignLintRuleId = "bus.serial_tx_rx_label_mismatch"

_RoleParser: TypeAlias = Callable[[str], str | None]


def _source_mismatch_matches(
    observed: NetlistContract,
    *,
    pin: str,
    pin_function: str,
    pin_role: str,
    net: str,
    net_role: str,
    parse_pin_role: _RoleParser,
    parse_net_role: _RoleParser,
    casefold_assignment: bool = False,
) -> bool:
    reference, separator, _number = pin.rpartition(".")
    if (
        not separator
        or reference.casefold() in {item.casefold() for item in observed.dnp_components}
        or observed.pin_functions.get(pin) != pin_function
    ):
        return False

    pin_key = pin.casefold() if casefold_assignment else pin
    assigned_nets = {
        native_net
        for native_net, pins in observed.nets.items()
        if any(
            item.casefold() == pin_key if casefold_assignment else item == pin_key for item in pins
        )
    }
    return (
        assigned_nets == {net}
        and parse_pin_role(pin_function) == pin_role
        and parse_net_role(net) == net_role
        and pin_role != net_role
    )


def _serial_signal_role(value: str) -> str | None:
    parsed = serial_function_role_and_channel(value)
    return None if parsed is None else parsed[0]


def _serial_channel_matches(value: str, *, role: str, channel: str) -> bool:
    parsed = serial_function_role_and_channel(value)
    return parsed == (role, channel) and channel.startswith(("uart", "usart"))


@dataclass(frozen=True, slots=True)
class I2cSignalLabelRoleMismatchEvidence:
    """One I2C native signal and conflicting explicit net-label role."""

    observed: NetlistContract
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=i2c_signal_role,
            parse_net_role=i2c_signal_role,
        ):
            raise ValueError("I2C label evidence must match its current native pin and net")


@dataclass(frozen=True, slots=True)
class CanLinePolarityLabelMismatchEvidence:
    """One CAN line with conflicting net role and no same-symbol short duplicate."""

    observed: NetlistContract
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=can_function_role,
            parse_net_role=can_function_role,
        ):
            raise ValueError("CAN label evidence must match its current native pin and net")

        reference = self.pin.rpartition(".")[0]
        pins_on_net = {
            pin for net, pins in self.observed.nets.items() if net == self.net for pin in pins
        }
        if any(
            other_pin != self.pin
            and other_pin.rpartition(".")[0] == reference
            and can_function_role(self.observed.pin_functions.get(other_pin, "")) == self.net_role
            for other_pin in pins_on_net
        ):
            raise ValueError("CAN polarity evidence must not duplicate a same-symbol line short")


@dataclass(frozen=True, slots=True)
class SpiDataLabelRoleMismatchEvidence:
    """One SPI MOSI/MISO pin with the opposing bounded net-label role."""

    observed: NetlistContract
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=spi_data_label_role,
            parse_net_role=spi_data_label_role,
        ):
            raise ValueError("SPI label evidence must match its current native pin and net")


@dataclass(frozen=True, slots=True)
class Rs485DataLabelRoleMismatchEvidence:
    """One RS-485 D/R pin and its paired, same-channel UART direction."""

    observed: NetlistContract
    reference: str
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str
    channel: str
    paired_pin: str
    paired_function: str
    paired_net: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=rs485_data_pin_role,
            parse_net_role=_serial_signal_role,
            casefold_assignment=True,
        ):
            raise ValueError("RS-485 data label evidence must match its current native pin and net")

        reference_key = self.reference.casefold()
        pin_reference, separator, pin_number = self.pin.rpartition(".")
        paired_reference, paired_separator, paired_number = self.paired_pin.rpartition(".")
        inventory = lookup_unique_casefold(self.observed.component_pin_numbers, self.reference)
        roles_by_reference: dict[str, list[tuple[str, str, str]]] = {}
        for current_pin, function in self.observed.pin_functions.items():
            current_reference, current_separator, _number = current_pin.rpartition(".")
            role = rs485_data_pin_role(function)
            if current_separator and role is not None:
                roles_by_reference.setdefault(current_reference.casefold(), []).append(
                    (current_pin, function, role)
                )
        assignments = {
            pin_key: {
                native_net
                for native_net, pins in self.observed.nets.items()
                if any(item.casefold() == pin_key.casefold() for item in pins)
            }
            for pin_key in (self.pin, self.paired_pin)
        }
        pin_channel = serial_function_role_and_channel(self.net)
        paired_channel = serial_function_role_and_channel(self.paired_net)
        candidates = roles_by_reference.get(reference_key, [])
        tx_pins = tuple(item for item in candidates if item[2] == "tx")
        rx_pins = tuple(item for item in candidates if item[2] == "rx")
        expected_paired_role = "rx" if self.pin_role == "tx" else "tx"
        selected_assignments_valid = (
            self.pin_role == rs485_data_pin_role(self.pin_function)
            and self.pin == self.observed_pin_for(self.pin, self.pin_function)
            and self.paired_function == self.observed.pin_functions.get(self.paired_pin)
            and rs485_data_pin_role(self.paired_function) == expected_paired_role
            and lookup_unique_casefold(self.observed.components, self.reference) is not None
            and is_integrated_circuit_reference(self.reference)
            and reference_key not in {item.casefold() for item in self.observed.dnp_components}
            and pin_reference.casefold() == reference_key
            and paired_reference.casefold() == reference_key
            and bool(separator)
            and bool(paired_separator)
            and inventory is not None
            and pin_number.casefold() in {item.casefold() for item in inventory}
            and paired_number.casefold() in {item.casefold() for item in inventory}
            and len(tx_pins) == 1
            and len(rx_pins) == 1
            and {tx_pins[0][0], rx_pins[0][0]} == {self.pin, self.paired_pin}
            and assignments[self.pin] == {self.net}
            and assignments[self.paired_pin] == {self.paired_net}
            and pin_channel is not None
            and paired_channel is not None
            and pin_channel[1] == self.channel
            and paired_channel[1] == self.channel
            and _serial_channel_matches(self.net, role=self.net_role, channel=self.channel)
            and self.channel.startswith(("uart", "usart"))
        )
        if not selected_assignments_valid:
            raise ValueError("RS-485 data label evidence must retain its current paired channel")

    def observed_pin_for(self, pin: str, function: str) -> str | None:
        """Return the exact function-map key for the unique native pin record."""
        matches = tuple(
            current_pin
            for current_pin, current_function in self.observed.pin_functions.items()
            if current_pin.casefold() == pin.casefold() and current_function == function
        )
        return matches[0] if len(matches) == 1 else None


@dataclass(frozen=True, slots=True)
class Rs485LineLabelRoleMismatchEvidence:
    """One explicitly identified RS-485 A/B line and its complete native pair."""

    observed: NetlistContract
    reference: str
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str
    identity_basis: str
    paired_pin: str
    paired_function: str
    paired_net: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=rs485_bus_line_role,
            parse_net_role=rs485_bus_line_label_role,
            casefold_assignment=True,
        ):
            raise ValueError("RS-485 line evidence must match its current native pin and label")

        reference_key = self.reference.casefold()
        pin_reference, separator, pin_number = self.pin.rpartition(".")
        paired_reference, paired_separator, paired_number = self.paired_pin.rpartition(".")
        inventory = lookup_unique_casefold(self.observed.component_pin_numbers, self.reference)
        identity = explicit_rs485_transceiver_identity(self.observed, self.reference)
        line_pins: dict[str, list[tuple[str, str, str]]] = {"a": [], "b": []}
        for current_pin, function in self.observed.pin_functions.items():
            current_reference, current_separator, _number = current_pin.rpartition(".")
            role = rs485_bus_line_role(function)
            if (
                current_separator
                and current_reference.casefold() == reference_key
                and role is not None
            ):
                line_pins[role].append((current_pin, function, role))
        paired_role = "b" if self.pin_role == "a" else "a"
        pin_assignments = {
            pin_key: {
                native_net
                for native_net, pins in self.observed.nets.items()
                if any(item.casefold() == pin_key.casefold() for item in pins)
            }
            for pin_key in (self.pin, self.paired_pin)
        }
        selected_pair_valid = (
            identity == self.identity_basis
            and lookup_unique_casefold(self.observed.components, self.reference) is not None
            and is_integrated_circuit_reference(self.reference)
            and reference_key not in {item.casefold() for item in self.observed.dnp_components}
            and inventory is not None
            and pin_reference.casefold() == reference_key
            and paired_reference.casefold() == reference_key
            and bool(separator)
            and bool(paired_separator)
            and pin_number.casefold() in {item.casefold() for item in inventory}
            and paired_number.casefold() in {item.casefold() for item in inventory}
            and len(line_pins["a"]) == 1
            and len(line_pins["b"]) == 1
            and (self.pin, self.pin_function, self.pin_role) in line_pins[self.pin_role]
            and (self.paired_pin, self.paired_function, paired_role) in line_pins[paired_role]
            and pin_assignments[self.pin] == {self.net}
            and pin_assignments[self.paired_pin] == {self.paired_net}
            and rs485_bus_line_label_role(self.paired_net) is not None
            and self.net.casefold() != self.paired_net.casefold()
        )
        if not selected_pair_valid:
            raise ValueError("RS-485 line evidence must retain its current identified A/B pair")


@dataclass(frozen=True, slots=True)
class SerialTxRxLabelRoleMismatchEvidence:
    """One fitted UART TX/RX pin and its same-channel explicit net label."""

    observed: NetlistContract
    reference: str
    pin: str
    pin_function: str
    pin_role: str
    net: str
    net_role: str
    channel: str

    def __post_init__(self) -> None:
        if not _source_mismatch_matches(
            self.observed,
            pin=self.pin,
            pin_function=self.pin_function,
            pin_role=self.pin_role,
            net=self.net,
            net_role=self.net_role,
            parse_pin_role=_serial_signal_role,
            parse_net_role=_serial_signal_role,
            casefold_assignment=True,
        ):
            raise ValueError("Serial label evidence must match its current native pin and net")

        reference_key = self.reference.casefold()
        pin_reference, separator, pin_number = self.pin.rpartition(".")
        matching_function_keys = tuple(
            (current_pin, function)
            for current_pin, function in self.observed.pin_functions.items()
            if current_pin.casefold() == self.pin.casefold()
        )
        inventory = lookup_unique_casefold(self.observed.component_pin_numbers, self.reference)
        valid_serial_pin = (
            pin_reference.casefold() == reference_key
            and bool(separator)
            and is_integrated_circuit_reference(self.reference)
            and lookup_unique_casefold(self.observed.components, self.reference) is not None
            and reference_key not in {item.casefold() for item in self.observed.dnp_components}
            and len(matching_function_keys) == 1
            and matching_function_keys[0] == (self.pin, self.pin_function)
            and inventory is not None
            and pin_number.casefold() in {item.casefold() for item in inventory}
            and _serial_channel_matches(self.pin_function, role=self.pin_role, channel=self.channel)
            and _serial_channel_matches(self.net, role=self.net_role, channel=self.channel)
            and self.channel.startswith(("uart", "usart"))
        )
        if not valid_serial_pin:
            raise ValueError("Serial label evidence must retain its current UART/USART channel")


SignalLabelRoleMismatchEvidence: TypeAlias = (
    I2cSignalLabelRoleMismatchEvidence
    | CanLinePolarityLabelMismatchEvidence
    | SpiDataLabelRoleMismatchEvidence
    | Rs485DataLabelRoleMismatchEvidence
    | Rs485LineLabelRoleMismatchEvidence
    | SerialTxRxLabelRoleMismatchEvidence
)


def project_signal_label_role_mismatch_evidence(
    source: SignalLabelRoleMismatchEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed role conflict into the established report fields."""
    source.__post_init__()
    evidence = {
        "pin": (source.pin,),
        "pin_function": (source.pin_function,),
        "pin_role": (source.pin_role,),
        "net": (source.net,),
        "net_role": (source.net_role,),
    }
    if isinstance(
        source,
        (
            Rs485DataLabelRoleMismatchEvidence,
            Rs485LineLabelRoleMismatchEvidence,
            SerialTxRxLabelRoleMismatchEvidence,
        ),
    ):
        evidence["reference"] = (source.reference,)
    if isinstance(source, Rs485DataLabelRoleMismatchEvidence | SerialTxRxLabelRoleMismatchEvidence):
        evidence["channel"] = (source.channel,)
    if isinstance(source, Rs485LineLabelRoleMismatchEvidence):
        evidence["identity_basis"] = (source.identity_basis,)
    if isinstance(source, I2cSignalLabelRoleMismatchEvidence):
        rule_id = I2C_SIGNAL_LABEL_RULE_ID
    elif isinstance(source, CanLinePolarityLabelMismatchEvidence):
        rule_id = CAN_LINE_POLARITY_LABEL_RULE_ID
    elif isinstance(source, SpiDataLabelRoleMismatchEvidence):
        rule_id = SPI_DATA_POLARITY_LABEL_RULE_ID
    elif isinstance(source, Rs485DataLabelRoleMismatchEvidence):
        rule_id = RS485_DATA_LABEL_RULE_ID
    elif isinstance(source, Rs485LineLabelRoleMismatchEvidence):
        rule_id = RS485_LINE_LABEL_RULE_ID
    else:
        rule_id = SERIAL_TX_RX_LABEL_RULE_ID
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class SignalLabelRoleMismatchCandidate(Candidate):
    """Candidate whose pin and net roles remain bound to their native source."""

    source_evidence: SignalLabelRoleMismatchEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SignalLabelRoleMismatchEvidence,
        *,
        subject: str,
        message: str,
    ) -> SignalLabelRoleMismatchCandidate:
        projection = project_signal_label_role_mismatch_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_signal_label_role_mismatch_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Signal label fields must match their typed source projection")
