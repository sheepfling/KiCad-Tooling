"""Build a source-bound onboarding review from the ordinary dry-run importer."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .diagnostics import diagnose_import
from .discovery import settings
from .evidence import digest
from .import_inventory import source_kind
from .import_review_html import render_import_review
from .import_review_models import ImportReviewDependency, ImportReviewFile, ImportReviewReport
from .importing import import_project
from .layout import CONFIG_NAME, layout
from .project_models import ProjectImportReport, ToolchainRecord, ToolchainsCatalog
from .repository import cad_dependencies, cad_references, import_source_roots
from .review_overview_evidence import read_receipt, recorded_directory, selected_receipt


def _repository_inputs(root: Path) -> dict[str, str]:
    discovery = settings(root)
    names = (layout(root).discovery, discovery.catalogs.toolchains, CONFIG_NAME)
    return {name: digest(path) for name in names if (path := repo_path(root, name)).is_file()}


def _files(source: Path, preview: ProjectImportReport) -> tuple[ImportReviewFile, ...]:
    rows: list[ImportReviewFile] = []
    for name in sorted(preview.copied_sha256.keys() | preview.excluded.keys()):
        role = (
            "PROJECT"
            if name.endswith(".kicad_pro")
            else "SCHEMATIC"
            if name.endswith(".kicad_sch")
            else "PCB"
            if name.endswith(".kicad_pcb")
            else "LIBRARY"
            if name.endswith((".kicad_sym", ".kicad_mod"))
            or Path(name).name in {"sym-lib-table", "fp-lib-table"}
            else "OTHER"
        )
        included = name in preview.copied_sha256
        rows.append(
            ImportReviewFile(
                path=name,
                role=role,
                disposition="INCLUDED" if included else "EXCLUDED",
                sha256=preview.copied_sha256.get(name),
                reason="" if included else preview.excluded[name],
            )
        )
    for issue in preview.issues:
        if issue.startswith("Missing schematic sheet: "):
            rows.append(
                ImportReviewFile(
                    path=issue.removeprefix("Missing schematic sheet: "),
                    role="SCHEMATIC",
                    disposition="MISSING",
                    reason="Referenced sheet is absent",
                )
            )
    if source.suffix != ".kicad_pro":
        rows.append(
            ImportReviewFile(
                path=source.name,
                role="UNSUPPORTED",
                disposition="UNSUPPORTED",
                reason="Select a native .kicad_pro project for this importer",
            )
        )
    return tuple(rows)


def _dependencies(
    source: Path, preview: ProjectImportReport, toolchain: ToolchainRecord | None
) -> tuple[ImportReviewDependency, ...]:
    if toolchain is None:
        return ()
    parent = source.parent.resolve()
    copied = frozenset(preview.copied_sha256)
    roots = import_source_roots(copied)
    major = toolchain.kicad_version.split(".")[0]
    rows: list[ImportReviewDependency] = []
    for name in sorted(copied):
        path = repo_path(parent, name)
        if path.suffix not in {".kicad_pcb", ".kicad_mod"} and path.name not in {
            "sym-lib-table",
            "fp-lib-table",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        issues = cad_dependencies(parent, path, parent, major, copied, roots, exposed_inputs=copied)
        for reference in cad_references(parent, path, text):
            issue = next(
                (item for item in issues if item.startswith(f"CAD_PATH: {reference.location}:")),
                "",
            )
            if "missing dependency" in issue or "missing embedded model" in issue:
                status = "MISSING"
            elif any(
                marker in issue
                for marker in (
                    "machine-local",
                    "undocumented",
                    "invalid versioned",
                    "case mismatch",
                )
            ):
                status = "NONPORTABLE"
            elif issue:
                status = "UNRESOLVED"
            elif reference.value.startswith("kicad-embed://"):
                status = "EMBEDDED_DECLARED"
            elif reference.value.startswith("${KICAD"):
                status = "PINNED_LIBRARY"
            else:
                status = "PROJECT_LOCAL"
            rows.append(
                ImportReviewDependency(
                    source_location=reference.location,
                    kind="MODEL" if reference.kind == "model" else "LIBRARY",
                    reference=reference.value,
                    status=status,
                    issue=issue,
                )
            )
    return tuple(rows)


def _source_digest(source: Path) -> str | None:
    try:
        content, _ = read_regular_bytes(source, maximum=16 * 1024 * 1024)
        return hashlib.sha256(content).hexdigest()
    except (OSError, ValueError):
        return None


def _source_path(root: Path, source_project: Path) -> Path:
    """Interpret a relative selected source against the explicit project checkout."""
    return (source_project if source_project.is_absolute() else root / source_project).absolute()


def _snapshot(
    root: Path, source: Path, project_id: str, toolchain_id: str, directory: Path
) -> ImportReviewReport:
    preview = import_project(root, source, project_id, toolchain_id, dry_run=True)
    diagnosis = diagnose_import(root, source, project_id, toolchain_id)
    catalog = settings(root).catalogs.toolchains
    records = read_model(repo_path(root, catalog), ToolchainsCatalog)
    toolchain = next((item for item in records.toolchains if item.id == toolchain_id), None)
    files = _files(source, preview)
    dependencies = _dependencies(source, preview, toolchain)
    issues = (
        *preview.issues,
        *(item.observed for item in diagnosis.findings if item.severity == "BLOCKING"),
    )
    return ImportReviewReport(
        status="UNSUPPORTED_FORMAT"
        if source.suffix != ".kicad_pro"
        else "PREVIEW_CLEAR"
        if preview.status == "PASS" and diagnosis.status == "PASS"
        else "NEEDS_WORK",
        project_id=project_id,
        source_project=str(source),
        source_project_sha256=preview.copied_sha256.get(source.name) or _source_digest(source),
        source_kind=source_kind(source) if source.suffix == ".kicad_pro" else None,
        toolchain_id=toolchain_id,
        toolchain=toolchain,
        repository_inputs_sha256=_repository_inputs(root),
        preview=preview,
        diagnosis=diagnosis,
        files=files,
        dependencies=dependencies,
        issues=tuple(dict.fromkeys(issues)),
        output_directory=str(directory),
    )


def build_import_review(
    root: Path,
    source_project: Path,
    project_id: str,
    toolchain_id: str,
    output: Path | None = None,
) -> ImportReviewReport:
    """Save one offline preview; no source or project manifest is edited."""
    root = root.resolve()
    source = _source_path(root, source_project)
    target = output or Path("build/import-review") / f"{project_id}-{uuid4().hex[:12]}"
    directory = repo_path(
        root, target.relative_to(root).as_posix() if target.is_absolute() else target.as_posix()
    )
    report = _snapshot(root, source, project_id, toolchain_id, directory)
    if _snapshot(root, source, project_id, toolchain_id, directory) != report:
        raise ValueError("Import source or repository configuration changed during review")
    directory = receipt_directory(root, project_id, target)
    (directory / "index.html").write_text(render_import_review(report), encoding="utf-8")
    if _snapshot(root, source, project_id, toolchain_id, directory) != report:
        raise ValueError("Import source or repository configuration changed during review")
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "review.json", report)
    return report


def apply_reviewed_import(
    root: Path,
    source_project: Path,
    project_id: str,
    toolchain_id: str,
    review_receipt: Path,
) -> ProjectImportReport:
    """Apply only the reviewed import selection and exact copied-source inventory."""
    root = root.resolve()
    source = _source_path(root, source_project)
    path = selected_receipt(root, review_receipt, "review.json")
    saved, _ = read_receipt(path, ImportReviewReport)
    if not recorded_directory(root, saved.output_directory, path.parent):
        raise ValueError("Import review identifies a different output directory")
    if (
        saved.status != "PREVIEW_CLEAR"
        or saved.project_id != project_id
        or saved.source_project != str(source)
        or saved.toolchain_id != toolchain_id
        or not saved.preview.dry_run
        or saved.preview.status != "PASS"
    ):
        raise ValueError("Import review does not match this clear source and project selection")
    if (
        saved.artifacts_sha256.get("index.html") is None
        or digest(path.parent / "index.html") != saved.artifacts_sha256["index.html"]
        or _repository_inputs(root) != dict(saved.repository_inputs_sha256)
    ):
        raise ValueError("Import review page or project configuration changed; preview again")
    current = import_project(root, source, project_id, toolchain_id, dry_run=True)
    if current != saved.preview:
        raise ValueError("Import source changed since the saved review; preview again")
    return import_project(
        root,
        source,
        project_id,
        toolchain_id,
        expected_preview=saved.preview,
    )
