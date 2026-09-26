"""Read-only island repair aid when global project discovery is not trustworthy."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from .contracts import read_model, repo_path
from .diagnostic_journal import DiagnosticJournal
from .diagnostics import finding, quote_argument, repository_guidance
from .discovery import load_config, manifest_paths
from .layout import layout, within_roots, workflow_guide
from .models import DiagnosticFinding, LocalRescueReport, ProjectManifest
from .repository import cad_dependencies

DIAGNOSTICS_GUIDE = "docs/workflow/DIAGNOSTICS.md"
OMITTED = (
    "Other project manifests and complete registry uniqueness/discovery",
    "Shared catalog relationships, products, and dependent projects",
    "Project Python tests, global quality tools, and native KiCad checks",
    "Hosted CI, engineering acceptance, and release readiness",
)


def selected_manifest(root: Path, project_id: str) -> Path:
    """Find a configured island without parsing potentially malformed peer manifests."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must be one portable directory name")
    candidates = list(manifest_paths(root, project_id))
    if not candidates:
        raise ValueError(f"No project.json for {project_id!r} in configured project roots")
    if len(candidates) != 1:
        raise ValueError(
            "The selected ID is ambiguous across configured roots: "
            + ", ".join(path.relative_to(root).as_posix() for path in candidates)
        )
    return candidates[0]


def selected_findings(
    root: Path,
    project_id: str,
    path: Path,
    journal: DiagnosticJournal,
) -> list[DiagnosticFinding]:
    """Inspect selected manifest, contract, source inventory and CAD references only."""
    findings: list[DiagnosticFinding] = []
    relative = path.relative_to(root).as_posix()
    try:
        manifest = read_model(path, ProjectManifest)
        journal.save_model("selected-manifest", manifest)
    except (OSError, ValueError) as exc:
        return [
            finding(
                "BLOCKING",
                "SELECTED_MANIFEST",
                relative,
                str(exc),
                "Repair this board's project.json syntax or typed fields, then rerun rescue.",
                DIAGNOSTICS_GUIDE,
            )
        ]
    if manifest.id != project_id:
        return [
            finding(
                "BLOCKING",
                "SELECTED_IDENTITY",
                relative,
                f"Manifest ID {manifest.id!r} differs from selected directory {project_id!r}.",
                "Make the folder and manifest ID agree without renaming an unrelated board.",
                DIAGNOSTICS_GUIDE,
            )
        ]
    try:
        config = load_config(root, path)
        journal.save_model("selected-config", config)
    except (OSError, ValueError) as exc:
        return [
            finding(
                "BLOCKING",
                "SELECTED_CONFIG",
                relative,
                str(exc),
                "Repair this board's declared toolchain, checks contract, or local path; "
                "do not change another project's manifest to make rescue pass.",
                DIAGNOSTICS_GUIDE,
            )
        ]

    design: Path | None = None
    try:
        design = repo_path(root, config.project)
        if design.suffix != ".kicad_pro" or not design.is_file():
            raise ValueError(f"Selected .kicad_pro is missing or misnamed: {config.project}")
    except (OSError, ValueError) as exc:
        findings.append(
            finding(
                "BLOCKING",
                "SELECTED_DESIGN",
                config.project,
                str(exc),
                "Restore the selected saved .kicad_pro or correct this board's project path.",
                DIAGNOSTICS_GUIDE,
            )
        )

    for shared in manifest.shared_source_roots:
        if not within_roots(shared, layout(root).library_roots):
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_SHARED_ROOT",
                    relative,
                    shared,
                    "Shared roots must be named libraries, not another project's private files. "
                    "Repair the declaration and verify library ownership in the normal gate.",
                    "docs/workflow/LIBRARIES.md",
                )
            )
    for name in manifest.shared_inputs:
        if not any(name.startswith(f"{source}/") for source in manifest.shared_source_roots):
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_SHARED_INPUT",
                    relative,
                    name,
                    "A shared input must belong to a declared named library root. Repair the "
                    "inventory, then verify library ownership in the normal gate.",
                    "docs/workflow/LIBRARIES.md",
                )
            )
    for name in (*config.source_roots, *config.required_inputs):
        try:
            repo_path(root, name)
        except ValueError as exc:
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_PATH",
                    relative,
                    f"{name}: {exc}",
                    "Correct the exact portable source path in this board's manifest.",
                    DIAGNOSTICS_GUIDE,
                )
            )
    if any(
        row.code in {"SELECTED_PATH", "SELECTED_SHARED_ROOT", "SELECTED_SHARED_INPUT"}
        for row in findings
    ):
        return findings

    try:
        from ..validate import hashes

        observed = set(hashes(root, config.source_roots))
        expected = set(config.required_inputs)
        for name in sorted(expected - observed):
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_INPUT_MISSING",
                    name,
                    "Declared input is absent from the selected source roots.",
                    "Restore the real input or correct the reviewed inventory; do not make a placeholder.",
                    DIAGNOSTICS_GUIDE,
                )
            )
        for name in sorted(observed - expected):
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_INPUT_UNLISTED",
                    name,
                    "Source file is not listed in this board's required_inputs.",
                    "Classify the file, then inventory authored source or move generated state to build/.",
                    DIAGNOSTICS_GUIDE,
                )
            )
    except (OSError, ValueError) as exc:
        findings.append(
            finding(
                "BLOCKING",
                "SELECTED_INVENTORY",
                relative,
                str(exc),
                "Repair the selected source-root path, missing directory, or linked file; "
                "then rerun this local inspection.",
                DIAGNOSTICS_GUIDE,
            )
        )
        return findings

    if design is None or not design.is_file():
        return findings
    major = config.kicad_version.split(".")[0]
    inventory = frozenset(config.required_inputs)
    roots = frozenset(config.source_roots)
    project_dir = design.parent
    for name in config.required_inputs:
        path = repo_path(root, name)
        if not path.is_file() or not (
            path.suffix in {".kicad_pcb", ".kicad_mod"}
            or path.name in {"sym-lib-table", "fp-lib-table"}
        ):
            continue
        try:
            findings.extend(
                repository_guidance(issue, major)
                for issue in cad_dependencies(
                    root,
                    path,
                    project_dir,
                    major,
                    inventory,
                    roots,
                )
            )
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append(
                finding(
                    "BLOCKING",
                    "SELECTED_CAD_PARSE",
                    name,
                    str(exc),
                    "Repair the named selected CAD source or reference, then rerun rescue.",
                    DIAGNOSTICS_GUIDE,
                )
            )
    return findings


