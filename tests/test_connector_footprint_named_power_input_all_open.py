"""Review named power-input contacts left open across footprint aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import (
    lint_report,
    named_power_input_all_open_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_named_power_input_all_open"


def test_named_power_input_open_on_every_alias_is_reviewed_with_common_anchor() -> None:
    report = lint_report(named_power_input_all_open_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (BIAS_IN)"
    )
    assert finding.evidence["assignments"] == (
        "J1.2=<unassigned>",
        "J2.2=<unassigned>",
    )
    assert finding.evidence["pin_electrical_type"] == ("power_in",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "may be intentional" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.named_power_input_all_open_peer_pin_group_count == 1
    assert alias.named_power_input_all_open_finding_count == 1
    assert alias.unanchored_named_power_input_all_open_peer_pin_group_count == 0


def test_common_unanchored_or_ineligible_contacts_are_not_all_open_findings() -> None:
    controls = (
        named_power_input_all_open_netlist(target_assignments=("BIAS", "BIAS")),
        named_power_input_all_open_netlist(anchor_assignments=("GND_A", "GND_B")),
        named_power_input_all_open_netlist(function="Pin_2"),
        named_power_input_all_open_netlist(function="VDD"),
        named_power_input_all_open_netlist(function="GND"),
        named_power_input_all_open_netlist(electrical_type="power_out"),
        named_power_input_all_open_netlist(electrical_type="input"),
        named_power_input_all_open_netlist(electrical_type="output"),
        named_power_input_all_open_netlist(electrical_type="passive"),
        named_power_input_all_open_netlist(electrical_type="free"),
        named_power_input_all_open_netlist(electrical_type="unspecified"),
        named_power_input_all_open_netlist(target_assignments=("BIAS", None)),
        named_power_input_all_open_netlist(ambiguous_target=True),
        named_power_input_all_open_netlist(incomplete_inventory=True),
        named_power_input_all_open_netlist(missing_metadata_pin="J2.2"),
        named_power_input_all_open_netlist(dnp=("J2",)),
        named_power_input_all_open_netlist(part_id="SYNTHETIC-POWER-INPUT-ALL-OPEN-001"),
    )
    mismatched = named_power_input_all_open_netlist()
    functions = dict(mismatched.pin_functions)
    functions["J2.2"] = "OTHER_INPUT"
    controls += (mismatched.model_copy(update={"pin_functions": functions}),)

    for source in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(source).findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    alias = unanchored.footprint_alias_coverage
    assert alias.named_power_input_all_open_peer_pin_group_count == 1
    assert alias.named_power_input_all_open_finding_count == 0
    assert alias.unanchored_named_power_input_all_open_peer_pin_group_count == 1


def test_named_power_input_all_open_is_stable_under_mapping_order() -> None:
    source = named_power_input_all_open_netlist()
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


def test_named_power_input_all_open_obeys_policy_and_exact_ignore() -> None:
    source = named_power_input_all_open_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of all-open power inputs.",
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
                    reason="Synthetic policy records an intentionally unused input.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
