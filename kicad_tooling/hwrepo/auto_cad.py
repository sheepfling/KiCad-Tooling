"""Import footprint-authored models automatically, preserving placed board geometry."""
from __future__ import annotations

import difflib
import hashlib
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .cad_assets import (
    MissingFootprintError,
    ResolvedFootprint,
    inventory,
    plan_model_assignment,
    resolve_footprint,
)
from .cad_download import fetch_official_footprint
from .contracts import read_model, repo_path, update_project_manifest_inputs
from .discovery import load_config
from .models import (
    AutoCadAsset,
    AutoCadItem,
    AutoCadPlan,
    AutoCadProvenance,
    AutoCadReport,
    ProjectManifest,
)
from .part_picker import _snapshot, _verify_snapshot  # pyright: ignore[reportPrivateUsage]
from .parts_workflow import local_path, selected_project


@dataclass(frozen=True)
class _Edit:
    path: str
    before: bytes | None
    after: bytes


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _receipt(root: Path, output: Path) -> Path:
    output = local_path(root, output)
    if (not output.is_relative_to(root / "build") or output == root / "build"
            or not output.is_dir() or any(output.iterdir())):
        raise ValueError("CAD automation requires a fresh empty receipt under build/")
    return output


def _resolve(root: Path, project_id: str, footprint_id: str, *, allow_downloads: bool) -> ResolvedFootprint:
    try:
        return resolve_footprint(root, project_id, footprint_id)
    except MissingFootprintError:
        project = selected_project(root, project_id)
        config = load_config(root, project.config)
        library = fetch_official_footprint(repo_path(root, "build/cad-cache"), footprint_id,
                                           config.kicad_version, allow_downloads=allow_downloads)
        return replace(resolve_footprint(root, project_id, footprint_id, library_root=library), official_library=True)


def _build(root: Path, project_id: str, *, allow_downloads: bool) -> tuple[tuple[AutoCadItem, ...], tuple[_Edit, ...]]:
    project = selected_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    board = inventory(root, project_id)
    board_path = board.path
    if not any(board_path.is_relative_to(repo_path(manifest_path.parent, name))
               for name in manifest.source_roots):
        raise ValueError("PCB must belong to a declared project-local source root")
    asset_root = board_path.parent / "cad/auto"
    source = board.source
    proposed: dict[str, bytes] = {}
    items: list[AutoCadItem] = []
    resolved: dict[str, ResolvedFootprint] = {}
    for placed in board.footprints:
        try:
            pair = resolved.get(placed.footprint_id)
            if pair is None:
                pair = _resolve(root, project_id, placed.footprint_id, allow_downloads=allow_downloads)
                resolved[placed.footprint_id] = pair
            if not pair.models:
                raise ValueError("The assigned footprint has no paired 3D model. Select a footprint with CAD or import its vendor bundle.")
            library, member = pair.footprint_id.split(":")
            directory = repo_path(root, (asset_root / library / member).relative_to(root).as_posix())
            references: dict[str, str] = {}
            assets: list[AutoCadAsset] = []
            copied: dict[str, bytes] = {}
            for model in pair.models:
                name = _sha(model.source_bytes)[:16] + "-" + model.source_path.name
                destination = directory / name
                relative = destination.relative_to(root).as_posix()
                references[model.source_model_reference] = "${KIPRJMOD}/" + destination.relative_to(board_path.parent).as_posix()
                copied[relative] = model.source_bytes
                assets.append(AutoCadAsset(source=str(model.source_path), sha256=_sha(model.source_bytes), destination=relative))
            updated = plan_model_assignment(source, placed.reference, pair, references)
            copied[(directory / "source-footprint.txt").relative_to(root).as_posix()] = pair.source_bytes
            provenance = AutoCadProvenance(footprint=pair.footprint_id, source=pair.provenance,
                source_sha256=_sha(pair.source_text.encode("utf-8")), models=tuple(assets))
            provenance_path = repo_path(root, (directory / "provenance.json").relative_to(root).as_posix())
            provenance_bytes = (provenance.model_dump_json(indent=2) + "\n").encode("utf-8")
            if provenance_path.exists():
                recorded = read_model(provenance_path, AutoCadProvenance)
                identity = tuple((item.destination, item.sha256) for item in provenance.models)
                recorded_identity = tuple((item.destination, item.sha256) for item in recorded.models)
                if (recorded.footprint == provenance.footprint
                        and recorded.source_sha256 == provenance.source_sha256
                        and recorded_identity == identity):
                    # Retain historical provenance across machines and moved checkouts.
                    provenance_bytes = provenance_path.read_bytes()
            copied[provenance_path.relative_to(root).as_posix()] = provenance_bytes
            # Installed/downloaded official packages are redistributed with the library license.
            if pair.official_library:
                copied[(directory / "LICENSE.txt").relative_to(root).as_posix()] = (
                    Path(__file__).with_name("kicad_library_license.txt").read_bytes()
                )
            for path, content in copied.items():
                if path in proposed and proposed[path] != content:
                    raise ValueError(f"Conflicting asset destinations: {path}")
            proposed.update(copied)
            items.append(AutoCadItem(reference=placed.reference, footprint=placed.footprint_id,
                status="ALREADY_PRESENT" if updated == source else "READY",
                detail="Pad numbering, positions, sizes and drills match the source footprint; its model transforms are preserved."))
            source = updated
        except (OSError, ValueError) as error:
            items.append(AutoCadItem(reference=placed.reference, footprint=placed.footprint_id,
                                     status="NEEDS_REVIEW", detail=str(error)))
    if source != board.source:
        proposed[board_path.relative_to(root).as_posix()] = source.encode("utf-8")
    if proposed:
        additions: dict[str, set[str]] = {"required_inputs": {Path(path).relative_to(manifest_path.parent.relative_to(root)).as_posix()
                                         for path in proposed}, "shared_inputs": set()}
        before = manifest_path.read_text(encoding="utf-8")
        after = update_project_manifest_inputs(before, additions)
        if after != before:
            proposed[project.config] = after.encode("utf-8")
    edits: list[_Edit] = []
    for name, content in sorted(proposed.items()):
        path = repo_path(root, name)
        before_bytes = path.read_bytes() if path.is_file() else None
        if before_bytes != content:
            # Existing imported assets are immutable. Source PCB/manifest remain editable.
            if before_bytes is not None and path not in {board_path, manifest_path}:
                raise ValueError(f"Imported CAD asset was changed: {name}; retain it and resolve the conflict before importing")
            edits.append(_Edit(name, before_bytes, content))
    return tuple(items), tuple(edits)