def rescue_project(root: Path, project_id: str, journal: DiagnosticJournal) -> LocalRescueReport:
    """Return a partial repair report; never call the authoritative CI/release gates."""
    root = root.resolve()
    manifest: Path | None = None
    try:
        with journal.stage("selected-island"):
            manifest = selected_manifest(root, project_id)
        with journal.stage("local-read-only-inspection"):
            findings = selected_findings(root, project_id, manifest, journal)
    except (OSError, ValueError) as exc:
        findings = [
            finding(
                "BLOCKING",
                "RESCUE_SELECTION",
                "catalog/projects.json",
                str(exc),
                "Select one direct project island or repair the configured discovery roots. "
                "Do not bypass an unsafe or ambiguous manifest path.",
                DIAGNOSTICS_GUIDE,
            )
        ]
    try:
        findings = [
            row.model_copy(update={"guide": workflow_guide(root, row.guide)}) for row in findings
        ]
    except (OSError, ValueError):
        pass  # Preserve repair guidance even when the layout file is invalid.
    command = (
        "python -B -m kicad_tooling.template diagnose"
        f" --root {quote_argument(str(root))} --project-id {quote_argument(project_id)}"
    )
    return LocalRescueReport(
        project_id=project_id,
        selected_manifest=None if manifest is None else manifest.relative_to(root).as_posix(),
        local_inspection="NEEDS_REPAIR"
        if any(row.severity == "BLOCKING" for row in findings)
        else "CLEAR",
        findings=tuple(findings),
        omitted_checks=OMITTED,
        next_command=command,
        run_directory=str(journal.directory),
    )


def format_rescue(
    result: LocalRescueReport,
    detail: Literal["brief", "full"] = "brief",
) -> str:
    """Show a compact repair queue while stating the global acceptance boundary."""
    lines = [
        f"{result.status}: local rescue for {result.project_id}",
        f"Selected island: {result.selected_manifest or 'not safely selected'}",
        f"Local inspection: {result.local_inspection}",
        "This receipt is not eligible for CI, release, or engineering acceptance.",
        f"{len(result.findings)} local finding(s).",
    ]
    if detail == "full":
        for number, row in enumerate(result.findings, 1):
            lines.extend(
                (
                    f"{number}. [{row.severity}] {row.code} at {row.location}",
                    f"   Observed: {row.observed}",
                    f"   Fix: {row.action}",
                    f"   Guide: {row.guide}",
                )
            )
    else:
        for number, row in enumerate(result.findings[:5], 1):
            lines.extend(
                (
                    f"{number}. [{row.severity}] {row.code} at {row.location}: {row.observed}",
                    f"   Fix: {row.action}",
                )
            )
        if len(result.findings) > 5:
            lines.append(f"... {len(result.findings) - 5} more in diagnosis.json")
    lines.extend(
        (
            "Not checked: " + "; ".join(result.omitted_checks) + ".",
            "After repair, run the normal fail-closed diagnosis and CI gate:",
            f"  {result.next_command}",
            f"Run log: {Path(result.run_directory) / 'events.log'}",
            f"Full findings: {Path(result.run_directory) / 'diagnosis.json'}",
        )
    )
    return "\n".join(lines)
