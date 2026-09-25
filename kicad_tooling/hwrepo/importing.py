"""Import an existing native project, preserving local names and recording omissions."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

from .contracts import repo_path, write_model
from .markdown import imported_project_readme, write_markdown
from .models import ComponentIdentity, ProjectImportReport, ProjectKind
from .repository import ephemeral, generated_artifact, unmanaged_artifact
from .scaffold import prepare_manifest, write_scaffold


def schematic_files(source: Path, schematic: Path) -> set[Path]:
    """Follow native Sheetfile properties without loading or executing project code."""
    pending = [schematic]
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        path = repo_path(source, path.relative_to(source).as_posix())
        if not path.is_file():
            raise ValueError(f"Missing schematic sheet: {path.relative_to(source)}")
        visited.add(path)
        for match in re.finditer(r'\(property\s+"Sheetfile"\s+"([^"\n]+)"',
                                 path.read_text(encoding="utf-8")):
            name = match.group(1).replace("${KIPRJMOD}/", "")
            if "$" in name:
                raise ValueError(f"Resolve the schematic sheet variable before import: {name}")
            # KiCad Sheetfile is relative to its containing sheet, except KIPRJMOD.
            parent = source if match.group(1).startswith("${KIPRJMOD}/") else path.parent
            normalized = Path(os.path.abspath(parent / name))
            if not normalized.is_relative_to(source):
                raise ValueError(
                    f"Schematic sheet {match.group(1)!r} in {path.relative_to(source)} "
                    "resolves outside the selected project directory; relocate the sheet "
                    "and update Sheetfile before import"
                )
            pending.append(repo_path(source, normalized.relative_to(source).as_posix()))
    return visited


def import_project(root: Path, source_project: Path, project_id: str,
                   toolchain_id: str, dry_run: bool = False) -> ProjectImportReport:
    """Copy one project atomically; never modify the source or generate test truth."""
    root = root.resolve()
    stage: Path | None = None
    copied: dict[str, str] = {}
    excluded: dict[str, str] = {}
    try:
        source = source_project.parent.resolve()
        project = repo_path(source, source_project.name)
        if project.suffix != ".kicad_pro" or not project.is_file():
            raise ValueError("Select an existing .kicad_pro file, not a directory")
        schematic = project.with_suffix(".kicad_sch")
        pcb = project.with_suffix(".kicad_pcb")
        if schematic.is_file():
            kind = ProjectKind.PCB if pcb.is_file() else ProjectKind.SCHEMATIC
        elif pcb.is_file():
            kind = ProjectKind.PCB_ONLY
        else:
            raise ValueError("A matching .kicad_sch or .kicad_pcb source is required")
        manifest = prepare_manifest(root, project_id, kind, toolchain_id)
        destination = repo_path(root, f"projects/{manifest.id}")
        if source == root or source in destination.parents or destination in source.parents:
            raise ValueError("Source and destination directories must not overlap")
        sheets: set[Path] = set()
        if schematic.is_file():
            sheets = schematic_files(source, schematic)
        nested = {path.parent for path in source.rglob("*.kicad_pro") if path.parent != source}
        seen: set[str] = set()
        for path in sorted(source.rglob("*")):
            name = path.relative_to(source).as_posix()
            if ".git" in path.relative_to(source).parts or ephemeral(name):
                if path.is_file():
                    excluded[name] = "local state or build output"
                continue
            if any(folder == path or folder in path.parents for folder in nested):
                if path.is_file():
                    excluded[name] = "separate nested project; import independently"
                continue
            if path.is_symlink():
                raise ValueError(f"Linked source path is not portable: {name}")
            repo_path(source, name)
            if name.casefold() in seen:
                raise ValueError(f"Case-colliding source path: {name}")
            seen.add(name.casefold())
            if not path.is_file():
                continue
            reason = None
            if generated_artifact(name):
                reason = "generated export"
            elif unmanaged_artifact(name):
                reason = "artifact restricted by repository hygiene; review separately"
            elif path.suffix in {".kicad_pro", ".kicad_pcb"} and path.stem != project.stem:
                reason = "separate sibling project; import independently"
            elif path.suffix == ".kicad_sch" and path not in sheets:
                reason = "schematic outside the selected hierarchy"
            if reason:
                excluded[name] = reason
            else:
                copied[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        required: set[str] = {
            project.name,
            *(path.relative_to(source).as_posix() for path in sheets),
        }
        if kind is ProjectKind.PCB_ONLY:
            required.add(pcb.name)
        if not required.issubset(copied):
            raise ValueError(f"Required design sources were excluded: {sorted(required - set(copied))}")
        next_step = (
            f"Review board dependencies and DRC/layout expectations, then run python -B -m kicad_tooling.verify --project {manifest.id}. "
            "Add an authoritative schematic and migrate to pcb before product or manufacturing work."
            if kind is ProjectKind.PCB_ONLY
            else f"Review dependencies, populate independent test expectations, then run python -B -m kicad_tooling.verify --project {manifest.id}. "
            "Import does not approve the design."
        )
        report = ProjectImportReport(
            status="PASS",
            directory=f"projects/{manifest.id}",
            source_project=project.name,
            dry_run=dry_run,
            copied_sha256=copied,
            excluded=excluded,
            next_step=next_step,
        )
        if dry_run:
            return report
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".import-project-", dir=destination.parent))
        manifest = manifest.model_copy(update={
            "project": f"kicad/{project.name}",
            "required_inputs": tuple(f"kicad/{name}" for name in copied),
            # Imported designs have not yet been assigned the team's part IDs.
            "component_identity": ComponentIdentity(required=False, part_ids=()),
        })
        write_scaffold(root, stage, manifest)
        for name, digest in copied.items():
            target = stage / "kicad" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_path(source, name), target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Source changed during import: {name}")
        write_model(stage / "docs/import.json", report)
        upstream_docs = sorted(name for name in copied if name.lower().endswith(".md"))
        write_markdown(
            stage / "README.md",
            imported_project_readme(manifest.id, manifest.project, upstream_docs, manifest.kind),
        )
        os.rename(stage, destination)
        stage = None
        return report
    except (OSError, ValueError) as exc:
        return ProjectImportReport(status="FAIL", directory=f"projects/{project_id}",
            source_project=source_project.name, dry_run=dry_run, copied_sha256=copied,
            excluded=excluded, issues=(str(exc),))
    finally:
        if stage is not None:
            shutil.rmtree(stage)