def _diff(edits: tuple[_Edit, ...]) -> str:
    chunks: list[str] = []
    for edit in edits:
        if Path(edit.path).suffix in {".kicad_pcb", ".json"}:
            chunks.append("".join(difflib.unified_diff(
                (edit.before or b"").decode("utf-8").splitlines(keepends=True),
                edit.after.decode("utf-8").splitlines(keepends=True),
                fromfile="a/" + edit.path, tofile="b/" + edit.path)))
        else:
            chunks.append(f"Import {edit.path} ({len(edit.after)} bytes; SHA256 {_sha(edit.after)})\n")
    return "".join(chunks)


def _write_edits(root: Path, project_id: str, spec: AutoCadPlan, edits: tuple[_Edit, ...]) -> None:
    expected = dict(spec.preconditions)
    applied: list[_Edit] = []
    with tempfile.TemporaryDirectory(prefix=".auto-cad-", dir=root / "build") as temporary:
        stage = Path(temporary)
        for index, edit in enumerate(edits):
            path = stage / str(index)
            path.write_bytes(edit.after)
            target = repo_path(root, edit.path)
            if target.exists():
                path.chmod(target.stat().st_mode)
        try:
            for index, edit in enumerate(edits):
                _verify_snapshot(root, project_id, expected)
                target = repo_path(root, edit.path)
                current = target.read_bytes() if target.exists() else None
                if current != edit.before:
                    raise ValueError(f"{edit.path} changed since preview")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / str(index), target)
                applied.append(edit)
                expected[edit.path] = _sha(edit.after)
            _verify_snapshot(root, project_id, expected)
        except (OSError, ValueError) as error:
            failures: list[str] = []
            for index, edit in enumerate(reversed(applied)):
                try:
                    target = repo_path(root, edit.path)
                    if not target.is_file() or _sha(target.read_bytes()) != _sha(edit.after):
                        raise ValueError(f"{edit.path} changed externally; retained for recovery")
                    if edit.before is None:
                        target.unlink()
                    else:
                        saved = stage / f"restore-{index}"
                        saved.write_bytes(edit.before)
                        saved.chmod(target.stat().st_mode)
                        os.replace(saved, target)
                except (OSError, ValueError) as failure:
                    failures.append(str(failure))
            if failures:
                raise ValueError(f"Import failed: {error}. Recovery needs review: {'; '.join(failures)}") from error
            raise


def _run(root: Path, project_id: str, output: Path, locked: Path | None, *, allow_downloads: bool) -> AutoCadReport:
    root = root.resolve()
    output = _receipt(root, output)
    try:
        before = _snapshot(root, project_id)
        spec = None if locked is None else read_model(local_path(root, locked), AutoCadPlan)
        if spec is not None:
            if spec.project_id != project_id:
                raise ValueError("CAD plan belongs to a different project")
            _verify_snapshot(root, project_id, spec.preconditions)
        items, edits = _build(root, project_id, allow_downloads=allow_downloads)
        _verify_snapshot(root, project_id, before)
        hashes = {edit.path: _sha(edit.after) for edit in edits}
        if spec is not None and hashes != spec.after_hashes:
            raise ValueError("CAD assets or plan changed since preview; scan and review again")
        locked_path = output / "cad-plan.json"
        plan_record = AutoCadPlan(project_id=project_id, preconditions=before, after_hashes=hashes)
        locked_path.write_text(plan_record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        diff = _diff(edits)
        (output / "cad.diff").write_text(diff, encoding="utf-8")
        issues = tuple(f"{item.reference}: {item.detail}" for item in items if item.status == "NEEDS_REVIEW")
        if spec is not None:
            _write_edits(root, project_id, spec, edits)
        status = ("APPLIED" if spec is not None else "PLAN") if edits else "NEEDS_REVIEW" if issues else "PLAN"
        report = AutoCadReport(project_id=project_id, status=status, items=items,
            files=tuple(hashes), issues=issues, plan_path=str(locked_path) if edits else None,
            receipt_directory=str(output), diff=diff)
    except (OSError, ValueError) as error:
        report = AutoCadReport(project_id=project_id, status="BLOCKED", issues=(str(error),), receipt_directory=str(output))
    (output / "cad-report.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def plan(root: Path, project_id: str, output: Path, *, allow_downloads: bool = True) -> AutoCadReport:
    """Resolve pairs and show a source-bound preview; no project inputs are changed."""
    return _run(root, project_id, output, None, allow_downloads=allow_downloads)


def apply(root: Path, project_id: str, plan_path: Path, output: Path, *, allow_downloads: bool = True) -> AutoCadReport:
    """Recalculate a reviewed plan and transactionally import its unchanged bytes."""
    return _run(root, project_id, output, plan_path, allow_downloads=allow_downloads)
