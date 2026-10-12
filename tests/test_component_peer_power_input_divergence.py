"""Generic component peer power-input assignment regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_connector_report import connector_peer_report_lines
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.component_peer_power_assignment_support import lint_report
from tests.component_peer_power_input_support import (
    GENERIC_PEER_POWER_INPUT_RULE_ID,
    generic_peer_power_input_netlist,
)

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint, pytest.mark.power_lint]


def test_generic_peer_power_input_split_is_reviewed_with_bounded_controls() -> None:
    fault = generic_peer_power_input_netlist()
    report = lint_report(fault)
    findings = [
        item for item in report.findings if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
    ]

    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == (
        "Lint:GenericPowerInputPeer pin 1: generic peer power-input assignments differ"
    )
    assert finding.evidence["U1.1"] == ("SYNTHETIC_RAIL_A",)
    assert finding.evidence["U2.1"] == ("SYNTHETIC_RAIL_B",)
    assert "do not prove that the rails must be common" in finding.message
    coverage = next(
        item
        for item in report.component_peer_pin_coverage
        if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
    )
    assert coverage.status == "EVALUATED"
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.complete_pin_inventory_group_count == 1
    assert coverage.matching_electrical_type_pin_group_count == 1
    assert coverage.compatible_function_pin_group_count == 1
    assert coverage.unambiguous_assignment_pin_group_count == 1
    assert coverage.open_assignment_pin_group_count == 0
    assert coverage.candidate_group_count == coverage.finding_count == 1

    controls = (
        (generic_peer_power_input_netlist(assignments=("+3V3", "+3V3")), "EVALUATED"),
        (generic_peer_power_input_netlist(dnp=("U2",)), "NO_COMPARABLE_PEERS"),
        (generic_peer_power_input_netlist(references=("J1", "J2")), "NO_COMPARABLE_PEERS"),
        (generic_peer_power_input_netlist(assignments=("+5V", None)), "NO_COMPLETE_ASSIGNMENTS"),
        (
            generic_peer_power_input_netlist(incomplete_inventory=("U2",)),
            "INCOMPLETE_PIN_INVENTORY",
        ),
        (
            generic_peer_power_input_netlist(
                functions={"U1": "VDD", "U2": "VDD"},
            ),
            "NO_COMPATIBLE_PIN_FUNCTIONS",
        ),
        (
            generic_peer_power_input_netlist(electrical_types={"U2": "input"}),
            "NO_MATCHING_PIN_TYPES",
        ),
        (
            generic_peer_power_input_netlist(
                symbols={
                    "U1": "Synthetic:GenericPowerInputPeer",
                    "U2": "Synthetic:DifferentPowerInputPeer",
                }
            ),
            "NO_COMPARABLE_PEERS",
        ),
    )
    for control, expected_status in controls:
        control_report = lint_report(control)
        assert GENERIC_PEER_POWER_INPUT_RULE_ID not in {
            item.rule_id for item in control_report.findings
        }
        coverage = next(
            item
            for item in control_report.component_peer_pin_coverage
            if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
        )
        assert coverage.status == expected_status
        assert coverage.finding_count == 0
        if expected_status == "NO_COMPLETE_ASSIGNMENTS":
            assert coverage.open_assignment_pin_group_count == 1
            assert coverage.unambiguous_assignment_pin_group_count == 1
            assert any(
                GENERIC_PEER_POWER_INPUT_RULE_ID in line and "open assignments: 1" in line
                for line in connector_peer_report_lines(control_report)
            )
        if expected_status == "INCOMPLETE_PIN_INVENTORY":
            assert coverage.incomplete_pin_inventory_group_count == 1
            assert set(coverage.incomplete_pin_inventory_references) == {"U1", "U2"}


def test_generic_peer_power_input_rule_obeys_override_and_ignore_lifecycle() -> None:
    source = generic_peer_power_input_netlist()
    finding = next(
        item
        for item in lint_report(source).findings
        if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
    )
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=GENERIC_PEER_POWER_INPUT_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires reviewed peer power domains",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=GENERIC_PEER_POWER_INPUT_RULE_ID,
                    mode="off",
                    reason="Synthetic split rails are approved as isolated",
                ),
            )
        ),
    )
    assert any(
        item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID and item.disposition == "RULE_OFF"
        for item in disabled.findings
    )

    ignore = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=GENERIC_PEER_POWER_INPUT_RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic project reviewed the split supply domains",
            ),
        )
    )
    ignored = lint_report(source, ignore)
    assert any(
        item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID and item.disposition == "IGNORED"
        for item in ignored.findings
    )

    changed = source.model_copy(
        update={"nets": {"+3V3": ("U1.1", "U2.1"), "SIGNAL": ("U1.2", "U2.2")}}
    )
    stale = lint_report(changed, ignore)
    assert stale.stale_ignores == ignore.ignores


def test_generic_peer_power_input_findings_are_stable_under_mapping_order() -> None:
    source = generic_peer_power_input_netlist(
        references=("U3", "U1", "U2"),
        assignments=("+5V", "+3V3", "+5V"),
        symbols={
            "U1": "Synthetic:GenericPowerInputPeer",
            "U2": "synthetic:genericpowerinputpeer",
            "U3": "Synthetic:GenericPowerInputPeer",
        },
    )
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
    first = [
        item
        for item in lint_report(source).findings
        if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
    ]
    second = [
        item
        for item in lint_report(reordered).findings
        if item.rule_id == GENERIC_PEER_POWER_INPUT_RULE_ID
    ]

    assert [(item.subject, item.evidence, item.fingerprint) for item in second] == [
        (item.subject, item.evidence, item.fingerprint) for item in first
    ]
