"""Regressions for divergent assignments on named component power-input peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.component_peer_power_assignment_support import lint_report
from tests.component_peer_power_input_support import (
    NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
    named_peer_power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_named_peer_power_input_split_is_reviewed_with_controls() -> None:
    fault = named_peer_power_input_netlist(assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"))
    report = lint_report(fault)
    findings = [
        item
        for item in report.findings
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    ]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == (
        "Lint:NamedPeerPowerInput pin 1 (BIAS_IN): named power-input peer assignments differ"
    )
    assert finding.evidence["U1.1"] == ("SYNTHETIC_RAIL_A",)
    assert finding.evidence["U2.1"] == ("SYNTHETIC_RAIL_B",)
    assert "does not establish that the nets must be common" in finding.message
    coverage = next(
        item
        for item in report.component_peer_pin_coverage
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    )
    assert coverage.status == "EVALUATED"
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.complete_pin_inventory_group_count == 1
    assert coverage.matching_electrical_type_pin_group_count == 1
    assert coverage.compatible_function_pin_group_count == 1
    assert coverage.unambiguous_assignment_pin_group_count == 1
    assert coverage.open_assignment_pin_group_count == 0
    assert coverage.candidate_group_count == coverage.finding_count == 1

    ambiguous = named_peer_power_input_netlist(assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"))
    ambiguous_nets = dict(ambiguous.nets)
    ambiguous_nets["SYNTHETIC_EXTRA"] = ("U1.1",)
    controls = (
        (
            named_peer_power_input_netlist(assignments=("+3V3", "+3V3")),
            "EVALUATED",
        ),
        (named_peer_power_input_netlist(), "NO_COMPLETE_ASSIGNMENTS"),
        (
            named_peer_power_input_netlist(assignments=(None, None)),
            "NO_COMPLETE_ASSIGNMENTS",
        ),
        (
            named_peer_power_input_netlist(functions={"U1": "VDD", "U2": "VDD"}),
            "NO_COMPATIBLE_PIN_FUNCTIONS",
        ),
        (
            named_peer_power_input_netlist(functions={"U1": "1", "U2": "1"}),
            "NO_COMPATIBLE_PIN_FUNCTIONS",
        ),
        (
            named_peer_power_input_netlist(functions={"U2": "BIAS_OUT"}),
            "NO_COMPATIBLE_PIN_FUNCTIONS",
        ),
        (
            named_peer_power_input_netlist(electrical_types={"U2": "input"}),
            "NO_MATCHING_PIN_TYPES",
        ),
        (
            named_peer_power_input_netlist(incomplete_inventory=("U2",)),
            "INCOMPLETE_PIN_INVENTORY",
        ),
        (
            named_peer_power_input_netlist(dnp=("U2",)),
            "NO_COMPARABLE_PEERS",
        ),
        (
            named_peer_power_input_netlist(references=("J1", "J2")),
            "NO_COMPARABLE_PEERS",
        ),
        (
            named_peer_power_input_netlist(
                symbols={
                    "U1": "Synthetic:NamedPeerA",
                    "U2": "Synthetic:NamedPeerB",
                }
            ),
            "NO_COMPARABLE_PEERS",
        ),
        (
            ambiguous.model_copy(update={"nets": ambiguous_nets}),
            "NO_UNAMBIGUOUS_ASSIGNMENTS",
        ),
    )
    for control, expected_status in controls:
        control_report = lint_report(control)
        assert NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID not in {
            item.rule_id for item in control_report.findings
        }
        control_coverage = next(
            item
            for item in control_report.component_peer_pin_coverage
            if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
        )
        assert control_coverage.status == expected_status
        assert control_coverage.finding_count == 0
        if expected_status == "NO_COMPLETE_ASSIGNMENTS":
            assert control_coverage.open_assignment_pin_group_count == 1


def test_named_peer_power_input_identity_is_guarded() -> None:
    source = named_peer_power_input_netlist(
        symbols={"U1": "Synthetic:NamedPeerA", "U2": "Synthetic:NamedPeerB"},
        part_ids={"U1": "SYNTHETIC-NAMED-INPUT", "U2": "synthetic-named-input"},
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
    )
    report = lint_report(source)
    finding = next(
        item
        for item in report.findings
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    )
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_identity"] == ("SYNTHETIC-NAMED-INPUT",)
    assert finding.evidence["peer_symbols"] == ("Synthetic:NamedPeerA", "Synthetic:NamedPeerB")

    mismatched = named_peer_power_input_netlist(
        symbols={"U1": "Synthetic:NamedPeerA", "U2": "Synthetic:NamedPeerB"},
        part_ids={"U1": "SYNTHETIC-NAMED-INPUT", "U2": "SYNTHETIC-NAMED-INPUT"},
        values={"U2": "Different synthetic value"},
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
    )
    mismatch_report = lint_report(mismatched)
    assert NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID not in {
        item.rule_id for item in mismatch_report.findings
    }
    mismatch_coverage = next(
        item
        for item in mismatch_report.component_peer_pin_coverage
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    )
    assert mismatch_coverage.status == "INCOMPLETE_COMPONENT_IDENTITY"
    assert mismatch_coverage.part_id_incomplete_component_identity_references == ("U1", "U2")


def test_named_peer_power_input_rule_obeys_override_and_ignore_lifecycle() -> None:
    source = named_peer_power_input_netlist(assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"))
    finding = next(
        item
        for item in lint_report(source).findings
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    )
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
                    mode="block",
                    reason="Synthetic board contract requires one reviewed input domain",
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
                    rule_id=NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
                    mode="off",
                    reason="Synthetic split domains are approved as intentional",
                ),
            )
        ),
    )
    assert any(
        item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID and item.disposition == "RULE_OFF"
        for item in disabled.findings
    )

    ignore = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic project reviewed the separate input domains",
            ),
        )
    )
    ignored = lint_report(source, ignore)
    assert any(
        item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID and item.disposition == "IGNORED"
        for item in ignored.findings
    )

    changed = source.model_copy(
        update={
            "nets": {
                "+3V3": ("U1.1", "U2.1"),
                "SIGNAL": ("U1.2", "U2.2"),
            }
        }
    )
    stale = lint_report(changed, ignore)
    assert stale.stale_ignores == ignore.ignores


def test_named_peer_power_input_split_is_stable_under_mapping_order() -> None:
    source = named_peer_power_input_netlist(
        references=("U3", "U1", "U2"),
        symbols={
            "U1": "Synthetic:NamedPeerPowerInput",
            "U2": "synthetic:namedpeerpowerinput",
            "U3": "Synthetic:NamedPeerPowerInput",
        },
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B", "SYNTHETIC_RAIL_A"),
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
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    ]
    second = [
        item
        for item in lint_report(reordered).findings
        if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
    ]

    assert [(item.subject, item.evidence, item.fingerprint) for item in second] == [
        (item.subject, item.evidence, item.fingerprint) for item in first
    ]
