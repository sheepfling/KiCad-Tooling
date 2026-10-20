"""Review named passive connector contacts open on only some aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import (
    lint_report,
    named_passive_contact_open_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_named_passive_open_outlier"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_contact_open_on_one_alias_is_reviewed() -> None:
    report = lint_report(named_passive_contact_open_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (AUX_DETECT): "
        "named passive signal contact is open on a similar connector peer"
    )
    assert finding.evidence["assignments"] == (
        "J1.2=AUX_BUS",
        "J2.2=<unassigned>",
    )
    assert finding.evidence["open_pins"] == ("J2.2",)
    assert finding.evidence["pin_electrical_type"] == ("passive",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not establish" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.open_peer_pin_group_count == 1
    assert alias.open_outlier_finding_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_and_ineligible_passive_contacts_are_not_findings() -> None:
    controls = (
        named_passive_contact_open_netlist(target_assignments=("AUX_BUS", "AUX_BUS")),
        named_passive_contact_open_netlist(anchor_assignments=("GND_A", "GND_B")),
        named_passive_contact_open_netlist(target_assignments=("AUX_A", "AUX_B")),
        named_passive_contact_open_netlist(target_assignments=(None, None)),
        named_passive_contact_open_netlist(function="Pin_2"),
        named_passive_contact_open_netlist(function="VDD"),
        named_passive_contact_open_netlist(function="GND"),
        named_passive_contact_open_netlist(ambiguous_target=True),
        named_passive_contact_open_netlist(incomplete_inventory=True),
        named_passive_contact_open_netlist(missing_metadata_pin="J2.2"),
        named_passive_contact_open_netlist(dnp=("J2",)),
        named_passive_contact_open_netlist(part_id="SYNTHETIC-PASSIVE-001"),
    )
    mismatched = named_passive_contact_open_netlist()
    functions = dict(mismatched.pin_functions)
    functions["J2.2"] = "OTHER_DETECT"
    controls += (mismatched.model_copy(update={"pin_functions": functions}),)
    mismatched_type = named_passive_contact_open_netlist()
    types = dict(mismatched_type.pin_electrical_types)
    types["J2.2"] = "bidirectional"
    controls += (mismatched_type.model_copy(update={"pin_electrical_types": types}),)

    for source in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(source).findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    assert unanchored.footprint_alias_coverage.unanchored_open_peer_pin_group_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_open_finding_is_stable_under_mapping_order() -> None:
    source = named_passive_contact_open_netlist()
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
def test_named_passive_open_rule_obeys_policy_and_exact_ignore() -> None:
    source = named_passive_contact_open_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of this exposed connector contact.",
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
                    reason="Synthetic fixture tests an explicit project override.",
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
                    reason="Synthetic policy leaves this passive connector contact unused.",
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
