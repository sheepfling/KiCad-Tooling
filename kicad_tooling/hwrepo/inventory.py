"""Read-only inventory of selectable projects, cohorts and approved toolchains."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_registry
from .layout import layout
from .models import (
    InventoryGroup,
    InventoryProject,
    InventoryToolchain,
    PolicyIssue,
    ProductIndex,
    ProductRecord,
    ProjectManifest,
    ProjectTestContract,
    TemplateInventoryReport,
    ToolchainsCatalog,
)


def inventory(root: Path) -> TemplateInventoryReport:
    """List declared selections without running checks or creating evidence."""
    root = root.resolve()
    try:
        registry = load_registry(root)
        toolchains = read_model(repo_path(root, registry.catalogs.toolchains), ToolchainsCatalog)
        products = read_model(repo_path(root, layout(root).products), ProductIndex)
        toolchain_ids = {record.id for record in toolchains.toolchains}
        folded_toolchain_ids = [record.id.casefold() for record in toolchains.toolchains]
        if len(folded_toolchain_ids) != len(set(folded_toolchain_ids)):
            raise ValueError(f"{registry.catalogs.toolchains}: duplicate toolchain IDs")
        known_projects = {record.id for record in registry.projects}
        project_products: dict[str, list[str]] = defaultdict(list)
        product_rows: list[InventoryGroup] = []
        for entry in products.products:
            product = read_model(repo_path(root, entry.path), ProductRecord)
            if product.id != entry.id:
                raise ValueError(
                    f"{entry.path}: product ID {product.id} differs from index ID {entry.id}"
                )
            if len({name.casefold() for name in entry.project_ids}) != len(entry.project_ids):
                raise ValueError(f"{layout(root).products}: duplicate project IDs in product index")
            unknown = sorted(set(entry.project_ids) - known_projects)
            if unknown:
                raise ValueError(f"{layout(root).products}: unknown project IDs: {unknown}")
            product_rows.append(InventoryGroup(id=entry.id, project_ids=entry.project_ids))
            for project_id in entry.project_ids:
                project_products[project_id].append(entry.id)

        tag_members: dict[str, list[str]] = defaultdict(list)
        project_rows: list[InventoryProject] = []
        for record in registry.projects:
            manifest = read_model(repo_path(root, record.config), ProjectManifest)
            if manifest.toolchain_id not in toolchain_ids:
                raise ValueError(f"{record.config}: unknown toolchain ID {manifest.toolchain_id}")
            directory = Path(record.config).parent.as_posix()
            local_files = (manifest.project, manifest.checks, *manifest.required_inputs)
            files = [f"{directory}/{name}" for name in local_files]
            files.extend(manifest.shared_inputs)
            files.extend(
                f"{directory}/{name}"
                for name in (manifest.mechanical_handoff, manifest.governance_record)
                if name is not None
            )
            directories = [f"{directory}/{name}" for name in manifest.source_roots]
            directories.extend(manifest.shared_source_roots)
            missing = tuple(
                sorted(
                    {name for name in files if not repo_path(root, name).is_file()}
                    | {name for name in directories if not repo_path(root, name).is_dir()}
                )
            )
            checks_path = repo_path(root, f"{directory}/{manifest.checks}")
            if checks_path.is_file():
                contract = read_model(checks_path, ProjectTestContract)
                if contract.validation.kind is not manifest.kind:
                    raise ValueError(f"{checks_path}: validation kind differs from project kind")
            for tag in manifest.tags:
                tag_members[tag].append(record.id)
            project_rows.append(
                InventoryProject(
                    id=record.id,
                    kind=record.kind,
                    status=record.status,
                    assurance_profile=record.assurance_profile,
                    manifest=record.config,
                    project=record.project,
                    toolchain_id=manifest.toolchain_id,
                    tags=tuple(sorted(set(manifest.tags))),
                    products=tuple(sorted(project_products[record.id])),
                    readiness="NEEDS_INPUTS" if missing else "INPUTS_PRESENT",
                    missing_inputs=missing,
                    next_command=(
                        f"Complete declared inputs for {record.id}, then run "
                        f"python -B -m kicad_tooling.verify --project {record.id} --format text"
                        if missing
                        else f"python -B -m kicad_tooling.verify --project {record.id} --format text"
                    ),
                )
            )
        return TemplateInventoryReport(
            status="PASS",
            projects=tuple(project_rows),
            products=tuple(sorted(product_rows, key=lambda item: item.id)),
            tags=tuple(
                InventoryGroup(id=tag, project_ids=tuple(sorted(members)))
                for tag, members in sorted(tag_members.items())
            ),
            toolchains=tuple(
                InventoryToolchain(id=record.id, kicad_version=record.kicad_version)
                for record in sorted(toolchains.toolchains, key=lambda item: item.id)
            ),
            next_actions=(
                "No live projects are registered. Create one with kicad_tooling.template new-project."
                if not project_rows
                else "Input presence is not validation. Run the selected verify command and review its receipt.",
            ),
        )
    except (OSError, ValueError) as exc:
        return TemplateInventoryReport(
            status="FAIL",
            issues=(PolicyIssue(code="INVENTORY_INPUT", location="repository", message=str(exc)),),
            next_actions=(
                "Repair the named catalog or project manifest, then rerun kicad_tooling.template list.",
            ),
        )


def format_inventory(report: TemplateInventoryReport) -> str:
    """Keep the selection vocabulary and next commands obvious at a terminal."""
    lines = [f"Repository inventory: {report.status}"]
    if report.status == "FAIL":
        lines.extend(f"  {issue.code}: {issue.message}" for issue in report.issues)
    else:
        lines.append(f"Projects ({len(report.projects)}):")
        for project in report.projects:
            lines.append(
                f"  {project.id}: {project.kind.value}, {project.status}, "
                f"{project.assurance_profile}, "
                f"{project.readiness}; toolchain={project.toolchain_id}"
            )
            if project.tags:
                lines.append(f"    Tags: {', '.join(project.tags)}")
            if project.products:
                lines.append(f"    Products: {', '.join(project.products)}")
            if project.missing_inputs:
                lines.append(f"    Missing: {', '.join(project.missing_inputs)}")
            lines.append(f"    Next: {project.next_command}")
        lines.append(f"Products ({len(report.products)}):")
        lines.extend(f"  {group.id}: {', '.join(group.project_ids)}" for group in report.products)
        lines.append(f"Tags ({len(report.tags)}):")
        lines.extend(f"  {group.id}: {', '.join(group.project_ids)}" for group in report.tags)
        lines.append(f"Toolchains ({len(report.toolchains)}):")
        lines.extend(f"  {item.id}: KiCad {item.kicad_version}" for item in report.toolchains)
    lines.extend(f"Next: {action}" for action in report.next_actions)
    return "\n".join(lines)
