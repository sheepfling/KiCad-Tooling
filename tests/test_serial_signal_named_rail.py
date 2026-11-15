"""Focused regressions for serial signal pins assigned directly to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_signal_named_rail import (
    serial_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist

RULE_ID = "bus.serial_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-serial-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _connector_netlist(*, signal_net: str = "GND") -> NetlistContract:
    source = serial_signal_on_named_rail_netlist()
    return source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {signal_net: ("J1.1",), "USART1_RX": ("J1.2",)},
            "component_symbols": {"J1": "Connector_Generic:Conn_01x02"},
            "pin_functions": {"J1.1": "USART1_TX", "J1.2": "USART1_RX"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )


def _signal_netlist(*, function: str, pin: str, rail_name: str) -> NetlistContract:
    source = serial_signal_on_named_rail_netlist()
    other_pin = "U1.2" if pin == "U1.1" else "U1.1"
    other_net = "USART1_RX" if other_pin == "U1.2" else "USART1_TX"
    functions = dict(source.pin_functions)
    functions[pin] = function
    return source.model_copy(
        update={
            "pin_functions": functions,
            "nets": {rail_name: (pin,), other_net: (other_pin,)},
        }
    )


@pytest.mark.parametrize(
    ("rail_name", "pin", "function", "role_clue", "pin_role", "channel"),
    (
        ("GND", "U1.1", "USART1_TX", "return-like", "tx", "usart1"),
        ("0V PWM 2", "U1.2", "USART1_RX", "return-like", "rx", "usart1"),
        ("+3V3", "U1.1", "USART1_TX", "supply-like", "tx", "usart1"),
    ),
)
def test_explicit_serial_pin_on_named_rail_requests_review_with_exact_evidence(
    rail_name: str,
    pin: str,
    function: str,
    role_clue: str,
    pin_role: str,
    channel: str,
) -> None:
    report = _report(serial_signal_on_named_rail_netlist(rail_name=rail_name, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {role_clue} net {rail_name}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (pin_role,),
        "serial_channel": (channel,),
        "assigned_net": (rail_name,),
        "net_label_role_clue": (role_clue,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


@pytest.mark.parametrize(
    ("function", "pin", "rail_name", "role", "channel", "role_clue"),
    (
        ("CTS", "U1.1", "GND", "cts", "default", "return-like"),
        ("RTS", "U1.2", "0V PWM 2", "rts", "default", "return-like"),
        ("UART_CTS#", "U1.1", "+3V3", "cts", "uart", "supply-like"),
        ("USART1_RTS_N", "U1.2", "GND", "rts", "usart1", "return-like"),
    ),
)
def test_explicit_flow_control_pin_on_named_rail_requests_review(
    function: str,
    pin: str,
    rail_name: str,
    role: str,
    channel: str,
    role_clue: str,
) -> None:
    report = _report(_signal_netlist(function=function, pin=pin, rail_name=rail_name))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {role_clue} net {rail_name}"
    assert finding.evidence["pin_role"] == (role,)
    assert finding.evidence["serial_channel"] == (channel,)
    assert finding.evidence["pin_function"] == (function,)
    assert "hardware flow control is unused" in finding.message
    assert "not proof of electrical potential" in finding.message


@pytest.mark.parametrize("function", ("CTS", "RTS", "UART1_CTS#", "USART2_RTS_N"))
def test_flow_control_pin_on_neutral_serial_net_is_control(function: str) -> None:
    source = _signal_netlist(function=function, pin="U1.1", rail_name="UART1_CTS")

    assert not any(item.rule_id == RULE_ID for item in _report(source).findings)


def test_neutral_labels_and_unsupported_pin_functions_are_controls() -> None:
    source = serial_signal_on_named_rail_netlist(rail_name="POWER_SENSE")
    unsupported_function = source.model_copy(
        update={"pin_functions": {"U1.1": "UART1_TX_P", "U1.2": "USART1_RX"}}
    )
    incomplete_inventory = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})
    connector_neutral = _connector_netlist(signal_net="UART_TX")
    unsupported_flow_control = _signal_netlist(
        function="UART1_CTS_INPUT",
        pin="U1.1",
        rail_name="GND",
    )

    assert not any(item.rule_id == RULE_ID for item in _report(source).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(unsupported_function).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(unsupported_flow_control).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(incomplete_inventory).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(connector_neutral).findings)


@pytest.mark.parametrize(
    ("function", "role", "channel", "rail_name", "role_clue"),
    (
        ("DTR", "dtr", "default", "GND", "return-like"),
        ("DSR", "dsr", "default", "+3V3", "supply-like"),
        ("DCD", "dcd", "default", "GND", "return-like"),
        ("RI", "ri", "default", "+3V3", "supply-like"),
        ("UART_DTR#", "dtr", "uart", "GND", "return-like"),
        ("USART1_DSR_N", "dsr", "usart1", "+3V3", "supply-like"),
        ("UART2_DCD", "dcd", "uart2", "GND", "return-like"),
        ("USART3_RI#", "ri", "usart3", "+3V3", "supply-like"),
    ),
)
def test_modem_control_pin_on_named_rail_requests_review(
    function: str,
    role: str,
    channel: str,
    rail_name: str,
    role_clue: str,
) -> None:
    report = _report(_signal_netlist(function=function, pin="U1.1", rail_name=rail_name))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"U1.1: {function} on {role_clue} net {rail_name}"
    assert finding.evidence["pin_role"] == (role,)
    assert finding.evidence["serial_channel"] == (channel,)
    assert finding.evidence["pin_function"] == (function,)
    assert "Modem-control signals may be optional" in finding.message
    assert "not proof of electrical potential" in finding.message


@pytest.mark.parametrize("function", ("DTR", "DSR", "DCD", "RI", "UART1_RI#"))
def test_modem_control_pin_on_neutral_serial_net_is_control(function: str) -> None:
    source = _signal_netlist(function=function, pin="U1.1", rail_name="MODEM_CONTROL")

    assert not any(item.rule_id == RULE_ID for item in _report(source).findings)


@pytest.mark.parametrize(
    "function", ("UART1_DTR_OUTPUT", "DTR_ENABLE", "RI_INPUT", "USART2_DSR_GPIO")
)
def test_unsupported_modem_control_function_spelling_stays_unclassified(function: str) -> None:
    source = _signal_netlist(function=function, pin="U1.1", rail_name="GND")

    assert not any(item.rule_id == RULE_ID for item in _report(source).findings)


def test_connector_only_serial_pin_on_named_rail_requests_review() -> None:
    report = _report(_connector_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "J1.1: USART1_TX on return-like net GND"
    assert findings[0].evidence["pin"] == ("J1.1",)
    assert findings[0].evidence["component_pin_inventory"] == ("1", "2")


def test_dnp_open_and_ambiguous_assignments_stay_outside_the_predicate() -> None:
    source = serial_signal_on_named_rail_netlist()
    connector = _connector_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"USART1_RX": ("U1.2",)}})
    ambiguous = source.model_copy(
        update={
            "nets": {
                "GND": ("U1.1",),
                "0V": ("U1.1",),
                "USART1_RX": ("U1.2",),
            }
        }
    )
    connector_dnp = connector.model_copy(update={"dnp_components": ("J1",)})
    connector_open = connector.model_copy(update={"nets": {"USART1_RX": ("J1.2",)}})
    connector_ambiguous = connector.model_copy(
        update={
            "nets": {
                "GND": ("J1.1",),
                "0V": ("J1.1",),
                "USART1_RX": ("J1.2",),
            }
        }
    )
    connector_incomplete = connector.model_copy(update={"component_pin_numbers": {"J1": ("2",)}})

    for control in (
        dnp,
        open_pin,
        ambiguous,
        connector_dnp,
        connector_open,
        connector_ambiguous,
        connector_incomplete,
    ):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_and_exact_ignore_control_the_review() -> None:
    source = serial_signal_on_named_rail_netlist()
    default = _report(source)
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    block = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="test policy"),)
        ),
    )
    off = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="test policy"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="reviewed intentional serial rail strap",
                ),
            ),
        ),
    )

    assert finding.mode == "review"
    assert block.status == "FAIL"
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        ).disposition
        == "IGNORED"
    )


def test_mapping_order_is_stable_and_repairing_assignment_clears_review() -> None:
    fault = serial_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    corrected = serial_tx_rx_label_netlist(crossed=False)
    fault_findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert tuple(item.model_dump() for item in fault_findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(corrected).findings)


def test_pin_level_clue_adds_localization_to_existing_peer_coverage() -> None:
    report = _report(serial_signal_on_named_rail_netlist())
    finding_ids = {item.rule_id for item in report.findings}

    assert RULE_ID in finding_ids
    assert "bus.serial_unmapped_peer" in finding_ids
