"""Review open named passive supply contacts across mapped connector peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.reviewed_peer_passive_power_input_open"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_mapped_passive_open_contact_needs_review() -> None:
    observed = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
    )
    coverage = power_input_coverage(observed, roles=("supply", "supply"))

    report = lint_report(observed, coverage)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert "connector.repeated_pin_function" not in {item.rule_id for item in report.findings}
    finding = findings[0]
    assert finding.subject == (
        "reviewed-synthetic-power-peers: POWER_INPUT (external-5v) "
        "mapped passive power contact is open beside its peer"
    )
    assert finding.evidence["assignments"] == (
        "J1.1=USB_5V",
        "J2.1=<unassigned>",
    )
    assert finding.evidence["native_pin_functions"] == ("J1.1=VBUS", "J2.1=VDD_IN")
    assert finding.evidence["power_role_categories"] == ("vbus", "vdd")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_documented_and_same_category_opens_are_controls() -> None:
    common = power_input_netlist(
        power_assignments=("COMMON_5V", "COMMON_5V"),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
    )
    documented = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
    )
    same_category = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "USB_VBUS"),
        electrical_type="passive",
    )
    controls = (
        (common, power_input_coverage(common, roles=("supply", "supply"))),
        (
            documented,
            power_input_coverage(
                documented,
                roles=("supply", "supply"),
                unconnected_pin_reasons=(None, "intentionally open"),
            ),
        ),
        (same_category, power_input_coverage(same_category, roles=("supply", "supply"))),
    )

    for observed, coverage in controls:
        report = lint_report(observed, coverage)
        assert RULE_ID not in {item.rule_id for item in report.findings}
    same_category_report = lint_report(same_category, controls[-1][1])
    assert "connector.repeated_pin_function" in {
        item.rule_id for item in same_category_report.findings
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_prompt_obeys_policy_and_exact_ignore() -> None:
    observed = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
    )
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
                    reason="Synthetic policy reviews open named supply contacts.",
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
                    reason="Synthetic map documents this contact as unused.",
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_open_peer_stays_quiet_for_different_domains_or_stale_maps() -> None:
    observed = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
    )
    dnp = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN"),
        electrical_type="passive",
        dnp=("J2",),
    )
    controls = (
        (
            observed,
            power_input_coverage(
                observed, roles=("supply", "supply"), voltage_domains=("usb", "serial")
            ),
        ),
        (
            observed,
            power_input_coverage(
                observed, roles=("supply", "supply"), peer_groups=("usb", "serial")
            ),
        ),
        (observed, power_input_coverage(observed, roles=("supply", "supply"), complete_maps=False)),
        (observed, power_input_coverage(observed, roles=(None, None))),
        (dnp, power_input_coverage(dnp, roles=("supply", "supply"))),
    )
    stale = power_input_netlist(
        power_assignments=("USB_5V", None),
        functions=("VBUS", "VDD_IN_CHANGED"),
        electrical_type="passive",
    )

    assert all(
        RULE_ID not in {item.rule_id for item in lint_report(candidate, coverage).findings}
        for candidate, coverage in controls
    )
    current_coverage = power_input_coverage(observed, roles=("supply", "supply"))
    assert RULE_ID not in {item.rule_id for item in lint_report(stale, current_coverage).findings}

    ambiguous = observed.model_copy(
        update={"nets": {**observed.nets, "EXTRA_ASSIGNMENT": ("J1.1",)}}
    )
    assert RULE_ID not in {
        item.rule_id
        for item in lint_report(
            ambiguous, power_input_coverage(ambiguous, roles=("supply", "supply"))
        ).findings
    }
