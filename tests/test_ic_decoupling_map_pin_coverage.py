"""Fault, control, scope, policy, and determinism tests for IC map coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.power_ic_decoupling_map_coverage import (
    ic_decoupling_map_coverage_issues,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ic_decoupling import (
    ic_decoupling_map_coverage_map,
    ic_decoupling_map_coverage_netlist,
    ic_decoupling_map_omitted_component_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID = "power.ic_decoupling_map_pin_coverage"


def _review_policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        ic_decoupling_map=ic_decoupling_map_coverage_map(),
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic test explicitly selects map-coverage review",
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_native_power_input_pin_needs_review() -> None:
    policy = _review_policy()
    report = evaluate(
        "synthetic-ic-map-coverage", coach(ic_decoupling_map_coverage_netlist()), policy
    )
    (finding,) = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.evidence["component"] == ("U1",)
    assert finding.evidence["native_power_input_pins"] == ("U1.1", "U1.3", "U1.4")
    assert finding.evidence["mapped_power_pins"] == ("U1.1",)
    assert finding.evidence["unmapped_power_input_pins"] == ("U1.3", "U1.4")
    assert finding.evidence["map_sha256"]
    assert "does not infer that a capacitor is required" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_pin_metadata_needs_review() -> None:
    observed = ic_decoupling_map_coverage_netlist()
    missing_type = observed.model_copy(
        update={
            "pin_electrical_types": {
                key: value for key, value in observed.pin_electrical_types.items() if key != "U1.4"
            }
        }
    )
    missing_inventory = observed.model_copy(
        update={
            "component_pin_numbers": {
                key: value for key, value in observed.component_pin_numbers.items() if key != "U1"
            }
        }
    )
    disagreement = observed.model_copy(update={"component_pin_numbers": {"U1": ("1", "2", "3")}})

    (missing_type_issue,) = ic_decoupling_map_coverage_issues(
        missing_type, ic_decoupling_map_coverage_map()
    )
    (missing_inventory_issue,) = ic_decoupling_map_coverage_issues(
        missing_inventory, ic_decoupling_map_coverage_map()
    )
    (disagreement_issue,) = ic_decoupling_map_coverage_issues(
        disagreement, ic_decoupling_map_coverage_map()
    )

    assert missing_type_issue.pin_type_unavailable_pins == ("U1.4",)
    assert missing_inventory_issue.pin_inventory_unavailable
    assert disagreement_issue.pin_inventory_disagreement_pins == ("U1.4",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_current_pin_map_is_quiet() -> None:
    observed = ic_decoupling_map_coverage_netlist()
    pin_types = dict(observed.pin_electrical_types)
    pin_types["U1.2"] = "power_in"
    observed = observed.model_copy(
        update={
            "pin_electrical_types": pin_types,
            "pin_functions": {**observed.pin_functions, "U1.2": "GND"},
        }
    )
    requirements = ic_decoupling_map_coverage_map(("U1.1", "U1.3", "U1.4"))

    assert not ic_decoupling_map_coverage_issues(observed, requirements)
    report = evaluate(
        "synthetic-ic-map-coverage-control",
        coach(observed),
        _review_policy().model_copy(update={"ic_decoupling_map": requirements}),
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_fitted_ic_with_native_power_input_needs_component_review() -> None:
    observed = ic_decoupling_map_omitted_component_netlist()
    issues = ic_decoupling_map_coverage_issues(observed, ic_decoupling_map_coverage_map())
    (issue,) = tuple(item for item in issues if item.reference == "U2")

    assert issue.component_unmapped_from_map
    assert issue.native_power_input_pins == ("U2.1",)
    assert issue.unmapped_power_input_pins == ("U2.1",)
    assert issue.mapped_power_pins == ()
    report = evaluate(
        "synthetic-ic-map-coverage-omitted-component", coach(observed), _review_policy()
    )
    (finding,) = tuple(
        item
        for item in report.findings
        if item.rule_id == RULE_ID and item.evidence["component"] == ("U2",)
    )
    assert "has no entry for fitted U2" in finding.message
    assert finding.evidence["component_unmapped_from_map"] == ("true",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_return_function_is_not_a_component_coverage_candidate() -> None:
    observed = ic_decoupling_map_omitted_component_netlist()
    observed = observed.model_copy(
        update={
            "pin_functions": {**observed.pin_functions, "U2.1": "GND"},
        }
    )

    issues = ic_decoupling_map_coverage_issues(observed, ic_decoupling_map_coverage_map())

    assert tuple(issue.reference for issue in issues) == ("U1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_casefold_component_and_pin_metadata_are_not_discovered() -> None:
    observed = ic_decoupling_map_omitted_component_netlist()
    observed = observed.model_copy(
        update={
            "components": {**observed.components, "u2": observed.components["U2"]},
            "component_symbols": {
                **observed.component_symbols,
                "u2": observed.component_symbols["U2"],
            },
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "u2": observed.component_pin_numbers["U2"],
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "u2.1": "power_in",
            },
            "pin_functions": {**observed.pin_functions, "u2.1": "VDD"},
        }
    )

    issues = ic_decoupling_map_coverage_issues(observed, ic_decoupling_map_coverage_map())

    assert tuple(issue.reference for issue in issues) == ("U1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_non_ic_and_unmapped_non_supply_components_stay_out_of_scope() -> None:
    observed = ic_decoupling_map_coverage_netlist()
    requirements = ic_decoupling_map_coverage_map()

    dnp = observed.model_copy(update={"dnp_components": ("U1",)})
    assert not ic_decoupling_map_coverage_issues(dnp, requirements)

    non_ic_map = requirements.model_copy(
        update={
            "requirements": tuple(
                item.model_copy(
                    update={
                        "ic_reference": "J1",
                        "power_pin": "J1.1",
                        "capacitors": tuple(item.capacitors),
                    }
                )
                for item in requirements.requirements
            )
        }
    )
    non_ic_observed = observed.model_copy(
        update={
            "components": {"J1": observed.components["U1"]},
            "component_symbols": {"J1": "Synthetic:Connector"},
            "component_pin_numbers": {"J1": ("1",)},
            "pin_electrical_types": {"J1.1": "power_in"},
            "pin_functions": {"J1.1": "VDD"},
        }
    )
    assert not ic_decoupling_map_coverage_issues(non_ic_observed, non_ic_map)

    with_unmapped_ic_without_power_metadata = ic_decoupling_map_omitted_component_netlist().model_copy(
        update={
            "pin_electrical_types": {
                key: value
                for key, value in ic_decoupling_map_omitted_component_netlist().pin_electrical_types.items()
                if not key.startswith("U2.")
            }
        }
    )
    issues = ic_decoupling_map_coverage_issues(
        with_unmapped_ic_without_power_metadata, requirements
    )
    assert tuple(issue.reference for issue in issues) == ("U1",)
    assert not issues[0].component_unmapped_from_map
    assert not ic_decoupling_map_coverage_issues(observed, None)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_map_identity_needs_review() -> None:
    requirements = ic_decoupling_map_coverage_map()
    stale = requirements.model_copy(
        update={
            "requirements": tuple(
                item.model_copy(update={"expected_ic_value": "Different synthetic IC"})
                for item in requirements.requirements
            )
        }
    )
    (issue,) = ic_decoupling_map_coverage_issues(ic_decoupling_map_coverage_netlist(), stale)

    assert issue.stale_map_identity


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_requirement_order_does_not_change_issue_identity_or_order() -> None:
    observed = ic_decoupling_map_coverage_netlist()
    requirements = ic_decoupling_map_coverage_map(("U1.1", "U1.4"))
    reordered = requirements.model_copy(
        update={"requirements": tuple(reversed(requirements.requirements))}
    )

    assert ic_decoupling_map_coverage_issues(observed, requirements) == (
        ic_decoupling_map_coverage_issues(observed, reordered)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_and_map_mapping_order_does_not_change_finding() -> None:
    observed = ic_decoupling_map_omitted_component_netlist()
    reordered_observed = observed.model_copy(
        update={
            field: dict(reversed(tuple(getattr(observed, field).items())))
            for field in (
                "components",
                "component_symbols",
                "component_pin_numbers",
                "pin_functions",
                "pin_electrical_types",
                "nets",
            )
        }
    )
    requirements = ic_decoupling_map_coverage_map(("U1.1", "U1.4"))
    reordered_map = requirements.model_copy(
        update={"requirements": tuple(reversed(requirements.requirements))}
    )
    policy = _review_policy().model_copy(update={"ic_decoupling_map": requirements})
    reordered_policy = policy.model_copy(update={"ic_decoupling_map": reordered_map})
    first = evaluate("synthetic-ic-map-coverage-order", coach(observed), policy)
    second = evaluate(
        "synthetic-ic-map-coverage-order",
        coach(reordered_observed),
        reordered_policy,
    )

    assert first.findings == second.findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_is_opt_in_and_supports_review_block_off_and_exact_ignore() -> None:
    observed = ic_decoupling_map_coverage_netlist()
    requirements = ic_decoupling_map_coverage_map()
    default_report = evaluate(
        "synthetic-ic-map-coverage-policy",
        coach(observed),
        DesignLintPolicy(ic_decoupling_map=requirements),
    )
    (default_finding,) = [item for item in default_report.findings if item.rule_id == RULE_ID]
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"

    review_policy = _review_policy()
    review = evaluate("synthetic-ic-map-coverage-policy", coach(observed), review_policy)
    (review_finding,) = [item for item in review.findings if item.rule_id == RULE_ID]
    assert review_finding.mode == "review"

    blocking = review_policy.model_copy(
        update={
            "rules": (
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic explicit blocking control",
                ),
            )
        }
    )
    assert evaluate("synthetic-ic-map-coverage-policy", coach(observed), blocking).status == "FAIL"

    disabled = review_policy.model_copy(
        update={
            "rules": (
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic explicit disabled control",
                ),
            )
        }
    )
    off = evaluate("synthetic-ic-map-coverage-policy", coach(observed), disabled)
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"

    ignored = review_policy.model_copy(
        update={
            "ignores": (
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=review_finding.fingerprint,
                    reason="Synthetic exact-fingerprint ignore control",
                ),
            )
        }
    )
    ignore_report = evaluate("synthetic-ic-map-coverage-policy", coach(observed), ignored)
    assert next(item for item in ignore_report.findings if item.rule_id == RULE_ID).disposition == (
        "IGNORED"
    )
