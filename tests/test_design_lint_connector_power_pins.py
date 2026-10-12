"""Synthetic connector power-peer regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import (
    coach,
    cross_symbol_power,
    observed,
    three_port_power_pin_drift,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]


def test_exact_ignore_resurfaces_after_connection_changes() -> None:
    initial = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
    power = next(item for item in initial.findings if item.subject.endswith("PWR"))
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id="connector.repeated_pin_function",
                fingerprint=power.fingerprint,
                reason="Independent review permits the currently unconnected third port",
            ),
        )
    )
    ignored = evaluate("synthetic-ports", coach(observed()), policy)
    assert (
        next(item for item in ignored.findings if item.subject.endswith("PWR")).disposition
        == "IGNORED"
    )
    changed = evaluate("synthetic-ports", coach(observed(True)), policy)
    assert changed.status == "REVIEW"
    assert changed.stale_ignores == policy.ignores
    assert fingerprint(
        next(item for item in candidates(observed()) if item.subject.endswith("PWR"))
    ) != fingerprint(
        next(item for item in candidates(observed(True)) if item.subject.endswith("PWR"))
    )


def test_supply_pins_across_connector_symbols_need_review() -> None:
    report = evaluate("synthetic-ports", coach(cross_symbol_power()), DesignLintPolicy())
    assert report.status == "REVIEW"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.subject == "multiple connector symbols: PWR"
    assert finding.evidence == {"J1.1": ("USB_SUPPLY",), "J2.1": ("SERIAL_SUPPLY",)}
    assert "independent supplies" in finding.message


def test_three_generic_power_pins_report_different_and_missing_sibling_assignments() -> None:
    report = evaluate(
        "synthetic-three-port-power", coach(three_port_power_pin_drift()), DesignLintPolicy()
    )
    assert report.status == "REVIEW"
    assert {item.rule_id for item in report.findings} == {
        "connector.repeated_pin_function",
        "net.numbered_power_rails",
    }
    sibling_pins = next(
        item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
    )
    assert sibling_pins.evidence == {"J1.1": ("+5V_1",), "J2.1": ("5V-2",), "J3.1": ()}
    numbered_rails = next(
        item for item in report.findings if item.rule_id == "net.numbered_power_rails"
    )
    assert numbered_rails.evidence == {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)}
    common = evaluate(
        "synthetic-three-port-power-common",
        coach(three_port_power_pin_drift(common=True)),
        DesignLintPolicy(),
    )
    assert common.status == "PASS"
    assert not common.findings


def _named_power_input_peer_netlist(*, connected: bool) -> NetlistContract:
    references = ("J1", "J2")
    nets = {"SYNTHETIC_SIGNAL": ("J1.1", "J2.1")}
    if connected:
        nets["SYNTHETIC_BIAS"] = ("J1.2", "J2.2")
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={reference: "Synthetic:NamedPowerConnector" for reference in references},
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            **{f"{reference}.1": "Pin_1" for reference in references},
            **{f"{reference}.2": "BIAS_IN" for reference in references},
        },
        pin_electrical_types={
            **{f"{reference}.1": "passive" for reference in references},
            **{f"{reference}.2": "power_in" for reference in references},
        },
    )


@pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function")
def test_named_power_input_open_on_all_connector_peers_needs_review() -> None:
    report = evaluate(
        "synthetic-named-power-input-peers-open",
        coach(_named_power_input_peer_netlist(connected=False)),
        DesignLintPolicy(),
    )
    findings = [
        item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
    ]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence == {"J1.2": (), "J2.2": ()}
    assert "intended pinout" in findings[0].message
    assert "connector.unconnected_power_input" not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function")
def test_common_named_power_input_connector_peer_assignment_is_quiet() -> None:
    report = evaluate(
        "synthetic-named-power-input-peers-common",
        coach(_named_power_input_peer_netlist(connected=True)),
        DesignLintPolicy(),
    )

    assert "connector.repeated_pin_function" not in {item.rule_id for item in report.findings}
