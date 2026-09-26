"""Read-only inventory and import previews for a directory of KiCad projects."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from .importing import import_project
from .models import ImportInventoryCandidate, ImportInventoryReport, ProjectKind
from .repository import ephemeral


def suggested_id(relative: Path) -> str:
    """Suggest a stable island name without making it authoritative."""
    stem = relative.with_suffix("")
    value = re.sub(r"[^a-z0-9_.-]+", "-", "-".join(stem.parts).lower())
    return value.strip("._-") or "project"


def source_kind(project: Path) -> ProjectKind | None:
    schematic = project.with_suffix(".kicad_sch").is_file()
    pcb = project.with_suffix(".kicad_pcb").is_file()
    if schematic:
        return ProjectKind.PCB if pcb else ProjectKind.SCHEMATIC
    return ProjectKind.PCB_ONLY if pcb else None


def scan_imports(root: Path, source_directory: Path, toolchain_id: str) -> ImportInventoryReport:
    """Preview each candidate through the normal importer; never copy source."""
    source = source_directory.resolve()
    if not source.is_dir():
        return ImportInventoryReport(
            source_directory=str(source),
            status="NEEDS_WORK",
            issues=(f"Source directory does not exist: {source}",),
        )
    candidates: list[ImportInventoryCandidate] = []
    skipped: list[str] = []
    issues: list[str] = []
    seen_ids: dict[str, str] = {}
    for path in sorted(source.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.suffix.casefold() != ".kicad_pro":
            continue
        relative = path.relative_to(source)
        if ".git" in relative.parts or ephemeral(relative.as_posix()):
            skipped.append(relative.as_posix())
            continue
        project_id = suggested_id(relative)
        previous = seen_ids.get(project_id.casefold())
        if previous is not None:
            issues.append(f"Suggested project ID {project_id} collides: {previous} and {relative}")
        else:
            seen_ids[project_id.casefold()] = relative.as_posix()
        preview = import_project(root, path, project_id, toolchain_id, dry_run=True)
        candidates.append(
            ImportInventoryCandidate(
                source_project=str(path),
                suggested_project_id=project_id,
                kind=source_kind(path),
                preview=preview,
                next_command=(
                    "python -B -m kicad_tooling.template diagnose "
                    f"--source {shlex.quote(str(path))} "
                    f"--project-id {project_id} --toolchain {toolchain_id} --format text"
                ),
            )
        )
    if not candidates:
        issues.append("No .kicad_pro candidates were found outside local-state directories")
    return ImportInventoryReport(
        source_directory=str(source),
        status="PASS"
        if candidates
        and not issues
        and all(candidate.preview.status == "PASS" for candidate in candidates)
        else "NEEDS_WORK",
        candidates=tuple(candidates),
        skipped_local_state=tuple(skipped),
        issues=tuple(issues),
    )


def format_import_inventory(report: ImportInventoryReport) -> str:
    lines = [
        f"Import inventory: {report.status}; {len(report.candidates)} candidate(s)",
        f"Source: {report.source_directory}",
    ]
    for candidate in report.candidates:
        preview = candidate.preview
        kind = candidate.kind.value if candidate.kind is not None else "undetermined"
        lines.append(f"  {candidate.source_project}")
        lines.append(
            f"    {kind}; suggested ID: {candidate.suggested_project_id}; "
            f"preview: {preview.status}; copied: {len(preview.copied_sha256)}; "
            f"excluded: {len(preview.excluded)}"
        )
        lines.extend(f"    Issue: {issue}" for issue in preview.issues)
        if preview.status == "PASS":
            lines.append(f"    Next: {candidate.next_command}")
    lines.extend(f"Issue: {issue}" for issue in report.issues)
    if report.skipped_local_state:
        lines.append(
            f"Skipped {len(report.skipped_local_state)} local-state candidate(s); "
            "see JSON for paths"
        )
    lines.append(f"Next: {report.next_step}")
    return "\n".join(lines)
