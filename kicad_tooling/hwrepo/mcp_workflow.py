"""Bounded MCP workflow adapters over diagnostic, native and release services."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from ..check_toolchain import cli_executable
from ..ci import static_pipeline
from ..verify import run_command
from . import (
    contract_coach,
    design_lint,
    diagnostics,
    generation,
    packaging,
    releasing,
    rescue,
)
from . import mcp_3d_workflow as _mcp_3d_workflow
from . import mcp_workflow_paths as _mcp_workflow_paths
from . import model_population as _model_population
from .contracts import read_model, repo_path, write_model
from .design_lint_reconciliation import reconcile_design_lint_reports
from .design_lint_reconciliation_models import DesignLintReconciliationReport
from .design_lint_report_models import DesignLintReport
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_rule_types import DesignLintTheme
from .discovery import load_config
from .doctor import NativeRunner, doctor
from .evidence import source_state
from .exports import export as generate_exports
from .exports import require_declared_variant, verify_exports
from .mcp_workflow_journal import journal
from .models import (
    ContractCoachReport,
    DiagnosticReport,
    LocalRescueReport,
    McpGenerationReport,
    McpScopeReport,
    ProjectManifest,
    ReleaseClass,
    ReleaseExportReport,
    ReleaseManifest,
    ReleasePackageReport,
    ReleaseReadinessReport,
    ReleaseStatus,
)
from .portable_evidence import verify_release_portable
from .release import check as release_check
from .selection import ProjectSelector, resolve_project_ids
from .sharding import shard_projects

# Preserve the former import surface while implementation lives in owner modules.
model_population = _model_population
apply_model_population = _mcp_3d_workflow.apply_model_population
export_3d = _mcp_3d_workflow.export_3d
inspect_3d_models = _mcp_3d_workflow.inspect_3d_models
pcb_config = _mcp_3d_workflow.pcb_config
preview_model_population = _mcp_3d_workflow.preview_model_population
artifact_file = _mcp_workflow_paths.artifact_file
fresh_output = _mcp_workflow_paths.fresh_output
identifier = _mcp_workflow_paths.identifier
native_summary_path = _mcp_workflow_paths.native_summary_path
selected_project = _mcp_workflow_paths.selected_project


def diagnose_import(
    root: Path,
    source: Path,
    project_id: str,
    toolchain_id: str,
) -> DiagnosticReport:
    """Diagnose an already-authorized import source and retain the preview receipt."""
    with journal(root, project_id) as receipt:
        result = diagnostics.diagnose_import(root, source, project_id, toolchain_id, receipt)
        result = result.model_copy(update={"run_directory": str(receipt.directory)})
        receipt.finish(result, diagnostics.format_text(result, "full"), result.status)
        return result


def diagnose_project(
    root: Path,
    project_id: str,
    native_report: str | None = None,
    bom: str | None = None,
) -> DiagnosticReport:
    """Run selected diagnosis; optional native/BOM inputs must be ignored artifacts."""
    if bom is not None and native_report is None:
        raise ValueError("BOM diagnosis requires the selected project's native_report")
    native = None if native_report is None else native_summary_path(root, native_report)
    bom_path = None if bom is None else artifact_file(root, bom)
    with journal(root, project_id) as receipt:
        result = diagnostics.diagnose_project(root, project_id, native, bom_path, receipt)
        result = result.model_copy(update={"run_directory": str(receipt.directory)})
        receipt.finish(result, diagnostics.format_text(result, "full"), result.status)
        return result


def rescue_project(root: Path, project_id: str) -> LocalRescueReport:
    """Retain a local repair view without converting UNVERIFIED_GLOBAL into a pass."""
    with journal(root, project_id) as receipt:
        result = rescue.rescue_project(root, project_id, receipt)
        receipt.finish(result, rescue.format_rescue(result, "full"), result.status)
        return result


def check_scope(
    root: Path,
    project_ids: tuple[str, ...] = (),
    product_ids: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    exclude_tags: tuple[str, ...] = (),
    shard: str | None = None,
    jobs: int = 1,
) -> McpScopeReport:
    """Reuse union/exclusion selection; no selectors deliberately invokes the full gate."""
    job_count: int | bool = jobs
    if type(job_count) is not int or not 1 <= job_count <= 32:
        raise ValueError("jobs must be between 1 and 32")
    selector = ProjectSelector(
        project_ids=project_ids,
        product_ids=product_ids,
        tags=tags,
        excluded_tags=exclude_tags,
    )
    selected = list(resolve_project_ids(root, selector)) if selector.active else None
    if shard is not None:
        selected = list(
            shard_projects(
                tuple(selected)
                if selected is not None
                else resolve_project_ids(root, ProjectSelector()),
                shard,
            )
        )
    with journal(root, "scope") as receipt:
        with receipt.stage("portable"):
            result = static_pipeline(root, selected, workers=jobs)
        report = McpScopeReport(
            status=result.status,
            run_directory=str(receipt.directory),
            report=result,
        )
        receipt.finish_named("scope", report, f"Scope check: {report.status}", report.status)
        return report


def inspect_contract(root: Path, project_id: str, native_summary: str) -> ContractCoachReport:
    """Read source-bound observations without writing independent test expectations."""
    return contract_coach.inspect_summary(
        root, project_id, native_summary_path(root, native_summary)
    )


def inspect_design_lint(root: Path, project_id: str, native_summary: str) -> DesignLintReport:
    """Review source-bound heuristic findings through the same typed CLI service."""
    return design_lint.inspect_summary(root, project_id, native_summary_path(root, native_summary))


def list_design_lint_rules(
    theme: DesignLintTheme | None = None,
    status: Literal["active", "prototype", "retired"] | None = None,
    maturity: Literal["synthetic_validated", "cohort_candidate", "field_validated"] | None = None,
    default_mode: Literal["review", "block", "off"] | None = None,
    rule_id: str | None = None,
    rule_id_prefix: str | None = None,
) -> DesignLintRuleCatalog:
    """Return the packaged rule catalog without reading project evidence."""
    return design_lint.rule_catalog(
        theme=theme,
        status=status,
        maturity=maturity,
        default_mode=default_mode,
        rule_id=rule_id,
        rule_id_prefix=rule_id_prefix,
    )


def reconcile_design_lint(
    root: Path,
    project_id: str,
    native_summary: str,
    baseline_report_json: str,
) -> DesignLintReconciliationReport:
    """Compare a saved report with current source-bound lint, preserving both findings."""
    if len(baseline_report_json.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("Baseline design-lint report exceeds the 10 MiB input limit")
    baseline = DesignLintReport.model_validate_json(baseline_report_json)
    current = design_lint.inspect_summary(
        root, project_id, native_summary_path(root, native_summary)
    )
    return reconcile_design_lint_reports(baseline, current)


def capture_contract(
    root: Path,
    project_id: str,
    runner: NativeRunner = "auto",
) -> ContractCoachReport:
    """Capture an UNREVIEWED netlist with fixed local or digest-pinned native runners."""
    selected_project(root, project_id)
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    native_runner = (
        contract_coach.LocalNetlistRunner("kicad-cli")
        if runner == "local"
        else contract_coach.ContainerNetlistRunner()
        if runner == "container"
        else contract_coach.AutoNetlistRunner("kicad-cli")
    )
    output = contract_coach.receipt_directory(root, project_id, None)
    result = contract_coach.capture(root, project_id, output, native_runner)
    contract_coach.save_receipt(output, result)
    return result


def selected_cli(root: Path, project_id: str, runner: NativeRunner) -> str | None:
    """Use doctor selection and resolve the fixed local command; callers cannot supply one."""
    result = doctor(root, native=True, project_id=project_id, runner=runner)
    if result.status != "PASS":
        raise ValueError("Native prerequisites failed: " + "; ".join(result.next_actions))
    native = next((check.observed for check in result.checks if check.id == "native-runner"), None)
    if native == "container":
        return None
    if native != "local":
        raise ValueError("Doctor did not select an exact native runner")
    executable = cli_executable("kicad-cli")
    if executable is None:
        raise ValueError("The selected local KiCad executable is no longer available")
    return executable


def clean_source(root: Path) -> None:
    source = source_state(root)
    if not source.clean or source.commit is None:
        raise ValueError("Commit the reviewed source first; exports require a clean checkout")


def captured_command(root: Path, argv: tuple[str, ...], log: Path, timeout: int) -> None:
    """Keep subprocess output out of the MCP protocol and preserve failure evidence."""
    repo_path(root, log.relative_to(root).as_posix())
    if log.exists():
        raise ValueError(f"Command receipt already exists: {log.relative_to(root)}")
    log.parent.mkdir(parents=True, exist_ok=True)
    command = run_command(root, argv, timeout=timeout)
    write_model(log, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Workflow command failed; inspect {log.relative_to(root)}")


def export_project(
    root: Path,
    project_id: str,
    export_id: str,
    runner: NativeRunner = "auto",
    assembly_variant: str | None = None,
) -> ReleaseExportReport:
    """Export explicit PCB settings into a fresh ignored directory for review."""
    root = root.resolve()
    project = selected_project(root, project_id)
    manifest = read_model(repo_path(root, project.config), ProjectManifest)
    if manifest.release_exports is None or manifest.kind.value != "pcb":
        raise ValueError("PCB release exports require project.json release_exports settings")
    if assembly_variant is not None and not assembly_variant.strip():
        raise ValueError("KiCad assembly variant cannot be blank")
    selected_variant = assembly_variant or manifest.release_exports.assembly_variant
    config = load_config(root, project.config)
    require_declared_variant(repo_path(root, config.project), selected_variant)
    directory = fresh_output(root, "exports", export_id)
    output = repo_path(root, (directory / "files").relative_to(root).as_posix())
    clean_source(root)
    cli = selected_cli(root, project_id, runner)
    dependency_path = (
        fresh_output(root, "release-deps", "mcp-export-" + export_id) if cli is None else None
    )
    directory.mkdir(parents=True, exist_ok=False)
    dependencies: Path | None = None
    if dependency_path is not None:
        dependencies = dependency_path.relative_to(root)
        config = load_config(root, project.config)
        captured_command(
            root,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.native_deps",
                "--root",
                str(root),
                "--image",
                config.image,
                "--output",
                dependencies.as_posix(),
            ),
            directory / "dependencies.command.json",
            600,
        )
    source = source_state(root)
    if cli is not None:
        report = generate_exports(root, project.config, output, cli, assembly_variant)
    else:
        try:
            releasing.run_native(
                root,
                project,
                output,
                cli,
                dependencies,
                export_only=True,
                assembly_variant=assembly_variant,
            )
        except ValueError:
            # The CLI exits 1 for a typed domain FAIL. Preserve that report when
            # present; startup/container failures without a report remain errors.
            path = repo_path(root, (output / "exports.json").relative_to(root).as_posix())
            if not path.is_file():
                raise
            report = read_model(path, ReleaseExportReport)
            if report.status != "FAIL":
                raise
        else:
            report = read_model(output / "exports.json", ReleaseExportReport)
    if (
        report.project_id != project_id
        or report.source != source
        or report.toolchain_id != load_config(root, project.config).toolchain_id
        or report.settings != manifest.release_exports
        or report.assembly_variant != selected_variant
    ):
        raise ValueError("Export report differs from the requested project/source/settings")
    if report.status == "FAIL":
        return report
    return verify_exports(
        root,
        releasing.reference(root, output / "exports.json"),
        source_state(root),
        project_id,
        project.config,
        assembly_variant,
    )


def prepare_review_scope(
    root: Path,
    release_id: str,
    project_ids: tuple[str, ...] = (),
    variants: tuple[str, ...] = (),
    portable: str | None = None,
    runner: NativeRunner = "auto",
) -> ReleaseManifest:
    """Prepare an engineering-review scope using the same selections as the release CLI."""
    root = root.resolve()
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    output = fresh_output(root, "releases", release_id)
    fresh_output(root, "release-deps", release_id)
    clean_source(root)
    source = source_state(root)
    if source.commit is None:
        raise ValueError("Commit the reviewed source before preparing a review")
    selections = releasing.resolve_variants(root, variants)
    request = ReleaseManifest(
        release_id=release_id,
        release_class=ReleaseClass.ENGINEERING_REVIEW,
        status=ReleaseStatus.CANDIDATE,
        source_commit=source.commit,
        toolchain_id="pending",
        projects=project_ids,
        variants=selections,
        libraries=(),
        interfaces=(),
        artifacts=(),
    )
    projects = releasing.selected_projects(root, request)
    portable_path = None if portable is None else artifact_file(root, portable)
    if portable_path is not None:
        verify_release_portable(
            root,
            releasing.reference(root, portable_path),
            source,
            tuple(project.id for project in projects),
        )
    cli = selected_cli(root, projects[0].id, runner)
    if cli is not None:
        return releasing.prepare(
            root,
            release_id,
            project_ids,
            selections,
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            cli=cli,
            portable=None if portable_path is None else portable_path.relative_to(root),
        )
    # Existing dependency preparation inherits stdout; capture the CLI so progress
    # cannot enter the stdio protocol. Every option comes from a validated selection.
    selection_args = tuple(
        value for project_id in project_ids for value in ("--project", project_id)
    )
    variant_args = tuple(value for variant in variants for value in ("--variant", variant))
    portable_args = (
        ()
        if portable_path is None
        else (
            "--portable",
            portable_path.relative_to(root).as_posix(),
        )
    )
    captured_command(
        root,
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.release",
            "prepare",
            "--root",
            str(root),
            *selection_args,
            *variant_args,
            *portable_args,
            "--release-id",
            release_id,
            "--release-class",
            "engineering_review",
            "--format",
            "json",
        ),
        output.parent / f"{output.name}.command.json",
        1800,
    )
    candidate = read_model(
        repo_path(root, (output / "manifest.json").relative_to(root).as_posix()),
        ReleaseManifest,
    )
    if (
        candidate.release_id != release_id
        or candidate.projects != project_ids
        or candidate.variants != selections
        or candidate.release_class is not ReleaseClass.ENGINEERING_REVIEW
        or candidate.status is not ReleaseStatus.CANDIDATE
        or candidate.approval is not None
        or candidate.source_commit != source.commit
        or source_state(root) != source
    ):
        raise ValueError("Prepared candidate differs from the requested review or current source")
    return candidate


def prepare_review(
    root: Path,
    project_id: str,
    release_id: str,
    runner: NativeRunner = "auto",
) -> ReleaseManifest:
    """Prepare one engineering-review candidate without approval or production authority."""
    return prepare_review_scope(root, release_id, (project_id,), runner=runner)


def check_release(root: Path, manifest: str) -> ReleaseReadinessReport:
    return release_check(root, read_model(artifact_file(root, manifest), ReleaseManifest))


def package_release(root: Path, manifest: str, package_id: str) -> ReleasePackageReport:
    path = artifact_file(root, manifest)
    output = fresh_output(root, "packages", package_id, ".zip")
    return packaging.package(root, path.relative_to(root).as_posix(), output)


def verify_package(root: Path, archive: str) -> ReleasePackageReport:
    return packaging.verify(artifact_file(root, archive))


def restore_package(root: Path, archive: str, restore_id: str) -> ReleasePackageReport:
    path = artifact_file(root, archive)
    output = fresh_output(root, "restores", restore_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    return packaging.restore(path, output)


def generate_views(
    root: Path,
    view_id: str,
    project_ids: tuple[str, ...] = (),
    product_ids: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    exclude_tags: tuple[str, ...] = (),
) -> McpGenerationReport:
    """Render validated product/BOM projections into a fresh ignored review directory."""
    selector = ProjectSelector(
        project_ids=project_ids,
        product_ids=product_ids,
        tags=tags,
        excluded_tags=exclude_tags,
    )
    selected = resolve_project_ids(root, selector) if selector.active else None
    output = fresh_output(root, "views", view_id)
    output.mkdir(parents=True, exist_ok=False)
    names = generation.generate(root, output=output, selected_project_ids=selected)
    return McpGenerationReport(
        status="PASS",
        directory=output.relative_to(root).as_posix(),
        files=tuple((output / name).relative_to(root).as_posix() for name in names),
    )
