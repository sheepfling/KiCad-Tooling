"""Review named power contacts split across unlike reviewed connector peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.reviewed_peer_power_input_split"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_different_named_supply_roles_on_reviewed_peers_need_review() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_IN"))
    coverage = power_input_coverage(observed, roles=("supply", "supply"))

    report = lint_report(observed, coverage)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert coverage.status == "COMPLETE"
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "reviewed-synthetic-power-peers: POWER_INPUT (external-5v) "
        "named power contacts use separate nets"
    )
    assert finding.evidence["assignments"] == ("J1.1=USB_5V", "J2.1=SERIAL_5V")
    assert finding.evidence["native_pin_functions"] == ("J1.1=VBUS", "J2.1=VDD_IN")
    assert finding.evidence["power_role_categories"] == ("vbus", "vdd")
    assert "does not prove these nets should be joined" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_or_same_category_named_supplies_are_controls() -> None:
    common = power_input_netlist(
        functions=("VBUS", "VDD_IN"),
        power_assignments=("COMMON_5V", "COMMON_5V"),
    )
    same_category_split = power_input_netlist(
        functions=("VBUS", "USB_VBUS"),
    )

    common_report = lint_report(common, power_input_coverage(common, roles=("supply", "supply")))
    same_category_report = lint_report(
        same_category_split,
        power_input_coverage(same_category_split, roles=("supply", "supply")),
    )

    assert RULE_ID not in {item.rule_id for item in common_report.findings}
    assert RULE_ID not in {item.rule_id for item in same_category_report.findings}
    assert "connector.repeated_pin_function" in {
        item.rule_id for item in same_category_report.findings
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_and_named_mapped_supply_contacts_are_compared() -> None:
    observed = power_input_netlist(functions=("Pin_1", "VBUS"))
    coverage = power_input_coverage(observed, roles=("supply", "supply"))

    finding = next(
        item for item in lint_report(observed, coverage).findings if item.rule_id == RULE_ID
    )

    assert finding.subject.endswith("mapped power contacts use separate nets")
    assert finding.evidence["native_pin_functions"] == ("J1.1=Pin_1", "J2.1=VBUS")
    assert finding.evidence["power_role_categories"] == ("vbus",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_domain_role_and_source_coverage_boundaries_stay_quiet() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_IN"))
    controls = (
        power_input_coverage(
            observed, roles=("supply", "supply"), voltage_domains=("usb", "serial")
        ),
        power_input_coverage(observed, roles=(None, None)),
        power_input_coverage(observed, roles=("supply", "supply"), peer_groups=("usb", "serial")),
        power_input_coverage(
            observed,
            roles=("supply", "supply"),
            complete_maps=False,
        ),
    )

    assert all(
        RULE_ID not in {item.rule_id for item in lint_report(observed, item).findings}
        for item in controls
    )
    stale = power_input_netlist(functions=("VBUS", "VDD_IN_CHANGED"))
    current = power_input_coverage(observed, roles=("supply", "supply"))
    assert RULE_ID not in {item.rule_id for item in lint_report(stale, current).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_supply_split_supports_policy_and_stable_ordering() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_IN"))
    coverage = power_input_coverage(observed, roles=("supply", "supply"))
    baseline = next(
        item for item in lint_report(observed, coverage).findings if item.rule_id == RULE_ID
    )
    blocked = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of unlike named supply contacts.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic maps confirm independent sources.",
                ),
            )
        ),
    )
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    reordered_coverage = power_input_coverage(reordered, roles=("supply", "supply"))
    stable = next(
        item
        for item in lint_report(reordered, reordered_coverage).findings
        if item.rule_id == RULE_ID
    )

    assert blocked.status == "FAIL"
    assert any(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )
    assert (baseline.fingerprint, baseline.evidence) == (stable.fingerprint, stable.evidence)
