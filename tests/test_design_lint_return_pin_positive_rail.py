"""Regressions for connector return pins assigned to recognized positive rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_return_supply import return_pin_positive_rail_candidates
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_return_role_catalog,
    connector_return_role_netlist,
    connector_return_role_reviews,
    inventory_review,
)
from tests.design_lint_fixtures.connector_return_supply import return_pin_positive_rail_netlist

pytestmark = [
    pytest.mark.connector_lint,
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.return_pin_on_positive_rail"


def _report(netlist: NetlistContract, policy: DesignLintPolicy | None = None):
    source = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-return-positive-rail",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(source.project_id, source, policy or DesignLintPolicy())


def test_return_pin_assigned_to_positive_supply_requests_review() -> None:
    report = _report(return_pin_positive_rail_netlist())

    assert report.status == "REVIEW"
    findings = [finding for finding in report.findings if finding.rule_id == RULE_ID]
    assert len(findings) == 1
    assert findings[0].subject == "J1.1: return assigned to +5V"
    assert findings[0].evidence == {
        "J1.1": (
            "native_function=GND",
            "assigned_net=+5V",
            "positive_rail=recognized_by_net_name_or_attached_pin_function",
        )
    }
    assert "Review the approved connector pinout" in findings[0].message


def test_reference_net_negative_rail_and_unrecognized_pin_are_controls() -> None:
    for netlist in (
        return_pin_positive_rail_netlist(return_net="GND"),
        return_pin_positive_rail_netlist(return_net="-5V"),
        return_pin_positive_rail_netlist(return_function="TX"),
    ):
        assert RULE_ID not in {finding.rule_id for finding in _report(netlist).findings}


def test_project_policy_can_block_or_turn_off_the_review_hint() -> None:
    source = return_pin_positive_rail_netlist()
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires reviewed connector return assignments",
                ),
            )
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic fixture demonstrates the explicit rule-off option",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert disabled.status == "PASS"
    ignored = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert ignored.disposition == "RULE_OFF"


def test_shield_open_and_dnp_pins_are_not_return_to_rail_findings() -> None:
    shield = return_pin_positive_rail_netlist(return_function="SHIELD")
    open_return = return_pin_positive_rail_netlist().model_copy(
        update={"nets": {"TX": ("J1.2",), "RX": ("J1.3",)}}
    )
    dnp = return_pin_positive_rail_netlist().model_copy(update={"dnp_components": ("J1",)})

    for netlist in (shield, open_return, dnp):
        assert RULE_ID not in {finding.rule_id for finding in _report(netlist).findings}


def test_source_matched_generic_return_role_is_checked() -> None:
    observed = connector_return_role_netlist()
    nets = dict(observed.nets)
    del nets["SERIAL_RETURN"]
    nets["+5V"] = ("J2.3",)
    observed = observed.model_copy(
        update={"nets": nets, "pin_functions": {**observed.pin_functions, "J2.3": "Pin_3"}}
    )
    coverage = evaluate_connector_coverage(
        observed,
        ("usb-interface", "serial-interface"),
        connector_return_role_reviews(),
        interfaces=connector_return_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="b" * 64,
        inventory_review=inventory_review(),
    )

    candidates = return_pin_positive_rail_candidates(observed, connector_coverage=coverage)

    finding = next(item for item in candidates if item.rule_id == RULE_ID)
    assert finding.subject == "J2.3: return assigned to +5V"
    assert finding.evidence["J2.3"][0] == (
        "source_matched_interface_role=return;interface_pin=3;signal=RETURN"
    )


def test_finding_is_order_stable_and_reassignment_clears_it() -> None:
    source = return_pin_positive_rail_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    original = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    reordered_finding = next(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original.fingerprint,
        original.evidence,
    )
    assert RULE_ID not in {
        item.rule_id
        for item in _report(return_pin_positive_rail_netlist(return_net="GND")).findings
    }
