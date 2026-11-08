"""Project-authored native pin-role checks for mapped regulator topology."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.test_regulator_feedback import regulator_netlist
from tests.test_regulator_required_passives import RULE_ID as TOPOLOGY_RULE_ID
from tests.test_regulator_required_passives import topology_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_pin_role_mismatch"


def valid_topology_netlist(*, fault: str | None = None):
    return regulator_netlist(fault=fault, with_compensation_capacitor=True)


def lint(source, *, mode: str | None = None, map_roles: bool = True):
    authored_map = topology_map()
    if not map_roles:
        requirement = authored_map.requirements[0]
        regulator = requirement.regulator.model_copy(
            update={
                "pins": tuple(
                    pin.model_copy(
                        update={"expected_function": None, "expected_electrical_type": None}
                    )
                    for pin in requirement.regulator.pins
                )
            }
        )
        authored_map = authored_map.model_copy(
            update={"requirements": (requirement.model_copy(update={"regulator": regulator}),)}
        )
    policy = DesignLintPolicy(
        regulator_passive_topology_map=authored_map,
        rules=()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic pin-role policy exercise",
            ),
        ),
    )
    return evaluate(
        "synthetic-regulator",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator",
            observed=source,
            netlist_sha256="b" * 64,
        ),
        policy,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_authored_native_function_and_type_are_a_valid_control() -> None:
    report = lint(valid_topology_netlist())
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_pin_and_net_with_a_different_function_is_reviewed() -> None:
    source = valid_topology_netlist(fault="wrong-feedback-function")
    report = lint(source)

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert "U1.2 native function is 'VOUT'; expected 'FB'" in finding.message
    assert not any(item.rule_id == TOPOLOGY_RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_pin_and_net_with_a_different_electrical_type_is_reviewed() -> None:
    source = valid_topology_netlist().model_copy(
        update={
            "pin_electrical_types": {
                **valid_topology_netlist().pin_electrical_types,
                "U1.2": "output",
            }
        }
    )
    report = lint(source)

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert "U1.2 native electrical type is 'output'; expected 'input'" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_expected_native_metadata_is_not_reported_as_coverage() -> None:
    source = valid_topology_netlist()
    report = lint(
        source.model_copy(
            update={
                "pin_functions": {
                    pin: function for pin, function in source.pin_functions.items() if pin != "U1.2"
                },
                "pin_electrical_types": {
                    pin: electrical_type
                    for pin, electrical_type in source.pin_electrical_types.items()
                    if pin != "U1.2"
                },
            }
        )
    )

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert "U1.2 native pin function is unavailable" in finding.message
    assert "U1.2 native electrical type is unavailable" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_pin_roles_keep_existing_topology_behavior() -> None:
    source = valid_topology_netlist(fault="wrong-feedback-function")
    report = lint(source, map_roles=False)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_block_or_disable_a_pin_role_mismatch() -> None:
    source = valid_topology_netlist(fault="wrong-feedback-function")

    blocked = lint(source, mode="block")
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"

    disabled = lint(source, mode="off")
    finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert finding.disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_order_is_stable_for_mapping_order_changes() -> None:
    source = regulator_netlist(fault="wrong-feedback-function")
    reordered = source.model_copy(
        update={
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    assert lint(source).findings == lint(reordered).findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_changed_native_function_changes_source_bound_fingerprint() -> None:
    source = valid_topology_netlist(fault="wrong-feedback-function")
    changed = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.2": "COMP"},
        }
    )
    source_finding = next(item for item in lint(source).findings if item.rule_id == RULE_ID)
    changed_finding = next(item for item in lint(changed).findings if item.rule_id == RULE_ID)

    assert source_finding.fingerprint != changed_finding.fingerprint
