"""Fault, boundary, lifecycle, and determinism tests for mapped IC decoupling."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.ic_decoupling_models import (
    IcDecouplingCapacitorRequirement,
    IcDecouplingMap,
    IcDecouplingRequirement,
)
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ic_decoupling import (
    ic_decoupling_map,
    ic_decoupling_netlist,
)

RULE_ID = "power.ic_decoupling_below_project_minimum"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_minimum_reports_below_range_with_source_bound_evidence() -> None:
    report = evaluate(
        "synthetic-ic-decoupling",
        coach(ic_decoupling_netlist(("47nF",))),
        DesignLintPolicy(ic_decoupling_map=ic_decoupling_map()),
    )
    (finding,) = [item for item in report.findings if item.rule_id == RULE_ID]
    assert finding.mode == "review"
    assert finding.subject == "u1-vdd-decoupling: U1.1"
    assert finding.evidence["capacitor_values_pf"] == ("C1=47000",)
    assert finding.evidence["minimum_total_capacitance_pf"] == ("100000.0",)
    assert finding.evidence["observed_total_capacitance_pf"] == ("47000",)
    assert finding.evidence["basis"] == (
        "Synthetic test requirement: minimum total nominal capacitance is 100 nF",
    )
    assert finding.evidence["requirement_sha256"]
    assert "below the project-authored minimum" in finding.message
    assert "bias derating" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_minimum_and_parallel_caps_are_valid_controls() -> None:
    exact = evaluate(
        "synthetic-ic-decoupling-boundary",
        coach(ic_decoupling_netlist(("100nF",))),
        DesignLintPolicy(ic_decoupling_map=ic_decoupling_map()),
    )
    parallel = evaluate(
        "synthetic-ic-decoupling-parallel",
        coach(ic_decoupling_netlist(("47nF", "53nF"))),
        DesignLintPolicy(ic_decoupling_map=ic_decoupling_map(("C1", "C2"))),
    )
    assert RULE_ID not in {item.rule_id for item in exact.findings}
    assert RULE_ID not in {item.rule_id for item in parallel.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("observed", "expected_issue"),
    (
        (ic_decoupling_netlist(return_net="GND_ALT"), "C1.2"),
        (ic_decoupling_netlist(dnp_references=("C1",)), "DNP"),
        (ic_decoupling_netlist(dnp_references=("U1",)), "U1 is DNP"),
        (ic_decoupling_netlist(("Cload",)), "not a supported capacitance"),
        (ic_decoupling_netlist(capacitor_symbol="Device:R"), "symbol is Device:R"),
        (ic_decoupling_netlist(ic_value="Different IC"), "U1 value is Different IC"),
        (ic_decoupling_netlist(capacitor_footprint="Synthetic:0402"), "footprint is"),
    ),
)
def test_mapped_identity_topology_dnp_and_unknown_value_faults_are_reviewed(
    observed, expected_issue: str
) -> None:
    report = evaluate(
        "synthetic-ic-decoupling-map-fault",
        coach(observed),
        DesignLintPolicy(ic_decoupling_map=ic_decoupling_map()),
    )
    (finding,) = [item for item in report.findings if item.rule_id == RULE_ID]
    assert finding.evidence["mapping_issues"]
    assert expected_issue in " ".join(finding.evidence["mapping_issues"])
    assert not finding.evidence["observed_total_capacitance_pf"]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ic_decoupling_input_order_does_not_change_findings() -> None:
    observed = ic_decoupling_netlist(("47nF", "53nF"))
    policy = DesignLintPolicy(ic_decoupling_map=ic_decoupling_map(("C1", "C2")))
    first = evaluate("synthetic-ic-decoupling-order", coach(observed), policy)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    second = evaluate("synthetic-ic-decoupling-order", coach(reordered), policy)
    assert first.findings == second.findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ic_decoupling_rule_obeys_review_block_off_and_exact_ignore() -> None:
    observed = ic_decoupling_netlist(("47nF",))
    base_policy = DesignLintPolicy(ic_decoupling_map=ic_decoupling_map())
    report = evaluate("synthetic-ic-decoupling-policy", coach(observed), base_policy)
    (finding,) = [item for item in report.findings if item.rule_id == RULE_ID]
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-ic-decoupling-policy",
        coach(observed),
        base_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Synthetic exact-map blocking control",
                    ),
                )
            }
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-ic-decoupling-policy",
        coach(observed),
        base_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic exact-map disabled control",
                    ),
                )
            }
        ),
    )
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )

    ignored = evaluate(
        "synthetic-ic-decoupling-policy",
        coach(observed),
        base_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic exact-map ignore control",
                    ),
                )
            }
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ic_decoupling_map_rejects_ambiguous_component_and_pin_mappings() -> None:
    with pytest.raises(ValidationError, match="power pin must belong"):
        IcDecouplingRequirement(
            id="bad-owner",
            basis="Synthetic validation case",
            ic_reference="U1",
            expected_ic_value="Synthetic IC",
            expected_ic_symbol="Synthetic:Logic",
            expected_ic_footprint="Synthetic:QFN",
            power_pin="U2.1",
            power_net="+3V3",
            return_net="GND",
            minimum_total_capacitance_pf=100_000.0,
            capacitors=(
                IcDecouplingCapacitorRequirement(
                    reference="C1",
                    expected_symbol="Device:C",
                    expected_footprint="Synthetic:0603",
                    power_pin="C1.1",
                    return_pin="C1.2",
                ),
            ),
        )
    with pytest.raises(ValidationError, match="unique"):
        IcDecouplingMap(
            requirements=(
                ic_decoupling_map().requirements[0],
                ic_decoupling_map().requirements[0],
            )
        )
