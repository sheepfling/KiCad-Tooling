"""Optional MCP adapter over the existing, typed repository workflow services."""
from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from subprocess import SubprocessError
from threading import Lock
from typing import Annotated, Literal
from zipfile import BadZipFile

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, StrictInt

from ..verify import Depth, verify
from . import mcp_checks as checks
from . import mcp_conversion as conversion
from . import mcp_electrical as electrical
from . import mcp_files as files
from . import mcp_new_workflows as new_workflows
from . import mcp_parts as parts
from . import mcp_parts_extensions as part_tools
from . import mcp_planning as planning
from . import mcp_workflow as workflow
from .contracts import read_model, repo_path
from .doctor import NativeRunner
from .doctor import doctor as inspect_environment
from .import_inventory import scan_imports as scan_designs
from .importing import import_project as import_design
from .inventory import inventory
from .layout import layout, workflow_guide
from .models import (
    AutoCadReport,
    CadImportReport,
    CadSourcingReview,
    CadStepReport,
    ContractCoachReport,
    DiagnosticReport,
    ElectricalAnalysisReport,
    ElectricalChartsReport,
    ElectricalChartsSuiteReport,
    ElectricalInputInventory,
    ElectricalSetupReport,
    ElectricalSuiteReport,
    ForeignFormat,
    ForeignPcbReport,
    ImpactPlan,
    ImportInventoryReport,
    LocalRescueReport,
    McpArtifactList,
    McpEditPreview,
    McpEditResult,
    McpFileContent,
    McpGenerationReport,
    McpModelMapAssignment,
    McpNativeScopeReport,
    McpProjectReport,
    McpPurchasingPreferencesResult,
    McpScopeReport,
    ModelInventoryReport,
    ModelMapAssignment,
    ModelPopulationReport,
    PartPickerReport,
    PartSelectionAssignment,
    PartSelectionReport,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
    ProjectScaffoldReport,
    ProjectTestContract,
    ProjectVerificationReport,
    PurchasingPreferences,
    PurchasingReport,
    ReleaseExportReport,
    ReleaseManifest,
    ReleasePackageReport,
    ReleaseReadinessReport,
    SourcingSnapshotReport,
    SupplierHandoffReport,
    TemplateDoctorReport,
    TemplateInventoryReport,
    ThreeDReport,
    ToolSurfaceReport,
)
from .scaffold import new_project as scaffold_project

DocumentName = Literal[
    "start-here", "first-board", "diagnostics", "import-workflow",
    "contributor-guide", "checks-and-ci", "mcp", "bom-policy", "release-readiness",
    "release-storage", "project-kinds", "libraries", "authority-model", "assurance-profiles",
    "three-d-workflow", "parts-to-order", "tool-surfaces", "electrical-analysis",
    "cad-sourcing",
]
DOCUMENTS: Mapping[DocumentName, str] = {
    "start-here": "docs/workflow/START_HERE.md",
    "first-board": "docs/workflow/FIRST_BOARD.md",
    "diagnostics": "docs/workflow/DIAGNOSTICS.md",
    "import-workflow": "docs/workflow/IMPORT_WORKFLOW.md",
    "contributor-guide": "docs/workflow/CONTRIBUTOR_GUIDE.md",
    "checks-and-ci": "docs/workflow/CHECKS_AND_CI.md",
    "mcp": "docs/workflow/MCP.md",
    "bom-policy": "docs/workflow/BOM_POLICY.md",
    "release-readiness": "docs/workflow/RELEASE_READINESS.md",
    "release-storage": "docs/workflow/RELEASE_STORAGE.md",
    "project-kinds": "docs/workflow/PROJECT_KINDS.md",
    "libraries": "docs/workflow/LIBRARIES.md",
    "authority-model": "docs/workflow/AUTHORITY_MODEL.md",
    "assurance-profiles": "docs/workflow/ASSURANCE_PROFILES.md",
    "three-d-workflow": "docs/workflow/THREE_D_WORKFLOW.md",
    "parts-to-order": "docs/workflow/PARTS_TO_ORDER.md",
    "tool-surfaces": "docs/workflow/TOOL_SURFACES.md",
    "electrical-analysis": "docs/workflow/ELECTRICAL_ANALYSIS.md",
    "cad-sourcing": "docs/workflow/CAD_SOURCING.md",
}
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False,
)
CREATE_ONLY = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False,
)
EDIT = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False,
)
EXECUTION = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True,
)


def import_path(
    root: Path, source: str, scopes: tuple[Path, ...], *, directory: bool = False,
) -> Path:
    """Authorize a source before the importer resolves its parent or reads siblings."""
    candidate = Path(source).expanduser()
    if ".." in candidate.parts:
        raise ValueError("Import source must not contain parent traversal")
    candidate = candidate if candidate.is_absolute() else root / candidate
    for scope in scopes:
        if candidate.is_relative_to(scope):
            relative = candidate.relative_to(scope).as_posix()
            path = scope.resolve() if relative == "." else repo_path(scope, relative)
            if directory:
                if not path.is_dir():
                    raise ValueError("Select an existing import source directory")
            elif path.suffix != ".kicad_pro" or not path.is_file():
                raise ValueError("Select an existing .kicad_pro file, not a directory")
            return path
    raise ValueError("Import source is outside the checkout and configured --import-root directories")


