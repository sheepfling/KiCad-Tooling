"""Project-authored role checks for active regulator-support components."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.regulator_support_models import (
    RegulatorSupportComponentRequirement,
    RegulatorSupportPinRoleExpectation,
    RegulatorSupportPinRoleMap,
    RegulatorSupportTopologyRequirement,
)
from tests.test_regulator_feedback import regulator_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_support_pin_role_mismatch"


def support_map() -> RegulatorSupportPinRoleMap:
    return RegulatorSupportPinRoleMap(
        basis="Synthetic independently reviewed feedback-support pin map",
        requirements=(
            RegulatorSupportTopologyRequirement(
                id="synthetic-feedback",
                basis="Synthetic optocoupler and secondary-reference role map",
                regulator_reference="U1",
                components=(
                    RegulatorSupportComponentRequirement(
                        role="feedback isolator",
                        reference="U2",
                        value="SYNTH-ISO",
                        symbol="Synthetic:FeedbackIsolator",
                        footprint="Synthetic:SOIC-4",
                        pins=(
                            RegulatorSupportPinRoleExpectation(
                                pin="U2.1",
                                expected_function="IN",
                                expected_electrical_type="input",
                            ),
                            RegulatorSupportPinRoleExpectation(
                                pin="U2.2",
                                expected_function="OUT",
                                expected_electrical_type="output",
                            ),
                        ),
                    ),
                    RegulatorSupportComponentRequirement(
                        role="secondary reference",
                        reference="U3",
                        value="SYNTH-REF",
                        symbol="Synthetic:SecondaryReference",
                        footprint="Synthetic:SOT-23-3",
                        pins=(
                            RegulatorSupportPinRoleExpectation(
                                pin="U3.1", expected_function="K", expected_electrical_type="output"
                            ),
                            RegulatorSupportPinRoleExpectation(
                                pin="U3.2",
                                expected_function="A",
                                expected_electrical_type="passive",
                            ),
                            RegulatorSupportPinRoleExpectation(
                                pin="U3.3",
                                expected_function="REF",
                                expected_electrical_type="input",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def support_netlist(*, fault: str | None = None) -> NetlistContract:
    source = regulator_netlist()
    components = {
        **source.components,
        "U2": ComponentContract(value="SYNTH-ISO", footprint="Synthetic:SOIC-4"),
        "U3": ComponentContract(value="SYNTH-REF", footprint="Synthetic:SOT-23-3"),
    }
    symbols = {
        **source.component_symbols,
        "U2": "Synthetic:FeedbackIsolator",
        "U3": "Synthetic:SecondaryReference",
    }
    functions = {
        **source.pin_functions,
        "U2.1": "IN",
        "U2.2": "OUT",
        "U3.1": "K",
        "U3.2": "A",
        "U3.3": "REF",
    }
    electrical_types = {
        **source.pin_electrical_types,
        "U2.1": "input",
        "U2.2": "output",
        "U3.1": "output",
        "U3.2": "passive",
        "U3.3": "input",
    }
    inventories = {
        **source.component_pin_numbers,
        "U2": ("1", "2"),
        "U3": ("1", "2", "3"),
    }
    dnp = source.dnp_components
    if fault == "wrong-optocoupler-function":
        functions["U2.1"] = "OUT"
    elif fault == "wrong-reference-type":
        electrical_types["U3.3"] = "output"
    elif fault == "missing-native-role":
        del functions["U3.2"]
    elif fault == "wrong-support-identity":
        components["U2"] = ComponentContract(value="SYNTH-OTHER", footprint="Synthetic:SOIC-4")
    elif fault == "wrong-support-symbol":
        symbols["U2"] = "Synthetic:OtherDevice"
    elif fault == "wrong-support-footprint":
        components["U2"] = ComponentContract(value="SYNTH-ISO", footprint="Synthetic:QFN-4")
    elif fault == "missing-support-component":
        del components["U2"]
    elif fault == "dnp-support-component":
        dnp = ("U2",)
    elif fault == "incomplete-support-inventory":
        inventories["U3"] = ("1", "2")
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": inventories,
            "dnp_components": dnp,
        }
    )


def lint(source: NetlistContract, *, mode: str | None = None, mapped: bool = True):
    return evaluate(
        "synthetic-regulator-support",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator-support",
            observed=source,
            netlist_sha256="c" * 64,
        ),
        DesignLintPolicy(
            regulator_support_pin_role_map=support_map() if mapped else None,
            rules=()
            if mode is None
            else (
                DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Synthetic policy case"),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_optocoupler_and_reference_pin_roles_are_a_valid_control() -> None:
    report = lint(support_netlist())
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("fault", "expected"),
    (
        ("wrong-optocoupler-function", "U2.1 native function is 'OUT'; expected 'IN'"),
        ("wrong-reference-type", "U3.3 native electrical type is 'output'; expected 'input'"),
        ("missing-native-role", "U3.2 native pin function is unavailable"),
        ("wrong-support-identity", "U2 value is 'SYNTH-OTHER'; expected 'SYNTH-ISO'"),
        ("wrong-support-symbol", "U2 symbol is Synthetic:OtherDevice"),
        ("wrong-support-footprint", "U2 footprint is Synthetic:QFN-4"),
        ("missing-support-component", "U2 is absent or ambiguous"),
        ("dnp-support-component", "U2 is marked DNP"),
        ("incomplete-support-inventory", "U3 native pin inventory differs"),
    ),
)
def test_mapped_active_support_mismatches_are_reviewed(fault: str, expected: str) -> None:
    finding = next(
        item for item in lint(support_netlist(fault=fault)).findings if item.rule_id == RULE_ID
    )
    assert finding.mode == "review"
    assert expected in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_support_components_are_not_inferred() -> None:
    report = lint(support_netlist(fault="wrong-optocoupler-function"), mapped=False)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_block_or_disable_mapped_support_role_findings() -> None:
    source = support_netlist(fault="wrong-optocoupler-function")
    blocked = next(item for item in lint(source, mode="block").findings if item.rule_id == RULE_ID)
    disabled = next(item for item in lint(source, mode="off").findings if item.rule_id == RULE_ID)
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_support_candidate_order_is_stable_for_native_metadata_mapping_order() -> None:
    source = support_netlist(fault="wrong-optocoupler-function")
    reordered = source.model_copy(
        update={
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    assert lint(source).findings == lint(reordered).findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_changed_support_pin_function_changes_source_bound_fingerprint() -> None:
    original = support_netlist(fault="wrong-optocoupler-function")
    changed = original.model_copy(
        update={"pin_functions": {**original.pin_functions, "U2.1": "IN_ALT"}}
    )
    first = next(item for item in lint(original).findings if item.rule_id == RULE_ID)
    second = next(item for item in lint(changed).findings if item.rule_id == RULE_ID)
    assert first.fingerprint != second.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_support_role_map_rejects_incomplete_pin_role_expectations() -> None:
    invalid = support_map().model_dump(mode="python")
    invalid["requirements"][0]["components"][0]["pins"][0]["expected_function"] = None
    invalid["requirements"][0]["components"][0]["pins"][0]["expected_electrical_type"] = None
    invalid["requirements"][0]["components"][0]["pins"][1]["expected_function"] = None
    invalid["requirements"][0]["components"][0]["pins"][1]["expected_electrical_type"] = None
    with pytest.raises(ValidationError, match="at least one expected pin role"):
        RegulatorSupportPinRoleMap.model_validate(invalid)
