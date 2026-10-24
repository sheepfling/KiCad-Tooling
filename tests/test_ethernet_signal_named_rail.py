"""Focused regressions for Ethernet data pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_signal_pairs import ethernet_data_pair_function_role
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_netlist,
)

RULE_ID = "bus.ethernet_signal_on_named_rail"

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
        "synthetic-ethernet-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "rail", "function", "direction", "side", "rail_role"),
    (
        ("U1.1", "GND", "TDP", "TX", "positive", "return-like"),
        ("U1.2", "+3V3", "TDN", "TX", "negative", "supply-like"),
        ("U1.3", "VBUS", "RDP", "RX", "positive", "supply-like"),
        ("U1.4", "0V PHY", "RDN", "RX", "negative", "return-like"),
    ),
)
def test_ethernet_data_pin_on_named_rail_requests_review(
    pin: str, rail: str, function: str, direction: str, side: str, rail_role: str
) -> None:
    report = _report(ethernet_signal_on_named_rail_netlist(rail_name=rail, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "ethernet_direction": (direction,),
        "ethernet_pair_side": (side,),
        "assigned_net": (rail,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("1", "2", "3", "4"),
    }
    assert "intentional PHY strap" in finding.message
    assert "do not establish electrical potential" in finding.message


def test_bounded_ethernet_function_aliases_and_non_data_functions() -> None:
    assert ethernet_data_pair_function_role("TDP") == ("TX", "positive")
    assert ethernet_data_pair_function_role("RDN") == ("RX", "negative")
    assert ethernet_data_pair_function_role("TX+") is None
    assert ethernet_data_pair_function_role("MDC") is None
    assert ethernet_data_pair_function_role("GND") is None


def test_neutral_labels_and_unsupported_functions_are_quiet() -> None:
    source = ethernet_signal_on_named_rail_netlist(rail_name="ETH_TX_P")
    unsupported = source.model_copy(update={"pin_functions": {"U1.1": "MDC", "U1.2": "MDIO"}})
    incomplete = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})

    for control in (source, unsupported, incomplete):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_and_connector_pins_are_skipped() -> None:
    source = ethernet_signal_on_named_rail_netlist()
    controls = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"nets": {"ETH_RX_P": ("U1.3",), "ETH_RX_N": ("U1.4",)}}),
        source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "TDP", "u1.1": "RDP"}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "ETH_RX_P": ("J1.2",)},
                "component_symbols": {"J1": "Connector:Conn_01x02"},
                "pin_functions": {"J1.1": "TDP", "J1.2": "RDP"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_an_intentional_strap() -> None:
    source = ethernet_signal_on_named_rail_netlist()
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
                    reason="PHY strap is intentional",
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
    fault = ethernet_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(
        update={
            "nets": {
                "TDP": ("U1.1",),
                **{name: members for name, members in fault.nets.items() if name != "GND"},
            }
        }
    )

    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
