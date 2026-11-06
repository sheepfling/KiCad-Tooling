"""Prepare candidates from executed checks, without inventing review approvals."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .command_evidence_models import CommandEvidence
from .container_git import git_metadata_mounts
from .contracts import read_model, repo_path, write_model
from .discovery import load_config, load_registry
from .electrical_report_models import ElectricalAnalysisReport
from .evidence import digest, evidence_path, source_state
from .generation import expected_outputs
from .markdown import release_review, write_markdown
from .models import (
    InterfacesCatalog,
    LibrariesCatalog,
    ReleaseExportReport,
    ScopedReleasePortableReport,
)
from .native_dependencies import prepare_native_dependencies
from .native_dependency_models import NativeDependencyPreparationRequest
from .native_project_validation_models import ValidationSummary
from .policy_issue_models import PolicyIssue
from .portable_evidence import verify_release_portable
from .product_models import (
    ProductRecord,
)
from .product_repository_models import ProductRepository
from .project_models import (
    ProjectManifest,
    ProjectRecord,
)
from .project_static_pipeline import run_project_static_pipeline
from .project_static_pipeline_models import ProjectStaticPipelineRequest
from .release import (
    configured_toolchains,
    load_release_repository,
    selected_products,
    selected_project_records,
)
from .release_board_variant_selection import (
    ReleaseBoardVariantSelection,
    require_release_board_variant_sources_current,
    resolve_release_board_variants,
)
from .release_contract_models import (
    EvidenceFile,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseEvidence,
    ReleaseInterface,
    ReleaseLibrary,
    ReleaseManifest,
    ReleaseStatus,
    ReleaseVariant,
)
from .release_model_types import ReleaseClass
from .release_operation_models import ReleasePreparationRequest
from .release_population import verify_board_population


def reference(root: Path, path: Path) -> EvidenceFile:
    return EvidenceFile(path=path.relative_to(root).as_posix(), sha256=digest(path))


def run_native(
    root: Path,
    project: ProjectRecord,
    output: Path,
    cli: str | None,
    dependencies: Path | None,
    export_only: bool = False,
    assembly_variant: str | None = None,
) -> None:
    if cli is not None:
        if export_only:
            from .exports import export

            exported = export(root, project.config, output, cli, assembly_variant)
            if exported.status != "PASS":
                raise ValueError(f"Release exports failed for {project.id}; see {output}")
        else:
            from .native_project_validation import validate_project
            from .native_project_validation_models import NativeProjectValidationRequest

            native = validate_project(
                root,
                NativeProjectValidationRequest(
                    output=output,
                    cli=cli,
                    config_path=Path(project.config),
                ),
            )
            if native.status != "PASS":
                raise ValueError(f"Native checks failed for {project.id}; see {output}")
        return
    if dependencies is None:
        raise ValueError("Container dependencies were not prepared")
    config = load_config(root, project.config)
    command = (
        (
            "kicad_tooling.release",
            "export",
            "--project",
            project.id,
            *(("--assembly-variant", assembly_variant) if assembly_variant else ()),
        )
        if export_only
        else ("kicad_tooling.validate", "--config", project.config)
    )
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        *user,
        "--entrypoint",
        f"/work/{dependencies.as_posix()}/bin/python",
        "-e",
        "HOME=/tmp/kicad-release",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        f"{root}:/work",
        *git_metadata_mounts(root),
        "-w",
        "/work",
        config.image,
        "-I",
        "-B",
        "-m",
        *command,
        "--root",
        "/work",
        "--output",
        output.relative_to(root).as_posix(),
    )
    started = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.parent / f"{project.id}.container.command.json"
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, check=False, timeout=600
        )
        record = CommandEvidence(
            argv=argv,
            started_utc=started,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        record = CommandEvidence(argv=argv, started_utc=started, returncode=127, error=str(exc))
    write_model(log_path, record)
    if record.returncode != 0:
        raise ValueError(f"Pinned container failed for {project.id}; see {log_path}")


def resolve_variants(root: Path, values: tuple[str, ...]) -> tuple[ReleaseVariant, ...]:
    """Compatibility adapter for source-current release-variant selection."""
    from .release_variants import resolve_variants as select_release_variants

    return select_release_variants(root, values)


def _selected_scope_with_repository(
    root: Path,
    candidate: ReleaseManifest,
) -> tuple[
    ProductRepository,
    tuple[ProjectRecord, ...],
    tuple[ProductRecord, ...],
    ReleaseBoardVariantSelection,
]:
    """Validate release scope and its common toolchain before creating any evidence."""
    repository = load_release_repository(root, candidate)
    findings: list[PolicyIssue] = list(repository.issues)
    products, selection_issues = selected_products(repository, candidate)
    findings.extend(selection_issues)
    projects = selected_project_records(repository, products, candidate.projects)
    if findings or not projects:
        raise ValueError(f"Invalid release selection: {findings}")
    if candidate.release_class is not ReleaseClass.ENGINEERING_REVIEW and any(
        project.assurance_profile != "production" or project.status != "release_candidate"
        for project in projects
    ):
        raise ValueError(
            "Non-review releases require production-profile release_candidate projects"
        )
    if len(configured_toolchains(root, projects)) != 1:
        raise ValueError("Prepare separate release candidates for different toolchains")
    board_variants = resolve_release_board_variants(
        repository,
        candidate.variants,
        (project.id for project in projects),
    )
    require_release_board_variant_sources_current(root, board_variants)
    for project in projects:
        if (
            board_variants.for_project(project.id).state == "ASSIGNED"
            and read_model(
                repo_path(root, project.config),
                ProjectManifest,
            ).release_exports
            is None
        ):
            raise ValueError(
                f"{project.id} needs release_exports to apply its product KiCad variant"
            )
    return repository, projects, products, board_variants


def selected_scope(
    root: Path,
    candidate: ReleaseManifest,
) -> tuple[tuple[ProjectRecord, ...], tuple[ProductRecord, ...]]:
    """Compatibility projection of the selected projects and products."""
    _, projects, products, _ = _selected_scope_with_repository(root, candidate)
    return projects, products


def selected_projects(root: Path, candidate: ReleaseManifest) -> tuple[ProjectRecord, ...]:
    """Return projects only after validating the full release and population scope."""
    return selected_scope(root, candidate)[0]


def prepare_request(root: Path, request: ReleasePreparationRequest) -> ReleaseManifest:
    """Prepare one candidate from a typed project scope and execution request."""
    release_id = request.release_id
    project_ids = request.project_ids
    variants = request.variants
    release_class = request.release_class
    cli = request.cli
    portable = request.portable
    ngspice = request.ngspice
    root = root.resolve()
    source = source_state(root)
    if not source.clean or source.commit is None:
        raise ValueError(
            "Commit the reviewed source first; release preparation requires a clean checkout"
        )
    # Validate caller values before making any output directories.
    candidate = ReleaseManifest(
        release_id=release_id,
        release_class=release_class,
        status=ReleaseStatus.CANDIDATE,
        source_commit=source.commit,
        toolchain_id="pending",
        projects=project_ids,
        variants=variants,
        libraries=(),
        interfaces=(),
        artifacts=(),
    )
    repository, projects, products, board_variants = _selected_scope_with_repository(
        root, candidate
    )
    from .electrical_evidence import required_projects, verify_electrical

    electrical_ids = required_projects(root, projects, release_class)
    toolchains = configured_toolchains(root, projects)
    output = repo_path(root, f"build/releases/{release_id}")
    output.mkdir(parents=True, exist_ok=False)
    selected_ids = tuple(project.id for project in projects)
    if portable is None:
        portable = output / "portable.json"
        checks = run_project_static_pipeline(
            root,
            ProjectStaticPipelineRequest(project_ids=selected_ids),
        )
        if source_state(root) != source:
            raise ValueError("Source changed while running selected portable checks")
        write_model(
            portable,
            ScopedReleasePortableReport(
                source=source,
                projects=selected_ids,
                checks=checks,
            ),
        )
    else:
        portable = repo_path(root, portable.as_posix())
    portable_reference = reference(root, portable)
    verify_release_portable(root, portable_reference, source, selected_ids)
    dependencies: Path | None = None
    if cli is None:
        dependencies = Path(f"build/release-deps/{release_id}")
        prepare_native_dependencies(
            NativeDependencyPreparationRequest(
                root=root,
                image=load_config(root, projects[0].config).image,
                output=dependencies,
            )
        )
    native: dict[str, EvidenceFile] = {}
    exports: dict[str, EvidenceFile] = {}
    electrical: dict[str, EvidenceFile] = {}
    for project in projects:
        require_release_board_variant_sources_current(root, board_variants)
        native_output = output / "native" / project.id
        run_native(root, project, native_output, cli, dependencies)
        native[project.id] = reference(root, native_output / "summary.json")
        if project.id in electrical_ids:
            from .electrical_operation_models import ElectricalAnalysisRequest
            from .electrical_runner import analyze_request

            electrical_output = output / "electrical" / project.id
            analysis = analyze_request(
                root,
                ElectricalAnalysisRequest(
                    project_id=project.id,
                    output=electrical_output,
                    native_summary=native_output / "summary.json",
                    cli=cli or "kicad-cli",
                    ngspice=ngspice,
                    runner_mode="container" if cli is None else "local",
                ),
            )
            if analysis.status != "PASS":
                raise ValueError(
                    f"Electrical checks failed for {project.id}; see {electrical_output}"
                )
            electrical[project.id] = reference(root, electrical_output / "electrical.json")
            verify_electrical(root, electrical[project.id], source, project.id, native[project.id])
        manifest = read_model(repo_path(root, project.config), ProjectManifest)
        if manifest.release_exports is not None:
            export_output = output / "exports" / project.id
            board_variant = board_variants.for_project(project.id)
            require_release_board_variant_sources_current(root, board_variants)
            run_native(
                root,
                project,
                export_output,
                cli,
                dependencies,
                export_only=True,
                assembly_variant=(
                    board_variant.variant_name if board_variant.state == "ASSIGNED" else None
                ),
            )
            verify_board_population(
                products,
                variants,
                project.id,
                export_output / "assembly/bom.csv",
                product_sources=repository.product_sources,
            )
            exports[project.id] = reference(root, export_output / "exports.json")
        elif board_variants.for_project(project.id).state == "ASSIGNED":
            raise ValueError(f"{project.id} KiCad assembly variant has no native export evidence")
    # Only retain projections of selected product variants in this candidate.
    projections = expected_outputs(root, tuple(project.id for project in projects))
    for selection in variants:
        for name, content in projections.items():
            if f"/{selection.product}/build/{selection.variant}." in name:
                destination = output / "products" / selection.product / Path(name).name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
    write_markdown(
        output / "review.md",
        release_review(
            release_id,
            source.commit,
            release_class.value,
            (
                (
                    project.id,
                    "PASS — retained electrical evidence"
                    if project.id in electrical
                    else "NOT_CONFIGURED — electrical analysis not assessed",
                )
                for project in projects
            ),
        ),
    )
    artifacts = tuple(
        ReleaseArtifact(
            id=f"artifact-{index}",
            kind=artifact_kind(path, output),
            path=path.relative_to(root).as_posix(),
            sha256=digest(path),
            intended_use="Release candidate review; see approval and release class.",
        )
        for index, path in enumerate(sorted(output.rglob("*")))
        if path.is_file()
    )
    registry = load_registry(root)
    library_ids = {identifier for project in projects for identifier in project.library_ids}
    interface_ids = {identifier for project in projects for identifier in project.interfaces}
    libraries = read_model(repo_path(root, registry.catalogs.libraries), LibrariesCatalog)
    interfaces = read_model(repo_path(root, registry.catalogs.interfaces), InterfacesCatalog)
    candidate = candidate.model_copy(
        update={
            "toolchain_id": next(iter(toolchains)),
            "libraries": tuple(
                ReleaseLibrary(
                    id=library.id,
                    version=library.version,
                    provenance_sha256=library.provenance_sha256,
                    licensing_sha256=library.licensing_sha256,
                )
                for library in libraries.libraries
                if library.id in library_ids
            ),
            "interfaces": tuple(
                ReleaseInterface(id=interface.id, revision=interface.revision)
                for interface in interfaces.interfaces
                if interface.id in interface_ids
            ),
            "artifacts": artifacts,
            "evidence": ReleaseEvidence(
                portable=portable_reference, native=native, exports=exports, electrical=electrical
            ),
        }
    )
    if source_state(root) != source:
        raise ValueError(
            "Source changed while preparing the release; retained outputs are not a candidate"
        )
    require_release_board_variant_sources_current(root, board_variants)
    write_model(output / "manifest.json", candidate)
    return candidate


def prepare(
    root: Path,
    release_id: str,
    project_ids: tuple[str, ...],
    variants: tuple[ReleaseVariant, ...] = (),
    release_class: ReleaseClass = ReleaseClass.ENGINEERING_REVIEW,
    cli: str | None = None,
    portable: Path | None = None,
    ngspice: str = "ngspice",
) -> ReleaseManifest:
    """Compatibility adapter for the established release-preparation arguments."""
    return prepare_request(
        root,
        ReleasePreparationRequest(
            release_id=release_id,
            project_ids=project_ids,
            variants=variants,
            release_class=release_class,
            cli=cli,
            portable=portable,
            ngspice=ngspice,
        ),
    )


def artifact_kind(path: Path, output: Path) -> ReleaseArtifactKind:
    relative = path.relative_to(output)
    if path.name == "review.md":
        return ReleaseArtifactKind.REVIEW_RECORD
    if path.name.endswith("bom.csv"):
        return ReleaseArtifactKind.BOM
    if "review" in relative.parts and path.name == "schematic.pdf":
        return ReleaseArtifactKind.SCHEMATIC_EXPORT
    if "review" in relative.parts and path.name == "pcb.pdf":
        return ReleaseArtifactKind.PCB_EXPORT
    if "fabrication" in relative.parts:
        return ReleaseArtifactKind.FABRICATION_PACKAGE
    if "assembly" in relative.parts:
        return ReleaseArtifactKind.ASSEMBLY_PACKAGE
    if "schematic" in relative.parts and path.suffix == ".svg":
        return ReleaseArtifactKind.SCHEMATIC_EXPORT
    if path.name == "pcb.svg":
        return ReleaseArtifactKind.PCB_EXPORT
    if ".harness-schedule." in path.name:
        return ReleaseArtifactKind.HARNESS_EXPORT
    return ReleaseArtifactKind.VALIDATION_REPORT


def retained_paths(root: Path, manifest: ReleaseManifest) -> set[str]:
    """Close artifact inventories over every hashed native report dependency."""
    paths = {artifact.path for artifact in manifest.artifacts}
    if manifest.evidence is None:
        raise ValueError("Candidate lacks evidence")
    paths.add(manifest.evidence.portable.path)
    for reference_file in manifest.evidence.electrical.values():
        paths.add(reference_file.path)
        electrical_report = read_model(
            evidence_path(root, reference_file), ElectricalAnalysisReport
        )
        paths.update(
            (Path(reference_file.path).parent / name).as_posix()
            for name in electrical_report.artifacts_sha256
        )
    for reference_file in manifest.evidence.native.values():
        paths.add(reference_file.path)
        report = read_model(evidence_path(root, reference_file), ValidationSummary)
        paths.update(
            (Path(reference_file.path).parent / name).as_posix() for name in report.artifacts_sha256
        )
    for reference_file in manifest.evidence.exports.values():
        paths.add(reference_file.path)
        export_report = read_model(evidence_path(root, reference_file), ReleaseExportReport)
        paths.update(
            (Path(reference_file.path).parent / name).as_posix()
            for name in export_report.artifacts_sha256
        )
    return paths
