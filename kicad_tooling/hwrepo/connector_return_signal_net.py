"""Review connector returns assigned to native protocol-signal nets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Set as AbstractSet

from .bus_signal_pairs import (
    ethernet_data_pair_function_role,
    ethernet_management_function_role,
    usb_c_superspeed_lane_function_role,
    usb_data_function_identity,
    usb_superspeed_function_identity,
)
from .bus_signal_roles import can_function_role, i2c_signal_role, i3c_signal_identity, usb_c_cc_role
from .can_signal_functions import can_signal_role_and_channel
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import connector_candidate_references, is_return_function
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role
from .serial_participants import serial_function_role_and_channel
from .spi_participants import spi_signal_role_and_channel


def return_pin_protocol_signal_net_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt when a fitted connector return shares a net with a recognized signal role.

    The finding is a review hint. It does not establish that the native return
    role is correct or that the signal must remain separate from the return.
    """
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, reviewed_connector_references)
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = defaultdict(set)
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets[pin.casefold()].add(net)

    covered_mapped_nets = _mapped_return_signal_nets(observed, connector_coverage)
    return_pins_by_net: dict[str, set[str]] = defaultdict(set)
    signal_roles_by_net: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for pin, function in sorted(observed.pin_functions.items()):
        reference, separator, _number = pin.rpartition(".")
        if (
            not separator
            or reference.casefold() in dnp_references
            or reference not in observed.component_symbols
        ):
            continue
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        if reference.casefold() in connector_references and is_return_function(function):
            return_pins_by_net[net].add(pin)
        role = _protocol_signal_role(function, reference, connector_references, observed)
        if role is not None:
            signal_roles_by_net[net][pin] = (function, role)

    findings: list[Candidate] = []
    for net in sorted(return_pins_by_net.keys() & signal_roles_by_net.keys()):
        if net in covered_mapped_nets:
            continue
        returns = tuple(sorted(return_pins_by_net[net], key=str.casefold))
        signals = signal_roles_by_net[net]
        signal_pins = tuple(sorted(signals, key=str.casefold))
        role_evidence = tuple(
            f"{pin}: native_function={signals[pin][0]}; protocol_role={signals[pin][1]}"
            for pin in signal_pins
        )
        findings.append(
            Candidate(
                rule_id="connector.return_pin_shares_protocol_signal_net",
                subject=(
                    f"connector return pins {', '.join(returns)} and protocol signal pins "
                    f"{', '.join(signal_pins)} share native net {net}"
                ),
                message=(
                    "A fitted connector return contact shares one schematic net with a pin whose "
                    "native function identifies a supported protocol signal. Review the approved "
                    "pinout and intended connection. Native function text is a review clue; this "
                    "check does not establish the pinout, required isolation, PCB copper path, "
                    "or off-board behavior."
                ),
                evidence={
                    "assigned_net": (net,),
                    "return_pins": returns,
                    "signal_pins": signal_pins,
                    "signal_pin_roles": role_evidence,
                },
            )
        )
    return tuple(findings)


def _mapped_return_signal_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> frozenset[str]:
    """Leave current mapped return/signal sharing to its more specific rule."""
    if coverage is None:
        return frozenset()
    roles_by_net: dict[str, set[str]] = defaultdict(set)
    for mapped in source_matched_connector_pin_evidence(observed, coverage).values():
        if (
            mapped.role in {"return", "signal"}
            and mapped.unconnected_reason is None
            and len(mapped.nets) == 1
        ):
            roles_by_net[mapped.nets[0]].add(mapped.role)
    return frozenset(net for net, roles in roles_by_net.items() if roles == {"return", "signal"})


def _protocol_signal_role(
    function: str,
    reference: str,
    connector_references: AbstractSet[str],
    observed: NetlistContract,
) -> str | None:
    """Use existing exact protocol-role recognizers instead of net-name guesses."""
    if (role := i2c_signal_role(function)) is not None:
        return f"I2C {role}"
    if (identity := i3c_signal_identity(function)) is not None:
        return f"I3C {identity.role}"
    if (role := can_function_role(function)) is not None:
        return f"CAN {role}"
    if (role_channel := can_signal_role_and_channel(function)) is not None:
        return f"CAN {role_channel[0].upper()} {role_channel[1]}"
    if (role_channel := serial_function_role_and_channel(function)) is not None:
        return f"UART {role_channel[0].upper()} {role_channel[1]}"
    if (role_channel := spi_signal_role_and_channel(function)) is not None:
        return f"SPI {role_channel[0]} {role_channel[1]}"
    if (role := ethernet_data_pair_function_role(function)) is not None:
        return f"Ethernet {role[0]} {role[1]}"
    if (role := ethernet_management_function_role(function)) is not None:
        return f"Ethernet management {role}"
    if (identity := usb_data_function_identity(function)) is not None:
        return f"USB data {identity[0] or 'unindexed'} {identity[1]}"
    if (identity := usb_superspeed_function_identity(function)) is not None:
        return f"{identity[0]} {identity[1]}"
    if (role := usb_c_superspeed_lane_function_role(function)) is not None:
        return f"{role[0]} {role[1]}"
    if (role := usb_c_cc_role(function)) is not None:
        return f"USB-C {role}"
    if reference.casefold() not in connector_references:
        transceiver = explicit_rs485_transceiver_identity(observed, reference)
        if transceiver is not None and (role := rs485_data_pin_role(function)) is not None:
            return f"RS-485 {role.upper()}"
    return None
