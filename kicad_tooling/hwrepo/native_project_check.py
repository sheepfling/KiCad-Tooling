"""Native checks for selected KiCad projects with retained typed evidence."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts import write_model
from .discovery import load_config, load_registry
from .evidence import digest
from .governance_lint import lint
from .models import CheckAllSummary, CheckEvidence, ProjectCheckSummary
from .native_project_check_models import NativeProjectCheckRequest
from .native_project_validation import validate_project
from .native_project_validation_models import NativeProjectValidationRequest
from .product import check as check_product
from .project_models import ProjectKind, ProjectRecord
from .repository import check_repository


def selected_projects(root: Path, requested: Sequence[str] | None) -> tuple[ProjectRecord, ...]:
    registry = load_registry(root)
    available = {project.id: project for project in registry.projects}
    identifiers = tuple(available) if requested is None else tuple(requested)
    unknown = [identifier for identifier in identifiers if identifier not in available]
    if unknown:
        raise ValueError(f"Unknown project ids: {unknown}")
    return tuple(available[identifier] for identifier in identifiers)


def run_native_project_check(root: Path, request: NativeProjectCheckRequest) -> CheckAllSummary:
    """Run native checks for the authored selection and save its report artifacts."""
    root = root.resolve()
    output = request.output
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retained evidence: {output}")
    output.mkdir(parents=True)
    requested = request.project_ids
    governance = lint(root, requested)
    repository = check_repository(root, requested)
    product_policy = check_product(root, selected_project_ids=requested)
    rows: list[ProjectCheckSummary] = []
    if (
        governance.status == "PASS"
        and repository.status == "PASS"
        and product_policy.status == "PASS"
    ):
        for project in selected_projects(root, requested):
            report = validate_project(
                root,
                NativeProjectValidationRequest(
                    output=output / project.id,
                    cli=request.cli,
                    config_path=Path(project.config),
                ),
            )
            try:
                config = load_config(root, project.config)
            except (OSError, ValueError):
                config = None  # validate retained the malformed-input finding.
            if config is not None and config.kind in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
                from .design_lint import inspect_summary

                project_output = output / project.id
                lint_report = inspect_summary(root, project.id, project_output / "summary.json")
                lint_path = project_output / "design-lint.json"
                write_model(lint_path, lint_report)
                report = report.model_copy(
                    update={
                        "checks": {
                            **report.checks,
                            "design_lint": CheckEvidence(
                                status="PASS" if lint_report.status == "PASS" else "FAIL",
                                error=(
                                    None
                                    if lint_report.status == "PASS"
                                    else f"Design lint {lint_report.status}; inspect design-lint.json"
                                ),
                                findings=sum(
                                    item.disposition == "OPEN" for item in lint_report.findings
                                ),
                                files=("design-lint.json",),
                            ),
                        },
                        "status": "FAIL" if lint_report.status != "PASS" else report.status,
                        "artifacts_sha256": {
                            **report.artifacts_sha256,
                            "design-lint.json": digest(lint_path),
                        },
                    }
                )
                write_model(project_output / "summary.json", report)
            rows.append(
                ProjectCheckSummary(
                    id=project.id,
                    status=report.status,
                    summary=f"{project.id}/summary.json",
                )
            )
    result = CheckAllSummary(
        governance=governance,
        repository=repository,
        product_policy=product_policy,
        projects=tuple(rows),
        status=(
            "PASS"
            if governance.status == "PASS" and rows and all(row.status == "PASS" for row in rows)
            else "FAIL"
        ),
    )
    write_model(output / "summary.json", result)
    return result
