"""Fault, control, policy, and stability tests for Ethernet MDC/MDIO labels."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist

RULE_ID = "bus.ethernet_management_label_mismatch"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_management_labels_are_reviewed_with_exact_pin_evidence() -> None:
    assert not _findings(ethernet_management_netlist())

    findings = _findings(ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC")))

    assert tuple(item.subject for item in findings) == (
        "U1.5: MDC on ETH_MDIO",
        "U1.6: MDIO on ETH_MDC",
    )
    assert tuple(item.evidence["pin_role"] for item in findings) == (("clock",), ("data",))
    assert tuple(item.evidence["net_role"] for item in findings) == (("data",), ("clock",))


@pytest.mark.parametrize(
    ("clock_label", "data_label"),
    (
        ("MDC", "MDIO"),
        ("ETH_MDC", "ETH_MDIO"),
        ("ETHERNET_MDC", "ETHERNET_MDIO"),
        ("SMI_MDC", "SMI_MDIO"),
    ),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_supported_management_label_aliases_match_native_roles(
    clock_label: str, data_label: str
) -> None:
    assert not _findings(ethernet_management_netlist(labels=(clock_label, data_label)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_neutral_indexed_dnp_ambiguous_and_short_cases_are_not_classified() -> None:
    controls = (
        ethernet_management_netlist(labels=("CLOCK", "MANAGEMENT_DATA")),
        ethernet_management_netlist(labels=("ETH_MDC1", "ETH_MDIO1")),
        ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC"), dnp=True),
        ethernet_management_netlist(labels=("ETH_MDC", "ETH_MDC")),
    )
    ambiguous = ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC")).model_copy(
        update={
            "nets": {
                "ETH_MDIO": ("U1.5",),
                "AUX": ("U1.5",),
                "ETH_MDC": ("U1.6",),
            }
        }
    )
    unsupported = ethernet_management_netlist(functions=("MDC/MDIO", "MDIO"))

    assert all(not _findings(control) for control in controls)
    assert tuple(item.subject for item in _findings(ambiguous)) == ("U1.6: MDIO on ETH_MDC",)
    assert not _findings(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_are_supported() -> None:
    source = ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC"))
    report = evaluate("synthetic-ethernet-management", coach(source), DesignLintPolicy())
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-ethernet-management",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed pin map"),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-ethernet-management",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional"),)
        ),
    )
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )

    ignored = evaluate(
        "synthetic-ethernet-management",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic board mapping reviewed",
                ),
            )
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_correct_labels_clear_findings() -> None:
    fault = ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC"))
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )

    assert _findings(reordered) == _findings(fault)
    assert not _findings(ethernet_management_netlist())
