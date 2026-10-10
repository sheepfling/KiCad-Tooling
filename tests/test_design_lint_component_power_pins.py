"""Focused synthetic regressions for the component power pins lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    observed,
    repeated_component_supply_pins,
    unconnected_component_power_pins,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


def test_repeated_component_supply_pins_on_different_nets_need_review() -> None:
    report = evaluate(
        "synthetic-component-supplies",
        coach(repeated_component_supply_pins()),
        DesignLintPolicy(),
    )
    findings = [
        item for item in report.findings if item.rule_id == "component.repeated_supply_pin_function"
    ]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "U1 (Synthetic:MultiSupplyLogic): VDD supply pins"
    assert findings[0].evidence == {"U1.1": ("+3V3",), "U1.2": ("+1V8",)}
    assert "intended split" in findings[0].message


def test_repeated_supply_mapping_order_is_stable_and_shared_rail_clears_it() -> None:
    source = repeated_component_supply_pins()
    original = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate(
        "synthetic-component-supplies",
        coach(reordered_source),
        DesignLintPolicy(),
    )
    original_finding = next(
        item
        for item in original.findings
        if item.rule_id == "component.repeated_supply_pin_function"
    )
    reordered_finding = next(
        item
        for item in reordered.findings
        if item.rule_id == "component.repeated_supply_pin_function"
    )

    assert reordered_finding.evidence == original_finding.evidence
    assert reordered_finding.fingerprint == original_finding.fingerprint

    shared_rail = source.model_copy(update={"nets": {"+3V3": ("U1.1", "U1.2")}})
    repaired = evaluate("synthetic-component-supplies", coach(shared_rail), DesignLintPolicy())
    assert "component.repeated_supply_pin_function" not in {
        item.rule_id for item in repaired.findings
    }


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(repeated_component_supply_pins(split=False), id="shared-rail"),
        pytest.param(
            repeated_component_supply_pins(second_function="VDDIO"),
            id="distinct-function",
        ),
        pytest.param(repeated_component_supply_pins(dnp=True), id="dnp-split"),
    ],
)
def test_shared_rail_distinct_supply_functions_and_dnp_are_controls(
    source: NetlistContract,
) -> None:
    report = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())

    assert "component.repeated_supply_pin_function" not in {
        item.rule_id for item in report.findings
    }


def test_unassigned_duplicate_supply_pin_uses_specific_open_pin_rule() -> None:
    report = evaluate(
        "synthetic-component-supplies",
        coach(repeated_component_supply_pins(second_pin_assigned=False)),
        DesignLintPolicy(),
    )
    rule_ids = {item.rule_id for item in report.findings}

    assert "component.unconnected_supply_pin" in rule_ids
    assert "component.repeated_supply_pin_function" not in rule_ids


def test_repeated_supply_finding_uses_project_override_and_exact_ignore() -> None:
    source = repeated_component_supply_pins()
    initial = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
    finding = next(
        item
        for item in initial.findings
        if item.rule_id == "component.repeated_supply_pin_function"
    )
    ignored_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id="component.repeated_supply_pin_function",
                fingerprint=finding.fingerprint,
                reason="Synthetic control records an intentionally filtered rail split",
            ),
        )
    )
    ignored = evaluate("synthetic-component-supplies", coach(source), ignored_policy)
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == "component.repeated_supply_pin_function"
    )

    assert ignored.status == "PASS"
    assert ignored_finding.disposition == "IGNORED"

    changed_source = source.model_copy(update={"nets": {"+3V3": ("U1.1",), "+2V5": ("U1.2",)}})
    changed = evaluate("synthetic-component-supplies", coach(changed_source), ignored_policy)
    assert changed.status == "REVIEW"
    assert changed.stale_ignores == ignored_policy.ignores

    blocking_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="component.repeated_supply_pin_function",
                mode="block",
                reason="Synthetic project requires reviewed same-function supply pins",
            ),
        )
    )
    blocked = evaluate("synthetic-component-supplies", coach(source), blocking_policy)
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"


def test_ambiguous_component_supply_assignment_is_reported() -> None:
    source = repeated_component_supply_pins().model_copy(
        update={
            "nets": {
                "+3V3": ("U1.1", "U1.2"),
                "+1V8": ("U1.1",),
            }
        }
    )
    report = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
    finding = next(
        item for item in report.findings if item.rule_id == "component.repeated_supply_pin_function"
    )

    assert finding.evidence["U1.1"] == ("+1V8", "+3V3")


def test_open_findings_include_missing_power_and_separate_returns() -> None:
    report = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
    power = next(item for item in report.findings if item.subject.endswith("PWR"))

    assert report.status == "REVIEW"
    assert len(report.findings) == 3
    assert power.evidence["J3.1"] == ()
    assert power.disposition == "OPEN"
    assert {item.rule_id for item in report.findings} == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert all(len(item.fingerprint) == 64 for item in report.findings)
    assert not report.build_authorized


def test_unconnected_component_supply_and_return_pins_need_review() -> None:
    report = evaluate(
        "synthetic-logic", coach(unconnected_component_power_pins()), DesignLintPolicy()
    )

    assert report.status == "REVIEW"
    assert {item.rule_id for item in report.findings} == {
        "component.unconnected_supply_pin",
        "component.unconnected_return_pin",
    }
    assert {item.subject: item.evidence for item in report.findings} == {
        "U1.1: VDD": {"U1.1": ()},
        "U1.2: GND": {"U1.2": ()},
    }

    connected = evaluate(
        "synthetic-logic",
        coach(unconnected_component_power_pins(connected=True)),
        DesignLintPolicy(),
    )
    assert connected.status == "PASS"
    assert not connected.findings


def test_component_open_power_pin_findings_are_order_stable_and_assignment_clears_them() -> None:
    base = unconnected_component_power_pins()
    source = base.model_copy(
        update={
            "components": {
                **base.components,
                "U2": ComponentContract(value="Unrelated logic", footprint=""),
                "U3": ComponentContract(value="Unrelated logic", footprint=""),
            },
            "nets": {
                **base.nets,
                "AUX_A": ("U2.1",),
                "AUX_B": ("U3.1",),
            },
            "component_symbols": {
                **base.component_symbols,
                "U2": "Synthetic:Logic",
                "U3": "Synthetic:Logic",
            },
            "pin_functions": {
                **base.pin_functions,
                "U2.1": "DATA",
                "U3.1": "DATA",
            },
        }
    )
    original = evaluate("synthetic-logic", coach(source), DesignLintPolicy())
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate("synthetic-logic", coach(reordered_source), DesignLintPolicy())
    target_rules = {
        "component.unconnected_supply_pin",
        "component.unconnected_return_pin",
    }
    original_findings = {
        item.rule_id: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id in target_rules
    }
    reordered_findings = {
        item.rule_id: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id in target_rules
    }

    assert set(original_findings) == target_rules
    assert reordered_findings == original_findings

    repaired = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "+3V3": ("U1.1",),
                "GND": ("U1.2",),
            }
        }
    )
    repaired_report = evaluate("synthetic-logic", coach(repaired), DesignLintPolicy())
    assert not target_rules & {item.rule_id for item in repaired_report.findings}
