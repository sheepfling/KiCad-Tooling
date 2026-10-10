"""Verify connector design-lint findings gate native verify and CI flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.verify_design_lint_support import (
    check_ci_with_synthetic_connector_evidence,
    create_reference_project,
    verify_with_synthetic_connector_evidence,
)

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
]


@pytest.fixture
def synthetic_project(tmp_path: Path) -> Path:
    return create_reference_project(tmp_path / "repository")


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
                "design_lint": DesignLintPolicy(
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
                "design_lint": DesignLintPolicy(
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
