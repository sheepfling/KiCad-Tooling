"""Focused regressions for CAN controller pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_signal_functions import can_signal_role_and_channel
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_signal_named_rail import can_signal_on_named_rail_netlist

RULE_ID = "bus.can_signal_on_named_rail"

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
        "synthetic-can-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "rail", "function", "role", "channel", "rail_role"),
    (
        ("U1.1", "GND", "CAN1_TX", "tx", "can:index1", "return-like"),
        ("U1.2", "+3V3", "CAN1_RX", "rx", "can:index1", "supply-like"),
    ),
)
def test_can_controller_signal_on_named_rail_requests_review(
    pin: str, rail: str, function: str, role: str, channel: str, rail_role: str
) -> None:
    report = _report(can_signal_on_named_rail_netlist(rail_name=rail, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (role,),
        "can_channel": (channel,),
        "assigned_net": (rail,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


def test_bounded_can_aliases_and_non_can_or_bus_line_aliases() -> None:
    assert can_signal_role_and_channel("CAN1_TX") == ("tx", "can:index1")
    assert can_signal_role_and_channel("FDCAN2_RXD") == ("rx", "fdcan:index2")
    assert can_signal_role_and_channel("TXD_CAN") == ("tx", "can:default")
    assert can_signal_role_and_channel("CANH") is None
    assert can_signal_role_and_channel("TXD") is None
    assert can_signal_role_and_channel("UART1_TX") is None


def test_neutral_labels_and_unsupported_functions_are_quiet() -> None:
    source = can_signal_on_named_rail_netlist(rail_name="CAN_TX")
    unsupported = source.model_copy(update={"pin_functions": {"U1.1": "CANH", "U1.2": "CANL"}})
    incomplete = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})

    for control in (source, unsupported, incomplete):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_and_connector_pins_are_skipped() -> None:
    source = can_signal_on_named_rail_netlist()
    controls = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"nets": {"CAN1_RX": ("U1.2",)}}),
        source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "CAN1_TX", "u1.1": "CAN1_RX"}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "CAN1_RX": ("J1.2",)},
                "component_symbols": {"J1": "Connector:Conn_01x02"},
                "pin_functions": {"J1.1": "CAN1_TX", "J1.2": "CAN1_RX"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_an_intentional_strap() -> None:
    source = can_signal_on_named_rail_netlist(rail_name="GND")
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed policy"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed policy"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="CAN TX is intentionally held inactive",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_mapping_order_is_stable_and_repaired_assignment_clears_review() -> None:
    fault = can_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"CAN1_TX": ("U1.1",), "CAN1_RX": ("U1.2",)}})

    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