@contextmanager
def service_operation(operation: Lock) -> Generator[None, None, None]:
    """Preserve actionable service/input errors in the MCP tool response."""
    with operation:
        try:
            yield
        except (OSError, ValueError, BadZipFile, SubprocessError) as exc:
            raise ToolError(str(exc)) from exc


def create_server(
    root: Path, *, allow_checks: bool = False, allow_writes: bool = False,
    import_roots: tuple[Path, ...] = (), allow_edits: bool = False, allow_exports: bool = False,
    allow_downloads: bool = False, allow_supplier_submissions: bool = False,
) -> MCPServer[None]:
    """Bind one server to a trusted checkout; tool calls cannot change its authority."""
    declared_root = root.expanduser().absolute()
    root = declared_root.resolve(strict=True)
    if not root.is_dir() or not repo_path(root, layout(root).discovery).is_file():
        raise ValueError("MCP root must have the configured project discovery catalog")
    scopes = [declared_root, root]
    for path in import_roots:
        declared = path.expanduser().absolute()
        resolved = declared.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError(f"Import root must be an existing directory: {path}")
        scopes.extend((declared, resolved))
    permitted_sources = tuple(dict.fromkeys(scopes))
    # The SDK runs synchronous tools in worker threads. Serialize operations on this
    # checkout so discovery never observes a partially staged write from this server.
    operation = Lock()
    server: MCPServer[None] = MCPServer(
        "kicad-workflow", version="2", log_level="WARNING",
        instructions=(
            f"Use only this checkout: {root}. Start with list_projects and doctor. "
            "Use inspect_tool_surfaces to see CLI/MCP coverage and intentional gaps. "
            "Inventory input presence and import previews are not design validation. "
            "Read the status and next actions in every report. Passing checks are not "
            "electrical approval or manufacturing authorization. Follow scan/preview/import, "
            "doctor, diagnose_project, read artifacts/source, preview and apply an explicit "
            "reviewed edit, then recheck. Commit reviewed source with normal Git before "
            "export_project or prepare_review. Diagnose BOMs with the matching native report. "
            "Use prepare_parts for quantities and order-review files; it cannot place an order. "
            "Use list_artifacts/read_artifact to inspect receipts; they use repository-relative "
            "paths. Execution, creation, editing and export capabilities are enabled separately "
            "at startup. CAD downloads and supplier submissions require additional host opt-ins. "
            "Supplier submission sends a reviewed BOM externally but never places an order. "
            "Never invent electrical expectations, approvals, or waivers."
        ),
    )

    def list_projects() -> TemplateInventoryReport:
        """Discover project IDs, products, tags and toolchains; presence is not validation."""
        with service_operation(operation):
            return inventory(root)

    server.tool(annotations=READ_ONLY)(list_projects)

    def inspect_tool_surfaces() -> ToolSurfaceReport:
        """Compare CLI and full MCP coverage, declared gaps and interface drift.

        This covers all server capabilities, not only those enabled in this session.
        PASS requires interface coverage and core parity policy; behavior tests are
        NOT_RUN by this inspection. The full CI gate executes the referenced tests.
        """
        from .surface import inspect_tool_surfaces as inspect_surfaces

        with service_operation(operation):
            return inspect_surfaces(root)

    server.tool(annotations=READ_ONLY)(inspect_tool_surfaces)

    def plan_impact(
        base: str | None = None, head: str = "HEAD", paths: tuple[str, ...] | None = None,
        full: bool = False, select_project: str | None = None, select_tag: str | None = None,
        select_product: str | None = None, exclude_tag: str | None = None,
        shard: str | None = None,
    ) -> ImpactPlan:
        """Plan checks from one Git diff, path list, full request or manual selector.

        Git refs resolve to commits before diffing; head defaults to HEAD. exclude_tag
        applies only to manual project/tag/product selection. This does not run checks;
        ambiguous changed paths conservatively select the full scope.
        """
        with service_operation(operation):
            return planning.plan_impact(root, base, head, paths, full, select_project,
                                        select_tag, select_product, exclude_tag, shard)

    server.tool(annotations=READ_ONLY)(plan_impact)

    def inspect_sourcing_snapshot(path: str) -> SourcingSnapshotReport:
        """Check a recorded supplier snapshot, without live sourcing or purchase approval.

        Supply a checkout-relative build artifact containing typed sourcing-snapshot JSON.
        PASS checks recorded offer identities and catalog part references; it does not
        establish current stock, price, component approval or authorization to build.
        """
        with service_operation(operation):
            return planning.inspect_sourcing_snapshot(root, path)

    server.tool(annotations=READ_ONLY)(inspect_sourcing_snapshot)

    def get_project(project_id: str) -> McpProjectReport:
        """Read one registered project's inventory, manifest and authored test expectations."""
        with service_operation(operation):
            report = inventory(root)
            if report.status != "PASS":
                raise ValueError("Project discovery failed: " + "; ".join(
                    issue.message for issue in report.issues
                ))
            project = next((item for item in report.projects if item.id == project_id), None)
            if project is None:
                raise ValueError(f"Unknown project ID: {project_id}. Call list_projects first.")
            path = repo_path(root, project.manifest)
            manifest = read_model(path, ProjectManifest)
            contract_path = repo_path(path.parent, manifest.checks)
            contract = (read_model(contract_path, ProjectTestContract)
                        if contract_path.is_file() else None)
            return McpProjectReport(project=project, manifest=manifest, contract=contract)

    server.tool(annotations=READ_ONLY)(get_project)

    def doctor(
        project_id: str | None = None, native: bool = False,
        toolchain_id: str | None = None, runner: NativeRunner = "auto",
        electrical: bool = False,
    ) -> TemplateDoctorReport:
        """Inspect setup without running project tests; select a project for native readiness."""
        with service_operation(operation):
            return inspect_environment(
                root, native=native, project_id=project_id, toolchain_id=toolchain_id, runner=runner,
                electrical=electrical, ngspice="ngspice",
            )

    server.tool(annotations=READ_ONLY)(doctor)

    def document(name: DocumentName) -> str:
        with operation:
            try:
                return repo_path(root, workflow_guide(root, DOCUMENTS[name])).read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                raise ResourceError(str(exc)) from exc

    def read_document(name: DocumentName) -> str:
        """Read a named workflow guide from this checkout, including connection instructions."""
        return document(name)

    server.tool(annotations=READ_ONLY)(read_document)

    def resource_reader(name: DocumentName) -> Callable[[], str]:
        def read() -> str:
            return document(name)
        return read

    for name in DOCUMENTS:
        server.resource(
            f"kicad://docs/{name}", name=name, mime_type="text/markdown",
            description=f"Repository workflow guide: {name}",
        )(resource_reader(name))

    def preview_import(source: str, project_id: str, toolchain_id: str) -> ProjectImportReport:
        """Preview one .kicad_pro import without writing. Relative sources use the checkout.

        Sources must be inside the checkout or an enabled import root. The importer
        inventories the source directory's siblings too. Review hashes and exclusions;
        a PASS preview does not validate the electrical design.
        """
        with service_operation(operation):
            path = import_path(root, source, permitted_sources)
            return import_design(root, path, project_id, toolchain_id, dry_run=True)

    server.tool(annotations=READ_ONLY)(preview_import)

    def scan_imports(source_directory: str, toolchain_id: str) -> ImportInventoryReport:
        """Triage a permitted source directory into individual import previews; no files copied."""
        with service_operation(operation):
            path = import_path(root, source_directory, permitted_sources, directory=True)
            # The directory scanner must not resolve linked candidate files before authorization.
            for candidate in path.rglob("*.kicad_pro"):
                repo_path(path, candidate.relative_to(path).as_posix())
            return scan_designs(root, path, toolchain_id)

    server.tool(annotations=READ_ONLY)(scan_imports)

    def diagnose_import(source: str, project_id: str, toolchain_id: str) -> DiagnosticReport:
        """Triage one import into blockers, exclusions and repair guidance; save an ignored receipt."""
        with service_operation(operation):
            path = import_path(root, source, permitted_sources)
            return workflow.diagnose_import(root, path, project_id, toolchain_id)

    server.tool(annotations=CREATE_ONLY)(diagnose_import)

    def rescue_project(project_id: str) -> LocalRescueReport:
        """Inspect one island when global discovery is broken; always UNVERIFIED_GLOBAL.

        Saves an ignored receipt without running project tests. Repair discovery before
        normal diagnosis/checks; this result is never CI or release evidence.
        """
        with service_operation(operation):
            return workflow.rescue_project(root, project_id)

    server.tool(annotations=CREATE_ONLY)(rescue_project)

    def list_artifacts(
        directory: str = "build", offset: int = 0, limit: int = 100,
    ) -> McpArtifactList:
        """List a bounded page of retained artifacts in a repository-relative build directory."""
        with service_operation(operation):
            return files.list_artifacts(root, directory, offset, limit)

    server.tool(annotations=READ_ONLY)(list_artifacts)

    def read_artifact(path: str, offset: int = 0, limit: int = 20000) -> McpFileContent:
        """Read a bounded text chunk or binary metadata from an ignored build artifact.

        Use repository-relative paths from list_artifacts. Logs, reports, BOM CSVs and
        SVG source are available; this never executes or renders embedded content.
        """
        with service_operation(operation):
            return files.read_artifact(root, path, offset, limit)

    server.tool(annotations=READ_ONLY)(read_artifact)

    def read_project_file(
        project_id: str, path: str, offset: int = 0, limit: int = 20000,
    ) -> McpFileContent:
        """Read an authored text file relative to a registered project island for repair."""
        with service_operation(operation):
            return files.read_project_file(root, project_id, path, offset, limit)

    server.tool(annotations=READ_ONLY)(read_project_file)

    def preview_project_edit(
        project_id: str, path: str, expected_sha256: str, old_text: str, new_text: str,
    ) -> McpEditPreview:
        """Preview one exact reviewed source replacement against the last-read SHA256.

        Close KiCad, read the source, and inspect this diff before applying. This does
        not infer a circuit repair or validate electrical correctness. Match exactly once.
        """
        with service_operation(operation):
            return files.preview_project_edit(
                root, project_id, path, expected_sha256, old_text, new_text,
            )

    server.tool(annotations=READ_ONLY)(preview_project_edit)

    def inspect_contract(project_id: str, native_summary: str) -> ContractCoachReport:
        """Compare source-bound native observations with authored expectations; retain UNREVIEWED.

        native_summary is a repository-relative build artifact. This reads evidence;
        it does not execute KiCad or modify the independent test contract.
        """
        with service_operation(operation):
            return workflow.inspect_contract(root, project_id, native_summary)

    server.tool(annotations=READ_ONLY)(inspect_contract)

    def inspect_3d_models(project_id: str) -> ModelInventoryReport:
        """Inspect a PCB's placed-footprint model assignments without executing native kicad_tooling.

        READY describes static references only. REVIEW preserves missing, hidden or
        toolchain-dependent geometry; candidate filenames are not verified package matches.
        """
        with service_operation(operation):
            return workflow.inspect_3d_models(root, project_id)

    server.tool(annotations=READ_ONLY)(inspect_3d_models)

    def preview_model_population(
        project_id: str, board_sha256: str, assignments: tuple[McpModelMapAssignment, ...],
    ) -> ModelPopulationReport:
        """Preview explicit model assignments and retain a fresh ignored PLAN receipt.

        Supply the board SHA256 from read_project_file and reviewed reference/model
        pairs. Model paths are checkout-relative declared source assets. Review the
        board and manifest diffs before applying; package identity and fit stay unverified.
        """
        with service_operation(operation):
            reviewed = tuple(ModelMapAssignment(
                reference=item.reference, model=item.model, candidate_assets=tuple(item.candidate_assets),
                model_sha256=item.model_sha256,
            ) for item in assignments)
            return workflow.preview_model_population(root, project_id, board_sha256, reviewed)

    server.tool(annotations=CREATE_ONLY)(preview_model_population)

    def check_release(manifest: str) -> ReleaseReadinessReport:
        """Verify a retained release manifest and its source/evidence; creates no approval."""
        with service_operation(operation):
            return workflow.check_release(root, manifest)

    server.tool(annotations=READ_ONLY)(check_release)

    def verify_package(archive: str) -> ReleasePackageReport:
        """Verify an ignored ZIP through temporary restore without running restored project code."""
        with service_operation(operation):
            return workflow.verify_package(root, archive)

    server.tool(annotations=READ_ONLY)(verify_package)

    if allow_checks:
        def check_native_scope(
            view_id: str, project_ids: list[str] | None = None,
            product_ids: list[str] | None = None, tags: list[str] | None = None,
            exclude_tags: list[str] | None = None,
        ) -> McpNativeScopeReport:
            """Run the CLI grouped native lane with local kicad-cli and retain every failure.

            Matches kicad_tooling.ci --kicad. Include selectors form a union then exclusions
            subtract. Output uses fresh build/native/view_id. Each board checks its
            exact toolchain. Use check_project for automatic/container runner selection.
            """
            with service_operation(operation):
                return checks.check_native_scope(
                    root, view_id, tuple(project_ids or ()), tuple(product_ids or ()),
                    tuple(tags or ()), tuple(exclude_tags or ()),
                )

        server.tool(annotations=EXECUTION)(check_native_scope)

        def check_project(
            project_id: str, depth: Depth = "portable", runner: NativeRunner = "auto",
        ) -> ProjectVerificationReport:
            """Run trusted project tests and keep a fresh ignored verification receipt.

            This executes repository code, which may change files or contact services.
            Native depth uses exact local KiCad or pinned Docker and may download images
            and dependencies. Inspect status, diagnosis and run_directory in the report.
            """
            with service_operation(operation):
                if depth == "portable" and runner != "auto":
                    raise ValueError("A local or container runner requires native depth")
                # DiagnosticJournal creates this directory; reject links before it writes.
                repo_path(root, "build/diagnostics")
                return verify(root, project_id, depth=depth, runner=runner)

        server.tool(annotations=EXECUTION)(check_project)

        def diagnose_project(
            project_id: str, native_report: str | None = None, bom: str | None = None,
        ) -> DiagnosticReport:
            """Run project diagnosis with repair findings, optional native evidence and BOM review.

            Executes project/product tests and saves a receipt. Native report and BOM
            paths must be repository-relative build artifacts; BOM requires a matching
            native report. Stale or mismatched evidence must be repaired, not waived.
            """
            with service_operation(operation):
                return workflow.diagnose_project(root, project_id, native_report, bom)

        server.tool(annotations=EXECUTION)(diagnose_project)

        def capture_contract(
            project_id: str, runner: NativeRunner = "auto",
        ) -> ContractCoachReport:
            """Capture exact-toolchain netlist observations for review; never author expectations."""
            with service_operation(operation):
                return workflow.capture_contract(root, project_id, runner)

        server.tool(annotations=EXECUTION)(capture_contract)

        def check_scope(
            project_ids: list[str] | None = None, product_ids: list[str] | None = None,
            tags: list[str] | None = None, exclude_tags: list[str] | None = None,
            shard: str | None = None, jobs: int = 1,
        ) -> McpScopeReport:
            """Run selected project/product/tag checks or the full portable gate when unselected.

            Include selectors form a union; excluded tags subtract afterward. Executes
            repository tests. Use the full gate after shared tooling, catalog or policy edits.
            """
            with service_operation(operation):
                return workflow.check_scope(
                    root, tuple(project_ids or ()), tuple(product_ids or ()),
                    tuple(tags or ()), tuple(exclude_tags or ()), shard, jobs,
                )

        server.tool(annotations=EXECUTION)(check_scope)

    if allow_writes:
        def new_project(
            project_id: str, kind: ProjectKind, toolchain_id: str,
        ) -> ProjectScaffoldReport:
            """Create a new project skeleton without overwriting an existing island.

            Select kind and toolchain from the repository guidance and inventory. The
            skeleton is incomplete until an engineer supplies the design and expectations.
            """
            with service_operation(operation):
                return scaffold_project(root, project_id, kind, toolchain_id)

        server.tool(annotations=CREATE_ONLY)(new_project)

        def import_project(source: str, project_id: str, toolchain_id: str) -> ProjectImportReport:
            """Copy a previously reviewed import into a new project; preserve original source.

            Call preview_import first and review every exclusion. Source directory scope
            matches preview_import. This does not author electrical test expectations.
            """
            with service_operation(operation):
                path = import_path(root, source, permitted_sources)
                return import_design(root, path, project_id, toolchain_id)

        server.tool(annotations=CREATE_ONLY)(import_project)

    if allow_edits:
        def save_parts_preferences(
            project_id: str, preferences: PurchasingPreferences, expected_sha256: str | None = None,
        ) -> McpPurchasingPreferencesResult:
            """Save reviewed quantities and exact supplier SKUs to docs/purchasing.json.

            For an existing file, supply its current SHA256 from read_project_file.
            Omit the digest only to create a new file. These choices do not select
            substitutes, verify live supplier data or authorize a purchase.
            """
            with service_operation(operation):
                return parts.save_parts_preferences(root, project_id, preferences, expected_sha256)

        server.tool(annotations=EDIT)(save_parts_preferences)

        def apply_project_edit(
            project_id: str, path: str, expected_sha256: str, old_text: str, new_text: str,
        ) -> McpEditResult:
            """Apply a reviewed preview's exact source replacement; reject stale or ambiguous input.

            Requires the same SHA256 and replacement as the reviewed preview. Close KiCad
            first. Re-diagnose/check afterward, including native checks after CAD changes.
            This is an explicit source edit and does not approve the electrical decision.
            """
            with service_operation(operation):
                return files.apply_project_edit(
                    root, project_id, path, expected_sha256, old_text, new_text,
                )

        server.tool(annotations=EDIT)(apply_project_edit)

        def apply_model_population(project_id: str, plan: str) -> ModelPopulationReport:
            """Apply a reviewed model-population PLAN with unchanged source and planned edits.

            Give the checkout-relative model-population.json receipt path. Its sibling
            model-map.json supplies the explicit assignments. Close KiCad before applying;
            source, manifest, model hashes and diffs must still match. Rerun checks and
            inspect geometry afterward. This neither selects models nor approves fit.
            """
            with service_operation(operation):
                return workflow.apply_model_population(root, project_id, plan)

        server.tool(annotations=EDIT)(apply_model_population)

    if allow_exports:
        def init_model_map(project_id: str, view_id: str) -> ModelPopulationReport:
            """Create a source-bound model-map DRAFT in fresh build/model-maps/view_id.

            The draft lists unassigned footprints with blank model choices and candidate
            hints. Read it as an artifact, independently select physical models, then use
            preview_model_population before applying. The draft does not edit the board.
            """
            with service_operation(operation):
                return planning.init_model_map(root, project_id, view_id)

        server.tool(annotations=CREATE_ONLY)(init_model_map)

        def prepare_parts(
            project_id: str, view_id: str, native_summary: str | None = None,
            preferences: str | None = None, boards: Annotated[StrictInt, Field(gt=0)] | None = None,
            spare_percent: Annotated[StrictInt, Field(ge=0, le=100)] | None = None,
            spare_minimum: Annotated[StrictInt, Field(ge=0)] | None = None,
            runner: NativeRunner = "auto",
        ) -> PurchasingReport:
            """Write a source-bound parts checklist, BOM and conditional DigiKey CSV.

            Reuse a native_summary build artifact or enable checks for fresh native
            capture. Outputs use a fresh build/parts/view_id. Preferences default to
            selected docs/purchasing.json; alternative paths use that island's docs
            or build artifacts. Numeric overrides affect this run only. Metadata
            readiness never authorizes purchasing or overrides failed electrical checks.
            """
            with service_operation(operation):
                return parts.prepare_parts(
                    root, project_id, view_id, native_summary, preferences,
                    boards, spare_percent, spare_minimum, runner, allow_checks=allow_checks,
                )

        server.tool(annotations=EXECUTION if allow_checks else CREATE_ONLY)(prepare_parts)

        def generate_views(
            view_id: str, project_ids: list[str] | None = None,
            product_ids: list[str] | None = None, tags: list[str] | None = None,
            exclude_tags: list[str] | None = None,
        ) -> McpGenerationReport:
            """Generate product BOMs, harness schedules and review views into fresh ignored output.

            Select projects/products/tags or leave unselected for all configured views.
            These catalog-derived projections are distinct from native assembly/purchasing BOMs.
            """
            with service_operation(operation):
                return workflow.generate_views(
                    root, view_id, tuple(project_ids or ()), tuple(product_ids or ()),
                    tuple(tags or ()), tuple(exclude_tags or ()),
                )

        server.tool(annotations=CREATE_ONLY)(generate_views)

        def package_release(manifest: str, package_id: str) -> ReleasePackageReport:
            """Verify and package retained release evidence into a fresh ignored ZIP; no publishing."""
            with service_operation(operation):
                return workflow.package_release(root, manifest, package_id)

        server.tool(annotations=CREATE_ONLY)(package_release)

        def restore_package(archive: str, restore_id: str) -> ReleasePackageReport:
            """Restore an ignored ZIP to a fresh ignored checkout, without executing its scripts."""
            with service_operation(operation):
                return workflow.restore_package(root, archive, restore_id)

        server.tool(annotations=CREATE_ONLY)(restore_package)

        if allow_checks:
            def export_project(
                project_id: str, export_id: str, runner: NativeRunner = "auto",
                assembly_variant: str | None = None,
            ) -> ReleaseExportReport:
                """Export Gerbers, drills, placements and assembly/purchasing BOMs for review.

                Requires clean committed source, declared export settings and exact KiCad.
                Writes fresh ignored evidence only. Export success is not release approval.
                """
                with service_operation(operation):
                    return workflow.export_project(root, project_id, export_id, runner, assembly_variant)

            server.tool(annotations=EXECUTION)(export_project)

            def export_3d(
                project_id: str, view_id: str, runner: NativeRunner = "auto",
                assembly_variant: str | None = None,
            ) -> ThreeDReport:
                """Generate top/angled PNG, STEP and GLB in a fresh ignored 3D receipt.

                Uses exact local KiCad or a pinned container; never edits the board or
                assigns models. Export PASS can still have model coverage REVIEW. Inspect
                actual images and geometry before making mechanical decisions.
                """
                with service_operation(operation):
                    return workflow.export_3d(root, project_id, view_id, runner, assembly_variant)

            server.tool(annotations=EXECUTION)(export_3d)

            def prepare_review(
                project_id: str, release_id: str, runner: NativeRunner = "auto",
            ) -> ReleaseManifest:
                """Prepare an engineering_review candidate with portable/native/export evidence.

                Requires clean committed source and an exact runner. Never creates production
                approval, a tag, a purchase or a manufacturing authorization.
                """
                with service_operation(operation):
                    return workflow.prepare_review(root, project_id, release_id, runner)

            server.tool(annotations=EXECUTION)(prepare_review)

            def prepare_review_scope(
                release_id: str, project_ids: list[str] | None = None,
                variants: list[str] | None = None, portable: str | None = None,
                runner: NativeRunner = "auto",
            ) -> ReleaseManifest:
                """Prepare multiple projects or explicit PRODUCT:VARIANT choices for review.

                Requires clean committed source, one common toolchain and exact native
                checks. Optional portable evidence must be a source-bound build artifact.
                The candidate remains engineering_review without approval or manufacture authority.
                """
                with service_operation(operation):
                    return workflow.prepare_review_scope(
                        root, release_id, tuple(project_ids or ()), tuple(variants or ()),
                        portable, runner,
                    )

            server.tool(annotations=EXECUTION)(prepare_review_scope)

    if allow_edits:
        def init_electrical(project_id: str, ngspice_version: str = "UNREVIEWED") -> ElectricalSetupReport:
            """Create pending electrical requirements without overwriting existing contracts.

            An engineer must author limits and reviewed model bindings before analysis.
            Initialization does not approve electrical expectations or authorize a build.
            """
            with service_operation(operation):
                return electrical.init_electrical(root, project_id, ngspice_version)

        server.tool(annotations=EDIT)(init_electrical)

    if allow_exports:
        def capture_electrical_inputs(
            project_id: str, view_id: str, models: list[str] | None = None,
        ) -> ElectricalInputInventory:
            """Capture UNREVIEWED source/model hashes in a fresh ignored receipt."""
            with service_operation(operation):
                return electrical.capture_electrical_inputs(root, project_id, view_id, tuple(models or ()))

        server.tool(annotations=CREATE_ONLY)(capture_electrical_inputs)

        def export_electrical_charts(view_id: str, receipt: str) -> ElectricalChartsReport:
            """Export charts and full precision CSV from a saved, hashed electrical receipt.

            This does not rerun simulation or approve physical behavior.
            Missing or failed waveforms remain explicit in the report.
            """
            with service_operation(operation):
                return new_workflows.export_electrical_charts(root, view_id, receipt)

        server.tool(annotations=CREATE_ONLY)(export_electrical_charts)

        def export_electrical_chart_suite(view_id: str, suite: str) -> ElectricalChartsSuiteReport:
            """Export charts for every project in a saved electrical suite receipt."""
            with service_operation(operation):
                return new_workflows.export_electrical_chart_suite(root, view_id, suite)

        server.tool(annotations=CREATE_ONLY)(export_electrical_chart_suite)

    if allow_checks:
        def analyze_electrical(
            project_id: str, view_id: str, native_summary: str | None = None,
            runner: NativeRunner = "auto",
        ) -> ElectricalAnalysisReport:
            """Analyze reviewed grounding, power and frequency requirements with fixed executables.

            Optional native_summary is source-bound build evidence. FAIL/NOT_CONFIGURED
            remain explicit. Simulated results do not establish physical acceptance.
            """
            with service_operation(operation):
                return electrical.analyze_electrical(root, project_id, view_id, native_summary, runner)

        server.tool(annotations=EXECUTION)(analyze_electrical)

        def check_electrical_scope(
            project_ids: list[str] | None = None, product_ids: list[str] | None = None,
            tags: list[str] | None = None, exclude_tags: list[str] | None = None,
        ) -> ElectricalSuiteReport:
            """Run the CLI's selected electrical suite, preserving failures and missing requirements."""
            with service_operation(operation):
                return electrical.check_electrical_scope(
                    root, tuple(project_ids or ()), tuple(product_ids or ()),
                    tuple(tags or ()), tuple(exclude_tags or ()),
                )

        server.tool(annotations=EXECUTION)(check_electrical_scope)

        if allow_exports:
            def convert_pcb(
                source: str, project_id: str, toolchain_id: str,
                input_format: ForeignFormat = "auto", runner: NativeRunner = "auto",
            ) -> ForeignPcbReport:
                """Stage a foreign PCB conversion with hashes, native findings and an import preview.

                Source must be inside this checkout or a configured import root. Review
                converted geometry and warnings before the separate project import.
                Conversion does not modify the original or register a design.
                """
                with service_operation(operation):
                    return conversion.convert_pcb(
                        root, source, project_id, toolchain_id, input_format, runner,
                        import_roots=permitted_sources,
                    )

            server.tool(annotations=EXECUTION)(convert_pcb)

    if allow_exports:
        def prepare_part_picker(
            project_id: str, view_id: str, native_summary: str | None = None,
            runner: NativeRunner = "auto",
        ) -> PartPickerReport:
            """List reviewed catalog choices from source-bound component evidence.

            Fresh native capture also requires --allow-checks. Saved evidence must be
            a build artifact. Available choices do not establish electrical suitability.
            """
            with service_operation(operation):
                return part_tools.prepare_part_picker(
                    root, project_id, view_id, native_summary, runner, allow_checks=allow_checks,
                )

        server.tool(annotations=EXECUTION if allow_checks else CREATE_ONLY)(prepare_part_picker)

        def preview_part_selection(
            project_id: str, view_id: str, picker_report: str,
            assignments: list[PartSelectionAssignment],
        ) -> PartSelectionReport:
            """Preview explicit reference/part_id choices offered by a retained picker.

            Read the exact source diff and locked map before applying. This does not
            edit catalog identities, approve substitutions or change native source.
            """
            with service_operation(operation):
                return part_tools.preview_part_selection(root, project_id, view_id, picker_report, assignments)

        server.tool(annotations=CREATE_ONLY)(preview_part_selection)

        def preview_model_sync(project_id: str, view_id: str) -> PartSelectionReport:
            """Preview model assignments from saved selections after KiCad's PCB update."""
            with service_operation(operation):
                return part_tools.preview_model_sync(root, project_id, view_id)

        server.tool(annotations=CREATE_ONLY)(preview_model_sync)

        def preview_auto_cad(project_id: str, view_id: str) -> AutoCadReport:
            """Preview paired footprint/model imports and retain exact source changes.

            Official CAD downloads need host --allow-downloads. Without it,
            repository, installed or validated cached assets can be used. Physical fit still needs review.
            """
            with service_operation(operation):
                return part_tools.preview_auto_cad(root, project_id, view_id, allow_downloads=allow_downloads)

        server.tool(annotations=EXECUTION if allow_downloads else CREATE_ONLY)(preview_auto_cad)

        def source_cad(
            project_id: str, view_id: str, supplier_id: str,
            expected_mpn: str | None = None, refresh: bool = False,
        ) -> CadSourcingReview:
            """Check an exact LCSC identity, freeze CAD and preview project import.

            Without --allow-downloads, only an intact verified cache may be used.
            A provider response or internal pin match is not a part approval.
            """
            with service_operation(operation):
                return new_workflows.source_cad(
                    root, project_id, view_id, supplier_id, expected_mpn, refresh,
                    allow_downloads=allow_downloads,
                )

        server.tool(annotations=EXECUTION if allow_downloads else CREATE_ONLY)(source_cad)

        def preview_cad_import(project_id: str, view_id: str,
                               source_report: str) -> CadImportReport:
            """Preview source changes from a saved exact-part CAD cache receipt."""
            with service_operation(operation):
                return new_workflows.preview_cad_import(root, project_id, view_id, source_report)

        server.tool(annotations=CREATE_ONLY)(preview_cad_import)

        if allow_checks:
            def check_step_alignment(
                project_id: str, view_id: str, supplier_id: str,
                expected_mpn: str | None = None, refresh: bool = False,
                source_report: str | None = None,
            ) -> CadStepReport:
                """Render paired WRL/STEP views with pinned KiCad for visual review.

                A saved source_report reuses an exact frozen part. Network fetches
                require host --allow-downloads. REVIEW requires human inspection;
                STEP is not installed and physical fit is not approved.
                """
                with service_operation(operation):
                    return new_workflows.check_step_alignment(
                        root, project_id, view_id, supplier_id, expected_mpn, refresh,
                        source_report, allow_downloads=allow_downloads,
                    )

            server.tool(annotations=EXECUTION)(check_step_alignment)

        def prepare_supplier_handoff(
            project_id: str, view_id: str, parts_report: str,
        ) -> SupplierHandoffReport:
            """Prepare a source-bound DigiKey BOM payload for review without contacting the supplier.

            Inspect the retained payload, transmitted fields and handoff SHA-256 before
            a separate submission. This creates neither a supplier list nor a purchase.
            """
            with service_operation(operation):
                return part_tools.prepare_supplier_handoff(root, project_id, view_id, parts_report)

        server.tool(annotations=CREATE_ONLY)(prepare_supplier_handoff)

    if allow_edits:
        def apply_part_selection(
            project_id: str, view_id: str, selection_map: str, expected_sha256: str,
        ) -> PartSelectionReport:
            """Apply a reviewed locked selection whose exact artifact digest is still current.

            Changes selected board source only; rerun native checks and inspect geometry.
            """
            with service_operation(operation):
                return part_tools.apply_part_selection(root, project_id, view_id, selection_map, expected_sha256)

        server.tool(annotations=EDIT)(apply_part_selection)

        def apply_auto_cad(
            project_id: str, view_id: str, plan: str, expected_sha256: str,
        ) -> AutoCadReport:
            """Apply exactly a retained CAD plan with current source and plan hashes.

            A missing official asset can be downloaded only with host --allow-downloads.
            Source edits remain reviewable and require subsequent native/geometry checks.
            """
            with service_operation(operation):
                return part_tools.apply_auto_cad(
                    root, project_id, view_id, plan, expected_sha256, allow_downloads=allow_downloads,
                )

        server.tool(annotations=EXECUTION if allow_downloads else EDIT)(apply_auto_cad)

        def apply_cad_import(
            project_id: str, view_id: str, plan: str, expected_sha256: str,
        ) -> CadImportReport:
            """Import project-local CAD from the exact reviewed plan bytes.

            Current source, cached assets and planned edits are rechecked before
            applying. Placed components are not altered or electrically approved.
            """
            with service_operation(operation):
                return new_workflows.apply_cad_import(root, project_id, view_id, plan, expected_sha256)

        server.tool(annotations=EDIT)(apply_cad_import)

    if allow_supplier_submissions:
        def submit_supplier_handoff(handoff: str, expected_sha256: str) -> SupplierHandoffReport:
            """Submit one explicitly reviewed BOM to DigiKey for external product matching.

            Sends the prepared identifiers, quantities, references and manufacturer notes.
            Requires the exact reviewed handoff digest and current source. An attempt is
            recorded before transmission; repeated or uncertain attempts never retry.
            No order is placed. This capability requires host --allow-supplier-submissions.
            """
            with service_operation(operation):
                return part_tools.submit_supplier_handoff(root, handoff, expected_sha256)

        server.tool(annotations=EXECUTION)(submit_supplier_handoff)

    return server
