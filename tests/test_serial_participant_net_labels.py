"""Focused synthetic regressions for serial endpoint net-label discovery."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext, unmapped_serial_peers
from tests.serial_participant_support import (
    alternate_function_serial_netlist,
    alternate_function_serial_peer_analysis,
    coach,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_explicit_uart_net_labels_discover_alternate_function_mcu_pins() -> None:
    source = alternate_function_serial_netlist()
    candidates = unmapped_serial_peers(source, SerialPeerRosterContext(state="not_configured"))

    assert len(candidates) == 1
    assert candidates[0].reference == "U1"
    assert candidates[0].channel == "UART"
    assert candidates[0].tx_pins == ("U1.1",)
    assert candidates[0].rx_pins == ("U1.2",)
    assert candidates[0].discovery_basis == "net_label"
    assert candidates[0].signal_assignments == ("U1.1=UART_TX", "U1.2=UART_RX")

    report = evaluate("synthetic-serial-roster", coach(source), DesignLintPolicy())
    finding = next(item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer")
    assert finding.mode == "review"
    assert finding.evidence["discovery_basis"] == ("net_label",)
    assert "explicitly UART/USART-labeled TX/RX nets" in finding.message
    assert "does not assert that a peer or connection is required" in finding.message

    analysis = alternate_function_serial_peer_analysis()
    mapped = unmapped_serial_peers(
        source,
        SerialPeerRosterContext(state="required", analysis=analysis),
    )
    assert mapped == ()


def test_net_label_serial_discovery_rejects_ambiguous_or_incomplete_controls() -> None:
    source = alternate_function_serial_netlist()
    cases = {
        "connector-is-off-board-absent": source.model_copy(
            update={"nets": {"UART_TX": ("U1.1",), "UART_RX": ("U1.2",), "GND": ("U1.3",)}}
        ),
        "channel-mismatch": source.model_copy(
            update={
                "nets": {
                    "UART1_TX": ("J5.1", "U1.1"),
                    "UART2_RX": ("J5.2", "U1.2"),
                    "GND": ("J5.3", "U1.3"),
                }
            }
        ),
        "dnp-connector": alternate_function_serial_netlist(dnp=("J5",)),
        "ambiguous-mcu-pin": source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "UART_TX": ("J5.1", "U1.1", "U1.4"),
                },
                "pin_functions": {**source.pin_functions, "U1.4": "PA4"},
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U1": ("1", "2", "3", "4"),
                },
            }
        ),
        "bare-signal-labels": source.model_copy(
            update={
                "nets": {
                    "TX": ("J5.1", "U1.1"),
                    "RX": ("J5.2", "U1.2"),
                    "GND": ("J5.3", "U1.3"),
                }
            }
        ),
    }
    for name, candidate in cases.items():
        assert (
            unmapped_serial_peers(candidate, SerialPeerRosterContext(state="not_configured")) == ()
        ), name


def test_net_label_discovery_is_order_stable_and_does_not_duplicate_pin_function_findings() -> None:
    source = alternate_function_serial_netlist()
    baseline = unmapped_serial_peers(source, SerialPeerRosterContext(state="not_configured"))
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    assert (
        unmapped_serial_peers(reordered, SerialPeerRosterContext(state="not_configured"))
        == baseline
    )

    native_roles = source.model_copy(
        update={
            "pin_functions": {
                **source.pin_functions,
                "U1.1": "UART_TX",
                "U1.2": "UART_RX",
            }
        }
    )
    findings = unmapped_serial_peers(native_roles, SerialPeerRosterContext(state="not_configured"))
    assert len(findings) == 1
    assert findings[0].discovery_basis == "pin_function"
