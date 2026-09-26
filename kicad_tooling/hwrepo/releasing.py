"""Prepare candidates from executed checks, without inventing review approvals."""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .container_git import git_metadata_mounts
from .contracts import read_model, repo_path, write_model
from .discovery import load_config, load_registry
from .evidence import digest, evidence_path, source_state, verify_release_portable
from .generation import expected_outputs
from .layout import layout
from .markdown import release_review, write_markdown
from .models import (
    CommandEvidence,
    EvidenceFile,
    InterfacesCatalog,
    LibrariesCatalog,
    PolicyIssue,
    ProductIndex,
    ProductRecord,
    ProjectManifest,
    ProjectRecord,
    ProjectStaticPipelineReport,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseClass,
    ReleaseEvidence,
    ReleaseInterface,
    ReleaseLibrary,
    ReleaseManifest,
    ReleaseStatus,
    ReleaseVariant,
    ScopedReleasePortableReport,
    ValidationSummary,
)
from .release import (
    configured_toolchains,
    load_release_repository,
    selected_board_variants,
    selected_products,
    selected_project_records,
    verify_board_population,
)


def reference(root: Path, path: Path) -> EvidenceFile:
    return EvidenceFile(path=path.relative_to(root).as_posix(), sha256=digest(path))


def run_native(root: Path, project: ProjectRecord, output: Path, cli: str | None,
               dependencies: Path | None, export_only: bool = False,
               assembly_variant: str | None = None) -> None:
    if cli is not None:
        if export_only:
            from .exports import export

            exported = export(root, project.config, output, cli, assembly_variant)
            if exported.status != "PASS":
                raise ValueError(f"Release exports failed for {project.id}; see {output}")
        else:
            from ..validate import validate

            native = validate(root, output, cli, Path(project.config))
            if native.status != "PASS":
                raise ValueError(f"Native checks failed for {project.id}; see {output}")
        return
    if dependencies is None:
        raise ValueError("Container dependencies were not prepared")
    config = load_config(root, project.config)
    command = ("kicad_tooling.release", "export", "--project", project.id,
               *(("--assembly-variant", assembly_variant) if assembly_variant else ())) if export_only else (
        "kicad_tooling.validate", "--config", project.config)
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        import os

        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    argv = ("docker", "run", "--rm", "--platform", "linux/amd64", *user,
                    "--entrypoint", f"/work/{dependencies.as_posix()}/bin/python",
                    "-e", "HOME=/tmp/kicad-release",
                    "-e", "PYTHONDONTWRITEBYTECODE=1",
                    "-v", f"{root}:/work", *git_metadata_mounts(root),
                    "-w", "/work", config.image, "-I", "-B", "-m", *command,
                    "--root", "/work", "--output", output.relative_to(root).as_posix())
    started = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.parent / f"{project.id}.container.command.json"
    try:
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False, timeout=600)
        record = CommandEvidence(argv=argv, started_utc=started, returncode=result.returncode,
                                 stdout=result.stdout, stderr=result.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        record = CommandEvidence(argv=argv, started_utc=started, returncode=127, error=str(exc))
    write_model(log_path, record)
    if record.returncode != 0:
        raise ValueError(f"Pinned container failed for {project.id}; see {log_path}")


def resolve_variants(root: Path, values: tuple[str, ...]) -> tuple[ReleaseVariant, ...]:
    """Resolve explicit PRODUCT:VARIANT choices to current typed revision identities."""
    if not values:
        return ()
    index = read_model(repo_path(root, layout(root).products), ProductIndex)
    indexed = {entry.id: entry for entry in index.products}
    if len(indexed) != len(index.products):
        raise ValueError(f"{layout(root).products} has duplicate product IDs")
    selections: list[ReleaseVariant] = []
    for value in values:
        product_id, separator, variant_id = value.partition(":")
        if not separator:
            raise ValueError("Variant selection uses PRODUCT:VARIANT")
        entry = indexed.get(product_id)
        if entry is None:
            raise ValueError(f"Unknown release product {product_id!r} in {layout(root).products}")
        product = read_model(repo_path(root, entry.path), ProductRecord)
        if product.id != product_id:
            raise ValueError(f"{entry.path}: product ID differs from {layout(root).products}")
        variant = next((item for item in product.variants if item.id == variant_id), None)
        if variant is None:
            raise ValueError(f"Unknown variant {variant_id!r} for product {product_id!r}")
        selections.append(ReleaseVariant(
            product=product.id, product_revision=product.revision,
            variant=variant.id, variant_revision=variant.revision,
        ))
    return tuple(selections)


def selected_scope(
    root: Path, candidate: ReleaseManifest,
) -> tuple[tuple[ProjectRecord, ...], tuple[ProductRecord, ...]]:
    """Validate release scope and its common toolchain before creating any evidence."""
    repository = load_release_repository(root, candidate)
    findings: list[PolicyIssue] = list(repository.issues)
    products = selected_products(repository, candidate, findings)
    projects = selected_project_records(repository, products, candidate.projects)
    if findings or not projects:
        raise ValueError(f"Invalid release selection: {findings}")
    if candidate.release_class is not ReleaseClass.ENGINEERING_REVIEW and any(
        project.assurance_profile != "production" or project.status != "release_candidate"
        for project in projects
    ):
        raise ValueError("Non-review releases require production-profile release_candidate projects")
    if len(configured_toolchains(root, projects)) != 1:
        raise ValueError("Prepare separate release candidates for different toolchains")
    board_variants = selected_board_variants(products, candidate.variants,
                                             (project.id for project in projects))
    for project in projects:
        if project.id in board_variants and read_model(
            repo_path(root, project.config), ProjectManifest,
        ).release_exports is None:
            raise ValueError(f"{project.id} needs release_exports to apply its product KiCad variant")
    return projects, products


def selected_projects(root: Path, candidate: ReleaseManifest) -> tuple[ProjectRecord, ...]:
    """Return projects only after validating the full release and population scope."""
    return selected_scope(root, candidate)[0]


def prepare(root: Path, release_id: str, project_ids: tuple[str, ...],
            variants: tuple[ReleaseVariant, ...] = (), release_class: ReleaseClass = ReleaseClass.ENGINEERING_REVIEW,
            cli: str | None = None, portable: Path | None = None,
            ngspice: str = "ngspice") -> ReleaseManifest:
    """Commit source first; reports and the candidate are then written under build/."""
    from ..ci import static_pipeline

    root = root.resolve()
    source = source_state(root)
    if not source.clean or source.commit is None:
        raise ValueError("Commit the reviewed source first; release preparation requires a clean checkout")
    # Validate caller values before making any output directories.
    candidate = ReleaseManifest(release_id=release_id, release_class=release_class,
                                status=ReleaseStatus.CANDIDATE, source_commit=source.commit,
                                toolchain_id="pending", projects=project_ids, variants=variants,
                                libraries=(), interfaces=(), artifacts=())
    projects, products = selected_scope(root, candidate)
    from .electrical_evidence import required_projects, verify_electrical

    electrical_ids = required_projects(root, projects, release_class)
    toolchains = configured_toolchains(root, projects)
    board_variants = selected_board_variants(products, variants,
                                             (project.id for project in projects))
    output = repo_path(root, f"build/releases/{release_id}")
    output.mkdir(parents=True, exist_ok=False)
    selected_ids = tuple(project.id for project in projects)
    if portable is None:
        portable = output / "portable.json"
        checks = static_pipeline(root, list(selected_ids))
        if not isinstance(checks, ProjectStaticPipelineReport):
            raise ValueError("Selected release portable checks did not return a project report")
        if source_state(root) != source:
            raise ValueError("Source changed while running selected portable checks")
        write_model(portable, ScopedReleasePortableReport(
            source=source, projects=selected_ids, checks=checks,
        ))
    else:
        portable = repo_path(root, portable.as_posix())
    portable_reference = reference(root, portable)
    verify_release_portable(root, portable_reference, source, selected_ids)
    dependencies: Path | None = None
    if cli is None:
        from ..native_deps import prepare as prepare_dependencies

        dependencies = Path(f"build/release-deps/{release_id}")
        prepare_dependencies(root, load_config(root, projects[0].config).image, dependencies)
    native: dict[str, EvidenceFile] = {}
    exports: dict[str, EvidenceFile] = {}
    electrical: dict[str, EvidenceFile] = {}
    for project in projects:
        native_output = output / "native" / project.id
        run_native(root, project, native_output, cli, dependencies)
        native[project.id] = reference(root, native_output / "summary.json")
        if project.id in electrical_ids:
            from .electrical_runner import analyze

            electrical_output = output / "electrical" / project.id
            analysis = analyze(root, project.id, electrical_output,
                               native_output / "summary.json", ngspice=ngspice)
            if analysis.status != "PASS":
                raise ValueError(f"Electrical checks failed for {project.id}; see {electrical_output}")
            electrical[project.id] = reference(root, electrical_output / "electrical.json")
            verify_electrical(root, electrical[project.id], source, project.id, native[project.id])
        manifest = read_model(repo_path(root, project.config), ProjectManifest)
        if manifest.release_exports is not None:
            export_output = output / "exports" / project.id
            run_native(root, project, export_output, cli, dependencies, export_only=True,
                       assembly_variant=board_variants.get(project.id))
            verify_board_population(products, variants, project.id,
                                    export_output / "assembly/bom.csv")
            exports[project.id] = reference(root, export_output / "exports.json")
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
        release_review(release_id, source.commit, release_class.value, (
            (project.id, "PASS — retained electrical evidence" if project.id in electrical
             else "NOT_CONFIGURED — electrical analysis not assessed") for project in projects
        )),
    )
    artifacts = tuple(ReleaseArtifact(id=f"artifact-{index}", kind=artifact_kind(path, output),
                        path=path.relative_to(root).as_posix(), sha256=digest(path),
                        intended_use="Release candidate review; see approval and release class.")
                      for index, path in enumerate(sorted(output.rglob("*"))) if path.is_file())
    registry = load_registry(root)
    library_ids = {identifier for project in projects for identifier in project.library_ids}
    interface_ids = {identifier for project in projects for identifier in project.interfaces}
    libraries = read_model(repo_path(root, registry.catalogs.libraries), LibrariesCatalog)
    interfaces = read_model(repo_path(root, registry.catalogs.interfaces), InterfacesCatalog)
    candidate = candidate.model_copy(update={
        "toolchain_id": next(iter(toolchains)),
        "libraries": tuple(ReleaseLibrary(id=library.id, version=library.version,
            provenance_sha256=library.provenance_sha256, licensing_sha256=library.licensing_sha256)
                           for library in libraries.libraries if library.id in library_ids),
        "interfaces": tuple(ReleaseInterface(id=interface.id, revision=interface.revision)
                            for interface in interfaces.interfaces if interface.id in interface_ids),
        "artifacts": artifacts,
        "evidence": ReleaseEvidence(portable=portable_reference, native=native, exports=exports,
                                    electrical=electrical),
    })
    if source_state(root) != source:
        raise ValueError("Source changed while preparing the release; retained outputs are not a candidate")
    write_model(output / "manifest.json", candidate)
    return candidate


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
        from .models import ElectricalAnalysisReport

        paths.add(reference_file.path)
        electrical_report = read_model(evidence_path(root, reference_file), ElectricalAnalysisReport)
        paths.update((Path(reference_file.path).parent / name).as_posix()
                     for name in electrical_report.artifacts_sha256)
    for reference_file in manifest.evidence.native.values():
        paths.add(reference_file.path)
        report = read_model(evidence_path(root, reference_file), ValidationSummary)
        paths.update((Path(reference_file.path).parent / name).as_posix() for name in report.artifacts_sha256)
    for reference_file in manifest.evidence.exports.values():
        from .models import ReleaseExportReport

        paths.add(reference_file.path)
        export_report = read_model(evidence_path(root, reference_file), ReleaseExportReport)
        paths.update((Path(reference_file.path).parent / name).as_posix() for name in export_report.artifacts_sha256)
    return paths
