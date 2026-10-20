"""Review explicitly named power-input contacts split across connector aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import (
    lint_report,
)
from tests.connector_footprint_peer_support import (
    named_power_input_divergence_netlist as _power_input_divergence_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

RULE_ID = "connector.footprint_named_power_input_assignment_divergence"


def test_named_power_input_on_different_nets_is_reviewed_with_a_common_anchor() -> None:
    report = lint_report(_power_input_divergence_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (BIAS_IN)"
    )
    assert finding.evidence["assignments"] == ("J1.2=BIAS_A", "J2.2=BIAS_B")
    assert finding.evidence["pin_electrical_type"] == ("power_in",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not prove the assignments are wrong" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.named_power_input_different_assignment_pin_group_count == 1
    assert alias.named_power_input_divergence_finding_count == 1
    assert alias.unanchored_named_power_input_divergence_pin_group_count == 0


def test_common_unanchored_or_ineligible_contacts_are_not_power_divergence_findings() -> None:
    controls = (
        _power_input_divergence_netlist(target_assignments=("BIAS", "BIAS")),
        _power_input_divergence_netlist(anchor_assignments=("GND_A", "GND_B")),
        _power_input_divergence_netlist(function="Pin_2"),
        _power_input_divergence_netlist(function="VDD"),
        _power_input_divergence_netlist(function="GND"),
        _power_input_divergence_netlist(electrical_type="power_out"),
        _power_input_divergence_netlist(electrical_type="input"),
        _power_input_divergence_netlist(electrical_type="output"),
        _power_input_divergence_netlist(electrical_type="passive"),
        _power_input_divergence_netlist(electrical_type="free"),
        _power_input_divergence_netlist(electrical_type="unspecified"),
        _power_input_divergence_netlist(target_assignments=("BIAS_A", None)),
        _power_input_divergence_netlist(dnp=("J2",)),
        _power_input_divergence_netlist(part_id="SYNTHETIC-POWER-INPUT-001"),
    )
    for source in controls:
        report = lint_report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    alias = unanchored.footprint_alias_coverage
    assert alias.named_power_input_different_assignment_pin_group_count == 1
    assert alias.named_power_input_divergence_finding_count == 0
    assert alias.unanchored_named_power_input_divergence_pin_group_count == 1


def test_named_power_input_divergence_is_stable_under_mapping_order() -> None:
    source = _power_input_divergence_netlist()
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


def test_named_power_input_divergence_obeys_policy_and_exact_ignore() -> None:
    source = _power_input_divergence_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of divergent power inputs.",
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
                    reason="Synthetic policy records intentional separate power domains.",
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
