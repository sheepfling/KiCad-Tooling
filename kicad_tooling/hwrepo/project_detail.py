"""Read one registered project's authored inventory and check contract."""

from __future__ import annotations

from pathlib import Path

from .contracts import read_model, repo_path
from .inventory import inventory
from .project_inventory_models import McpProjectReport, ProjectDetailRequest
from .project_models import ProjectManifest, ProjectTestContract


def read_project_detail(root: Path, request: ProjectDetailRequest) -> McpProjectReport:
    """Return one project's authored records after repository inventory succeeds."""
    report = inventory(root)
    if report.status != "PASS":
        raise ValueError(
            "Project discovery failed: " + "; ".join(issue.message for issue in report.issues)
        )
    project = next((item for item in report.projects if item.id == request.project_id), None)
    if project is None:
        raise ValueError(f"Unknown project ID: {request.project_id}. Call list_projects first.")
    path = repo_path(root, project.manifest)
    manifest = read_model(path, ProjectManifest)
    contract_path = repo_path(path.parent, manifest.checks)
    contract = read_model(contract_path, ProjectTestContract) if contract_path.is_file() else None
    return McpProjectReport(project=project, manifest=manifest, contract=contract)
