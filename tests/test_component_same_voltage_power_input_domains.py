"""Opt-in review for split IC supply inputs with matching voltage-label clues."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_power_input_domains import (
    same_voltage_power_inputs_on_different_nets,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.same_voltage_power_inputs import (
    RULE_ID,
    same_voltage_power_input_netlist,
    same_voltage_power_input_review_policy,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_split_distinct_supply_functions_on_equal_voltage_labels_are_reviewed() -> None:
    source = same_voltage_power_input_netlist()
    groups = same_voltage_power_inputs_on_different_nets(source)
    report = evaluate(
        "synthetic-supply-domains", coach(source), same_voltage_power_input_review_policy()
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(groups) == 1
    assert groups[0].pins == {"U1.1": ("+3V3",), "U1.2": ("3.3V",)}
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert "do not establish actual voltage" in findings[0].message


def same_voltage_power_input_split_rule_ids() -> set[str]:
    report = evaluate(
        "synthetic-supply-domains",
        coach(same_voltage_power_input_netlist()),
        same_voltage_power_input_review_policy(),
    )
    return {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            same_voltage_power_input_netlist(nets={"+3V3": ("U1.1", "U1.2")}),
            id="common-net",
        ),
        pytest.param(
            same_voltage_power_input_netlist(nets={"+3V3": ("U1.1",), "+1V8": ("U1.2",)}),
            id="different-voltage-labels",
        ),
        pytest.param(
            same_voltage_power_input_netlist(
                electrical_types={"U1.1": "power_in", "U1.2": "passive"}
            ),
            id="passive-pin",
        ),
        pytest.param(
            same_voltage_power_input_netlist(functions={"U1.1": "VDD", "U1.2": "VDD"}),
            id="same-function-covered-elsewhere",
        ),
        pytest.param(same_voltage_power_input_netlist(dnp=("U1",)), id="dnp"),
        pytest.param(
            same_voltage_power_input_netlist(pin_numbers=("1", "2", "3")),
            id="incomplete-native-inventory",
        ),
        pytest.param(
            same_voltage_power_input_netlist(nets={"+3V3": ("U1.1",)}),
            id="open-supply-input",
        ),
        pytest.param(same_voltage_power_input_netlist(reference="J1"), id="connector"),
    ],
)
def test_inapplicable_or_intentional_supply_domains_stay_quiet(
    source: NetlistContract,
) -> None:
    assert same_voltage_power_inputs_on_different_nets(source) == ()
    report = evaluate(
        "synthetic-supply-domains", coach(source), same_voltage_power_input_review_policy()
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_rule_is_default_off_and_can_be_enabled_by_project_policy() -> None:
    source = same_voltage_power_input_netlist()
    disabled = evaluate("synthetic-supply-domains", coach(source), DesignLintPolicy())
    enabled = evaluate(
        "synthetic-supply-domains", coach(source), same_voltage_power_input_review_policy()
    )

    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.mode == "off"
    assert disabled_finding.disposition == "RULE_OFF"
    assert RULE_ID in {item.rule_id for item in enabled.findings}


def test_same_voltage_split_fingerprint_is_stable_under_mapping_reordering() -> None:
    source = same_voltage_power_input_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    policy = same_voltage_power_input_review_policy()
    baseline = evaluate("synthetic-supply-domains", coach(source), policy)
    repeated = evaluate("synthetic-supply-domains", coach(reordered), policy)
    baseline_finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    reordered_finding = next(item for item in repeated.findings if item.rule_id == RULE_ID)

    assert reordered_finding.fingerprint == baseline_finding.fingerprint
    assert reordered_finding.evidence == baseline_finding.evidence
