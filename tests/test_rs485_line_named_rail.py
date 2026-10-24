"""Focused regressions for RS-485 A/B line pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding, DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from kicad_tooling.hwrepo.rs485_line_functions import rs485_bus_line_role
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_line_named_rail import rs485_line_named_rail_netlist

RULE_ID = "bus.rs485_line_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-rs485-line-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.parametrize(
    ("pin", "rail", "function", "role", "peer"),
    (
        ("U1.1", "GND", "A", "a", "U1.2"),
        ("U1.1", "+3V3", "A", "a", "U1.2"),
        ("U1.2", "GND", "B", "b", "U1.1"),
        ("U1.2", "+5V", "B", "b", "U1.1"),
    ),
)
def test_explicit_rs485_line_pins_on_named_rails_request_review(
    pin: str, rail: str, function: str, role: str, peer: str
) -> None:
    source = rs485_line_named_rail_netlist(pin=pin, rail_name=rail, function=function)
    finding = _findings(_report(source))[0]

    assert finding.subject == (
        f"{pin}: {function} on {'return-like' if rail == 'GND' else 'supply-like'} net {rail}"
    )
    assert finding.mode == "review"
    assert finding.evidence["rs485_line_role"] == (role,)
    assert finding.evidence["complementary_line_pin"] == (peer,)
    assert finding.evidence["identity_basis"] == ("Synthetic:Rs485Transceiver RS-485 transceiver",)
    assert _report(source).status == "REVIEW"
    assert "not proof of electrical potential" in finding.message


def test_only_bounded_a_b_functions_and_explicit_rs485_identity_are_considered() -> None:
    assert rs485_bus_line_role("A") == "a"
    assert rs485_bus_line_role("b") == "b"
    assert rs485_bus_line_role("A1") is None
    assert rs485_bus_line_role("A+") is None
    assert rs485_bus_line_role("Y") is None
    assert rs485_bus_line_role("CANH") is None

    controls = (
        rs485_line_named_rail_netlist(rail_name="RS485_A"),
        rs485_line_named_rail_netlist(
            identity="Generic logic IC", symbol="Logic:Device", rail_name="GND"
        ),
        rs485_line_named_rail_netlist(
            identity="SN65HVD230", symbol="Vendor:Transceiver", rail_name="GND"
        ),
        rs485_line_named_rail_netlist(function="Y", rail_name="GND"),
    )
    for control in controls:
        assert not _findings(_report(control))


def test_dnp_open_ambiguous_duplicate_and_incomplete_pair_evidence_are_skipped() -> None:
    source = rs485_line_named_rail_netlist()
    controls = (
        rs485_line_named_rail_netlist(dnp=True),
        source.model_copy(update={"nets": {"RS485_B": ("U1.2",)}}),
        source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "A", "u1.1": "B", "U1.2": "B"}}),
        source.model_copy(update={"pin_functions": {"U1.1": "A", "U1.2": "A"}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "RS485_B": ("J1.2",)},
                "component_symbols": {"J1": "Connector:Conn_01x02"},
                "pin_functions": {"J1.1": "A", "J1.2": "B"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
    )
    for control in controls:
        assert not _findings(_report(control))


def test_project_policy_can_block_disable_or_ignore_an_intentional_line_strap() -> None:
    source = rs485_line_named_rail_netlist()
    finding = _findings(_report(source))[0]
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="required"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="not used"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="intentional RS-485 fail-safe strap",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


def test_reordering_is_stable_and_moving_the_pin_to_a_bus_net_clears_review() -> None:
    fault = rs485_line_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"RS485_A": ("U1.1",), "RS485_B": ("U1.2",)}})

    assert tuple(item.model_dump() for item in _findings(_report(fault))) == tuple(
        item.model_dump() for item in _findings(_report(reordered))
    )
    assert not _findings(_report(repaired))
