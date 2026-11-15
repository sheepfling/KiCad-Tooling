"""Focused regressions for Ethernet management pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_signal_pairs import ethernet_management_function_role
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist

RULE_ID = "bus.ethernet_management_signal_on_named_rail"

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
        "synthetic-ethernet-management-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "function", "rail", "role", "rail_role", "labels"),
    (
        ("U1.5", "MDC", "GND", "clock", "return-like", ("GND", "ETH_MDIO")),
        ("U1.6", "MDIO", "+3V3", "data", "supply-like", ("ETH_MDC", "+3V3")),
    ),
)
def test_management_pin_on_named_rail_requests_review(
    pin: str,
    function: str,
    rail: str,
    role: str,
    rail_role: str,
    labels: tuple[str, str],
) -> None:
    report = _report(ethernet_management_netlist(labels=labels))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "ethernet_management_role": (role,),
        "assigned_net": (rail,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("5", "6"),
    }
    assert "Review whether this direct assignment is intentional" in finding.message
    assert "do not establish electrical potential" in finding.message


def test_connector_management_pins_on_named_rails_request_review() -> None:
    report = _report(
        ethernet_management_netlist(
            reference="J1",
            labels=("GND", "+3V3"),
        )
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert tuple(item.subject for item in findings) == (
        "J1.1: MDC on return-like net GND",
        "J1.2: MDIO on supply-like net +3V3",
    )
    assert tuple(item.evidence["ethernet_management_role"] for item in findings) == (
        ("clock",),
        ("data",),
    )
    assert all(
        "Review whether this direct assignment is intentional" in item.message for item in findings
    )


def test_management_function_aliases_are_exact() -> None:
    assert ethernet_management_function_role("MDC") == "clock"
    assert ethernet_management_function_role("MDIO") == "data"
    assert ethernet_management_function_role("MDC1") is None
    assert ethernet_management_function_role("MII_MDC") is None
    assert ethernet_management_function_role("management clock") is None


def test_neutral_rail_names_and_unrecognized_functions_are_quiet() -> None:
    controls = (
        ethernet_management_netlist(),
        ethernet_management_netlist(functions=("MDCIO", "MDI"), labels=("GND", "+3V3")),
        ethernet_management_netlist(labels=("MDC", "MDIO")),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_and_connector_boundaries_are_respected() -> None:
    source = ethernet_management_netlist(labels=("GND", "ETH_MDIO"))
    controls = (
        ethernet_management_netlist(labels=("GND", "ETH_MDIO"), dnp=True),
        ethernet_management_netlist(reference="J1", labels=("GND", "+3V3"), dnp=True),
        source.model_copy(update={"component_pin_numbers": {"U1": ("6",)}}),
        source.model_copy(
            update={"nets": {"GND": ("U1.5",), "0V": ("U1.5",), "ETH_MDIO": ("U1.6",)}}
        ),
        source.model_copy(update={"pin_functions": {"U1.5": "MDC", "u1.5": "MDIO"}}),
        ethernet_management_netlist(
            reference="J1", labels=("GND", "ETH_MDIO"), open_functions=("MDC",)
        ),
        ethernet_management_netlist(
            reference="J1", labels=("GND", "ETH_MDIO"), functions=("MDC1", "MDIO")
        ),
        ethernet_management_netlist(reference="R1", labels=("GND", "ETH_MDIO")),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_a_review() -> None:
    source = ethernet_management_netlist(labels=("GND", "ETH_MDIO"))
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="intentional management-pin strap",
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
    fault = ethernet_management_netlist(labels=("GND", "ETH_MDIO"))
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = ethernet_management_netlist()
    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)

    connector_fault = ethernet_management_netlist(reference="J1", labels=("GND", "+3V3"))
    connector_reordered = connector_fault.model_copy(
        update={
            "nets": dict(reversed(tuple(connector_fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(connector_fault.pin_functions.items()))),
        }
    )
    connector_findings = tuple(
        item.model_dump() for item in _report(connector_fault).findings if item.rule_id == RULE_ID
    )
    reordered_connector_findings = tuple(
        item.model_dump()
        for item in _report(connector_reordered).findings
        if item.rule_id == RULE_ID
    )
    assert connector_findings == reordered_connector_findings
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(ethernet_management_netlist(reference="J1")).findings
    )
