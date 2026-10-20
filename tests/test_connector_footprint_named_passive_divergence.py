"""Review named passive connector contacts assigned to different nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import (
    lint_report,
    named_passive_contact_divergence_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_named_passive_assignment_divergence"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_contacts_on_different_nets_are_reviewed_with_anchor() -> None:
    report = lint_report(named_passive_contact_divergence_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (AUX_DETECT)"
    )
    assert finding.evidence["assignments"] == ("J1.2=AUX_A", "J2.2=AUX_B")
    assert finding.evidence["pin_electrical_type"] == ("passive",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "should be joined" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.named_passive_different_assignment_pin_group_count == 1
    assert alias.named_passive_divergence_finding_count == 1
    assert alias.unanchored_named_passive_divergence_pin_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_or_ineligible_passive_divergences_are_not_findings() -> None:
    controls = (
        named_passive_contact_divergence_netlist(target_assignments=("AUX", "AUX")),
        named_passive_contact_divergence_netlist(anchor_assignments=("GND_A", "GND_B")),
        named_passive_contact_divergence_netlist(target_assignments=("AUX_A", None)),
        named_passive_contact_divergence_netlist(target_assignments=(None, None)),
        named_passive_contact_divergence_netlist(function="Pin_2"),
        named_passive_contact_divergence_netlist(function="VDD"),
        named_passive_contact_divergence_netlist(function="GND"),
        named_passive_contact_divergence_netlist().model_copy(
            update={
                "pin_functions": {
                    "J1.1": "Pin_1",
                    "J2.1": "Pin_1",
                    "J1.2": "AUX_DETECT",
                    "J2.2": "OTHER_DETECT",
                }
            }
        ),
        named_passive_contact_divergence_netlist().model_copy(
            update={
                "pin_electrical_types": {
                    "J1.1": "passive",
                    "J2.1": "passive",
                    "J1.2": "passive",
                    "J2.2": "input",
                }
            }
        ),
        *(
            named_passive_contact_divergence_netlist(electrical_type=value)
            for value in (
                "input",
                "output",
                "bidirectional",
                "power_in",
                "power_out",
                "free",
                "unspecified",
            )
        ),
        named_passive_contact_divergence_netlist(ambiguous_target=True),
        named_passive_contact_divergence_netlist(incomplete_inventory=True),
        named_passive_contact_divergence_netlist(missing_metadata_pin="J2.2"),
        named_passive_contact_divergence_netlist(dnp=("J2",)),
        named_passive_contact_divergence_netlist(part_id="SYNTHETIC-PASSIVE-001"),
    )
    for source in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(source).findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    alias = unanchored.footprint_alias_coverage
    assert alias.named_passive_different_assignment_pin_group_count == 1
    assert alias.unanchored_named_passive_divergence_pin_group_count == 1
    assert alias.named_passive_divergence_finding_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_divergence_is_stable_under_mapping_order() -> None:
    source = named_passive_contact_divergence_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    second = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_divergence_obeys_policy_and_exact_ignore() -> None:
    source = named_passive_contact_divergence_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires reviewing passive-contact net splits.",
                ),
            )
        ),
    )
    disabled = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic fixture tests the project override.",
                ),
            )
        ),
    )
    ignored = lint_report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic policy documents intentionally separate domains.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "RULE_OFF" for item in disabled.findings
    )
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
