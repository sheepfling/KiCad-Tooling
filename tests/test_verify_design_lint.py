"""Verify connector design-lint findings gate native verify and CI flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from kicad_tooling.verify import format_report
from tests.design_lint_fixtures.connector_return_cases import pwm_return_case_contracts
from tests.verify_design_lint_support import (
    check_ci_with_synthetic_connector_evidence,
    create_reference_project,
    verify_with_empty_contract_native_failure,
    verify_with_synthetic_connector_evidence,
)

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
]


@pytest.fixture
def synthetic_project(tmp_path: Path) -> Path:
    root = create_reference_project(tmp_path / "repository")
    contract_path = root / "examples/projects/controller/tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    write_model(
        contract_path, contract.model_copy(update={"design_lint": _connector_lint_policy()})
    )
    return root


def _connector_lint_policy(*, ignores: tuple[DesignLintIgnore, ...] = ()) -> DesignLintPolicy:
    return DesignLintPolicy(
        ignores=ignores,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic connector-verification tests isolate connector review from native PCB inventory",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                mode="off",
                reason="Synthetic connector-verification tests have no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_value_mismatch",
                mode="off",
                reason="Synthetic connector-verification tests have no native PCB value snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_pad_net_mismatch",
                mode="off",
                reason="Synthetic connector-verification tests have no native PCB snapshot",
            ),
        ),
    )


def test_unreviewed_connector_findings_fail_verify_and_ci(synthetic_project: Path) -> None:
    result = verify_with_synthetic_connector_evidence(synthetic_project)

    assert result.status == "FAIL", result.error
    assert result.design_lint is not None
    assert result.design_lint.status == "REVIEW"
    assert result.design_lint.connector_coverage is not None
    assert result.design_lint.connector_coverage.status == "UNDECLARED"
    assert len(result.design_lint.findings) == 3
    assert (Path(result.run_directory) / "design-lint.json").is_file()

    ci_open = check_ci_with_synthetic_connector_evidence(synthetic_project, "native-lint-open")
    assert ci_open.status == "FAIL"
    ci_summary = read_model(
        synthetic_project / "build/native-lint-open/controller/summary.json", ValidationSummary
    )
    assert ci_summary.checks["design_lint"].status == "FAIL"
    assert ci_summary.status == "FAIL"
    assert (synthetic_project / "build/native-lint-open/controller/design-lint.json").is_file()


def test_empty_connectivity_expectations_still_raise_native_connector_review(
    synthetic_project: Path,
) -> None:
    # A blank pin/net contract is a coverage gap; heuristic review must remain independent.
    contract_path = synthetic_project / "examples/projects/controller/tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    incomplete_validation = contract.validation.model_copy(update={"components": {}, "nets": {}})
    write_model(
        contract_path,
        contract.model_copy(update={"validation": incomplete_validation, "design_lint": None}),
    )

    result = verify_with_synthetic_connector_evidence(synthetic_project)

    assert result.status == "FAIL", result.error
    assert result.portable is not None
    assert result.portable.status == "PASS"
    assert result.native is not None
    assert result.native.status == "PASS"
    assert result.design_lint is not None
    assert result.design_lint.status != "PASS"
    assert result.design_lint.connector_coverage is not None
    assert result.design_lint.connector_coverage.status == "UNDECLARED"
    ground_candidate = next(
        item
        for item in result.design_lint.findings
        if item.rule_id == "connector.repeated_pin_function"
        and item.subject == "Synthetic:Port: ground/return"
    )
    assert ground_candidate.evidence == {"J1.7": ("GND1",), "J2.7": ("GND2",)}
    assert ground_candidate.mode == "review"
    assert ground_candidate.disposition == "OPEN"
    assert "REVIEW connector.repeated_pin_function: Synthetic:Port: ground/return" in format_report(
        result
    )
    unchanged = read_model(contract_path, ProjectTestContract)
    assert unchanged.validation.components == {}
    assert unchanged.validation.nets == {}
    assert unchanged.design_lint is None
    assert (Path(result.run_directory) / "design-lint.json").is_file()


def test_empty_native_contract_blocker_still_surfaces_split_return_review(
    synthetic_project: Path,
) -> None:
    contract_path = synthetic_project / "examples/projects/controller/tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    incomplete_validation = contract.validation.model_copy(update={"components": {}, "nets": {}})
    write_model(
        contract_path,
        contract.model_copy(update={"validation": incomplete_validation}),
    )

    result = verify_with_empty_contract_native_failure(synthetic_project)

    assert result.status == "FAIL"
    assert result.native is not None
    assert result.native.status == "FAIL"
    native_validation = read_model(
        Path(result.run_directory) / "native/controller/summary.json", ValidationSummary
    )
    assert native_validation.status == "FAIL"
    assert native_validation.checks["netlist"].status == "FAIL"
    assert native_validation.checks["netlist"].returncode == 0
    assert native_validation.checks["netlist"].error == "Independent connectivity contract is empty"
    assert result.design_lint is not None
    assert result.design_lint.status == "REVIEW"
    finding = next(
        item
        for item in result.design_lint.findings
        if item.rule_id == "connector.repeated_pin_function"
        and item.subject == "Synthetic:Port: ground/return"
    )
    assert finding.evidence == {"J1.7": ("GND1",), "J2.7": ("GND2",)}
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
    assert "REVIEW connector.repeated_pin_function: Synthetic:Port: ground/return" in format_report(
        result
    )
    assert (Path(result.run_directory) / "design-lint.json").is_file()


@pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function")
@pytest.mark.design_lint_rule(rule_id="net.numbered_returns")
@pytest.mark.return_path_lint
@pytest.mark.parametrize(
    ("case", "expected_rule_ids"),
    (
        pytest.param(
            "four-db9-pwm-fault",
            frozenset({"connector.repeated_pin_function", "net.numbered_returns"}),
            id="split-return-fault",
        ),
        pytest.param("four-db9-pwm-control", frozenset(), id="common-return-control"),
    ),
)
def test_empty_contract_keeps_numbered_db9_return_reviews_visible(
    synthetic_project: Path,
    case: str,
    expected_rule_ids: frozenset[str],
) -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures/design_lint/four-port-db9-returns"
        / f"{'pwm-fault' if case.endswith('fault') else 'pwm-control'}.kicad_sch"
    )
    config = load_config(synthetic_project, "examples/projects/controller/project.json")
    (synthetic_project / config.project).with_suffix(".kicad_sch").write_bytes(fixture.read_bytes())

    result = verify_with_empty_contract_native_failure(
        synthetic_project,
        observed_netlist=pwm_return_case_contracts()[case],
    )

    assert result.status == "FAIL"
    assert result.native is not None
    assert result.native.status == "FAIL"
    validation = read_model(
        Path(result.run_directory) / "native/controller/summary.json", ValidationSummary
    )
    assert validation.checks["netlist"].error == "Independent connectivity contract is empty"
    assert result.design_lint is not None
    assert result.design_lint.status == "REVIEW"
    findings = {item.rule_id: item for item in result.design_lint.findings}
    assert expected_rule_ids <= findings.keys()
    assert not (
        {"connector.repeated_pin_function", "net.numbered_returns"} - expected_rule_ids
    ).intersection(findings)

    if case == "four-db9-pwm-fault":
        numbered_return = findings["net.numbered_returns"]
        assert numbered_return.evidence == {
            f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
            for reference in range(1, 5)
        }
        report = format_report(result, detail="full")
        assert "REVIEW connector.repeated_pin_function:" in report
        assert "REVIEW net.numbered_returns:" in report
    assert (Path(result.run_directory) / "design-lint.json").is_file()


def test_exact_ignores_do_not_clear_unreviewed_connector_coverage(
    synthetic_project: Path,
) -> None:
    initial = verify_with_synthetic_connector_evidence(synthetic_project)
    assert initial.design_lint is not None
    contract_path = synthetic_project / "examples/projects/controller/tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    write_model(
        contract_path,
        contract.model_copy(
            update={
                "design_lint": _connector_lint_policy(
                    ignores=tuple(
                        DesignLintIgnore(
                            rule_id=item.rule_id,
                            fingerprint=item.fingerprint,
                            reason="Synthetic reviewed pinout accepts this exact observation",
                        )
                        for item in initial.design_lint.findings
                    )
                )
            }
        ),
    )

    reviewed = verify_with_synthetic_connector_evidence(synthetic_project)

    assert reviewed.status == "FAIL", reviewed.error
    assert reviewed.design_lint is not None
    assert reviewed.design_lint.status == "REVIEW"
    assert reviewed.design_lint.connector_coverage is not None
    assert reviewed.design_lint.connector_coverage.status == "UNDECLARED"


def test_reviewed_connector_inventory_clears_verify_and_ci_gate(synthetic_project: Path) -> None:
    initial = verify_with_synthetic_connector_evidence(synthetic_project)
    assert initial.design_lint is not None
    contract_path = synthetic_project / "examples/projects/controller/tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    write_model(
        contract_path,
        contract.model_copy(
            update={
                "design_lint": _connector_lint_policy(
                    ignores=tuple(
                        DesignLintIgnore(
                            rule_id=item.rule_id,
                            fingerprint=item.fingerprint,
                            reason="Synthetic reviewed pinout accepts this exact observation",
                        )
                        for item in initial.design_lint.findings
                    )
                )
            }
        ),
    )

    manifest_path = synthetic_project / "examples/projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic fixture does not define external connector requirements",
                    )
                    for reference in ("J1", "J2")
                ),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covered every connector in the schematic"
                ),
            }
        ),
    )

    accepted = verify_with_synthetic_connector_evidence(synthetic_project)

    assert accepted.status == "PASS", accepted.error
    assert accepted.design_lint is not None
    assert accepted.design_lint.status == "PASS"
    assert accepted.design_lint.connector_coverage is not None
    assert (
        accepted.design_lint.connector_coverage.inventory_review_basis
        == "Synthetic review covered every connector in the schematic"
    )

    ci_reviewed = check_ci_with_synthetic_connector_evidence(
        synthetic_project, "native-lint-reviewed"
    )
    assert ci_reviewed.status == "PASS"
