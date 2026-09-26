"""Choose reviewed catalog parts, preview source edits, then apply a locked plan."""
from __future__ import annotations

import difflib
import hashlib
import os
import shlex
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from ..validate import hashes
from .contract_coach import NetlistRunner, capture, inspect_summary, project_context
from .contracts import read_model, repo_path, update_project_manifest_parts
from .discovery import load_config, load_registry
from .evidence import digest
from .layout import CONFIG_NAME, layout
from .model_population import (
    _model_path,  # pyright: ignore[reportPrivateUsage]
    _require_shared_consumer_inventory,  # pyright: ignore[reportPrivateUsage]
    _validate_shared_roots,  # pyright: ignore[reportPrivateUsage]
)
from .models import (
    PartCadComponent,
    PartPickerItem,
    PartPickerReport,
    PartRecord,
    PartsCatalog,
    PartSelectionAssignment,
    PartSelectionMap,
    PartSelectionReport,
    PartSourceEdit,
    PartStatus,
    PcbValidationContract,
    ProjectManifest,
    PurchasingPreferences,
    SchematicValidationContract,
)
from .part_cad import preview_cad, read_cad_components
from .parts_workflow import local_path, preferences_path, selected_project
from .purchasing import (
    _PLACEHOLDER,  # pyright: ignore[reportPrivateUsage]
    _safe_cell,  # pyright: ignore[reportPrivateUsage]
    read_components,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _receipt(root: Path, output: Path) -> Path:
    output = local_path(root, output)
    if (not output.is_relative_to(root / "build") or output == root / "build"
            or not output.is_dir() or any(output.iterdir())):
        raise ValueError("Part picker requires a new empty receipt directory below ignored build/")
    return output


def _catalog(root: Path) -> PartsCatalog:
    registry = load_registry(root)
    catalog = read_model(repo_path(root, registry.catalogs.parts), PartsCatalog)
    if len({part.id for part in catalog.parts}) != len(catalog.parts):
        raise ValueError("Parts catalog repeats PART_IDs; repair duplicate records before selecting")
    return catalog


def _candidate_problem(part: PartRecord) -> str | None:
    if part.cad is None:
        return "No reviewed CAD binding is recorded."
    if part.status != PartStatus.APPROVED:
        return "Catalog part is training or unapproved."
    if _PLACEHOLDER.search(part.manufacturer) or _PLACEHOLDER.search(part.mpn):
        return "Catalog manufacturer or MPN is a placeholder."
    if part.cad.digikey_sku is not None and _PLACEHOLDER.search(part.cad.digikey_sku):
        return "Catalog DigiKey SKU is a placeholder."
    try:
        _safe_cell(part.manufacturer)
        _safe_cell(part.mpn)
        if part.cad.digikey_sku is not None:
            _safe_cell(part.cad.digikey_sku)
    except ValueError as error:
        return str(error)
    return None


def _model(root: Path, project_id: str, part: PartRecord) -> tuple[Path, str, str, str]:
    project = selected_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    if part.cad is None:
        raise ValueError(f"{part.id}: reviewed CAD metadata is missing")
    _validate_shared_roots(root, load_registry(root), manifest)
    return _model_path(root, manifest_path.parent, repo_path(root, project.project).parent,
                       manifest, part.cad.model)


def _snapshot(root: Path, project_id: str) -> dict[str, str | None]:
    """Bind complete source plus every policy input read by selection, including absence."""
    registry = load_registry(root)
    project = selected_project(root, project_id)
    config = load_config(root, project.config)
    result: dict[str, str | None] = dict(hashes(root, config.source_roots))
    manifest = read_model(repo_path(root, project.config), ProjectManifest)
    names = {layout(root).discovery, registry.catalogs.parts, registry.catalogs.libraries,
             registry.catalogs.toolchains, registry.catalogs.interfaces,
             registry.catalogs.release_policies, project.config,
             (Path(project.config).parent / manifest.checks).as_posix()}
    names.add(CONFIG_NAME)
    # Shared model review reads every consumer manifest, not only the selected one.
    names.update(record.config for record in registry.projects)
    names.add(preferences_path(root, project_id, None).relative_to(root).as_posix())
    for name in sorted(names):
        path = repo_path(root, name)
        result[name] = digest(path) if path.is_file() else None
    # Valid candidate assets must be within declared roots and are already hashed.
    # Explicit indexing documents their role and prevents accidental future omission.
    for part in _catalog(root).parts:
        if _candidate_problem(part) is None:
            try:
                path, _, _, _ = _model(root, project_id, part)
            except ValueError:
                continue
            result[path.relative_to(root).as_posix()] = digest(path)
    return dict(sorted(result.items()))


def _verify_snapshot(root: Path, project_id: str, expected: Mapping[str, str | None]) -> None:
    current = _snapshot(root, project_id)
    if current != dict(expected):
        changed = sorted(name for name in set(current) | set(expected)
                         if name not in current or name not in expected or current.get(name) != expected.get(name))
        raise ValueError("Source or selection inputs changed, or preconditions are incomplete: "
                         + ", ".join(changed[:8]) + ". Create and review a fresh selection.")


def _choices(root: Path, project_id: str, components: tuple[PartCadComponent, ...],
             catalog: PartsCatalog) -> tuple[tuple[PartPickerItem, ...], tuple[PartRecord, ...]]:
    items: list[PartPickerItem] = []
    accepted: dict[str, PartRecord] = {}
    for component in components:
        choices: list[str] = []
        issues: list[str] = []
        if component.dnp or component.exclude_from_bom:
            issues.append("Excluded from this assembly's purchasing; keep the recorded exclusion.")
        else:
            for part in sorted(catalog.parts, key=lambda item: item.id):
                if part.cad is None or (part.cad.symbol_id, part.cad.value) != (component.symbol_id, component.value):
                    continue
                problem = _candidate_problem(part)
                if problem is not None:
                    issues.append(f"{part.id}: {problem}")
                    continue
                try:
                    _, _, _, model_reference = _model(root, project_id, part)
                    preview_cad(root, project_id, {component.reference: part},
                                {component.reference: model_reference})
                except ValueError as error:
                    issues.append(f"{part.id}: {error}")
                    continue
                choices.append(part.id)
                accepted[part.id] = part
            if not choices:
                issues.append("Add an approved real catalog part with a reviewed CAD binding for "
                              f"symbol {component.symbol_id!r} and exact value {component.value!r}; "
                              "include its model source in the project's declared inputs.")
        items.append(PartPickerItem(component=component, choice_ids=tuple(choices), issues=tuple(issues)))
    return tuple(items), tuple(accepted[identifier] for identifier in sorted(accepted))


def create_picker(root: Path, project_id: str, output: Path, runner: NetlistRunner,
                  native_summary: Path | None = None) -> PartPickerReport:
    root = root.resolve()
    evidence = None
    try:
        output = _receipt(root, output)
        before = _snapshot(root, project_id)
        if native_summary is None:
            evidence = capture(root, project_id, output, runner)
            netlist = output / "netlist.xml"
        else:
            summary = native_summary if native_summary.is_absolute() else root / native_summary
            evidence = inspect_summary(root, project_id, summary)
            netlist = (summary if summary.is_dir() else summary.parent) / "netlist.xml"
        if evidence.status != "READY_FOR_REVIEW":
            raise ValueError("; ".join(evidence.issues) + ". Declare reviewed model assets in "
                             "required_inputs/shared_inputs before opening the picker.")
        if digest(netlist) != evidence.netlist_sha256:
            raise ValueError("Native netlist changed after verification; capture a fresh picker")
        components = read_cad_components(root, project_id)
        native = read_components(netlist)
        actual = {component.reference: (component.value, component.footprint, component.part_id,
                  component.dnp, component.exclude_from_bom) for component in components}
        observed = {component.reference: (component.value, component.footprint, component.part_id,
                    component.dnp, component.exclude_from_bom) for component in native}
        if actual != observed:
            raise ValueError("Native component inventory differs from the editable schematic; "
                             "save the current assembly and recapture before selecting")
        items, choices = _choices(root, project_id, components, _catalog(root))
        _verify_snapshot(root, project_id, before)
        if digest(netlist) != evidence.netlist_sha256:
            raise ValueError("Native netlist changed during picker generation")
        if native_summary is not None:
            (output / "netlist.xml").write_bytes(netlist.read_bytes())
            if digest(output / "netlist.xml") != evidence.netlist_sha256:
                raise ValueError("Native netlist changed while saving picker evidence")
        draft = PartSelectionMap(project_id=project_id, preconditions=before)
        (output / "selection-draft.json").write_text(draft.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return PartPickerReport(status="READY" if choices else "NEEDS_CATALOG", project_id=project_id,
                                items=items, choices=choices, selection_template=draft,
                                receipt_dir=str(output), evidence=evidence)
    except (OSError, ValueError, TypeError) as error:
        return PartPickerReport(status="BLOCKED", project_id=project_id, receipt_dir=str(output),
                                evidence=evidence, issues=(str(error),))


def _planned_edits(root: Path, project_id: str, spec: PartSelectionMap) -> tuple[tuple[PartSourceEdit, ...], tuple[str, ...]]:
    if not spec.assignments:
        raise ValueError("Choose at least one compatible catalog part in the picker before previewing")
    project_context(root, project_id)  # Never bypass declared native-source inventory with an edited map.
    catalog = _catalog(root)
    records = {part.id: part for part in catalog.parts}
    components = {component.reference: component for component in read_cad_components(root, project_id)}
    selected: dict[str, PartRecord] = {}
    model_references: dict[str, str] = {}
    additions: dict[str, set[str]] = {"required_inputs": set(), "shared_inputs": set()}
    project = selected_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    for assignment in spec.assignments:
        component = components.get(assignment.reference)
        part = records.get(assignment.part_id)
        if component is None or component.dnp or component.exclude_from_bom:
            raise ValueError(f"{assignment.reference}: selection is not a fitted schematic component")
        if part is None:
            raise ValueError(f"{assignment.reference}: unknown catalog part {assignment.part_id}")
        problem = _candidate_problem(part)
        if problem is not None:
            raise ValueError(f"{assignment.part_id}: {problem}")
        if part.cad is None or (part.cad.symbol_id, part.cad.value) != (component.symbol_id, component.value):
            raise ValueError(f"{assignment.reference}: selected part must preserve the exact symbol and electrical value")
        _, field, name, reference = _model(root, project_id, part)
        additions[field].add(name)
        model_references[assignment.reference] = reference
        selected[assignment.reference] = part
    _require_shared_consumer_inventory(root, load_registry(root), project.config,
                                       manifest, additions["shared_inputs"])
    changes = preview_cad(root, project_id, selected, model_references)
    if changes.issues:
        raise ValueError("; ".join(changes.issues))
    edits = list(changes.edits)
    replaced_ids = {components[reference].part_id for reference, part in selected.items()
                    if components[reference].part_id is not None and components[reference].part_id != part.id}
    remaining_ids = {selected[reference].id if reference in selected else component.part_id
                     for reference, component in components.items()}
    retired_ids = tuple(sorted(identifier for identifier in replaced_ids - remaining_ids
                               if identifier is not None))
    manifest_before = _text(manifest_path)
    manifest_after = update_project_manifest_parts(manifest_before,
        tuple(part.id for part in selected.values()), additions, retired_ids)
    if manifest_before != manifest_after:
        edits.append(PartSourceEdit(path=project.config, before=manifest_before, after=manifest_after))
    prefs_path = preferences_path(root, project_id, None)
    prefs_before = _text(prefs_path) if prefs_path.exists() else None
    prefs = read_model(prefs_path, PurchasingPreferences) if prefs_before is not None else PurchasingPreferences()
    overrides = {identifier: sku for identifier, sku in prefs.digikey_skus.items()
                 if identifier not in retired_ids}
    for part in selected.values():
        if part.cad is not None and part.cad.digikey_sku is not None:
            existing = overrides.get(part.id)
            if existing is not None and existing != part.cad.digikey_sku:
                raise ValueError(f"{part.id}: saved DigiKey SKU conflicts with the reviewed CAD catalog binding; review both records")
            overrides[part.id] = part.cad.digikey_sku
    prefs_after = PurchasingPreferences(boards=prefs.boards, spare_percent=prefs.spare_percent,
        spare_minimum=prefs.spare_minimum, digikey_skus=overrides).model_dump_json(indent=2) + "\n"
    if prefs_before != prefs_after:
        edits.append(PartSourceEdit(path=prefs_path.relative_to(root).as_posix(), before=prefs_before, after=prefs_after))
    paths = [edit.path for edit in edits]
    if len(paths) != len(set(paths)):
        raise ValueError("Selection generated conflicting edits for one source file")
    for edit in edits:
        path = repo_path(root, edit.path)
        current = _text(path) if path.is_file() else None
        if current != edit.before:
            raise ValueError(f"{edit.path}: source changed during preview")
    return tuple(sorted(edits, key=lambda edit: edit.path)), changes.pending_references


def _contract_guidance(root: Path, project_id: str, spec: PartSelectionMap) -> tuple[str, ...]:
    """Point to independent requirements without rewriting them from observations."""
    project = selected_project(root, project_id)
    config = load_config(root, project.config)
    validation = config.validation
    if not isinstance(validation, (PcbValidationContract, SchematicValidationContract)):
        return ()
    catalog = {part.id: part for part in _catalog(root).parts}
    different: list[str] = []
    for assignment in spec.assignments:
        part = catalog[assignment.part_id]
        expected = validation.components.get(assignment.reference)
        if part.cad is not None and (expected is None or
                (expected.part_id, expected.value, expected.footprint) !=
                (part.id, part.cad.value, part.cad.footprint)):
            different.append(assignment.reference)
    if not different:
        return ()
    manifest = read_model(repo_path(root, project.config), ProjectManifest)
    contract = (Path(project.config).parent / manifest.checks).as_posix()
    return ((f"Review independent engineering requirements in {contract} for {', '.join(sorted(different))}: "
            "selected PART_ID or footprint differs from authored expectations. Resolve the requirements "
            "before native verification; this selection does not edit the contract or establish electrical approval."),)


def _apply_edits(root: Path, project_id: str, edits: tuple[PartSourceEdit, ...],
                 preconditions: Mapping[str, str | None]) -> None:
    """Stage all bytes, recheck all inputs for each replacement, roll back on failure."""
    applied: list[PartSourceEdit] = []
    expected = dict(preconditions)
    with tempfile.TemporaryDirectory(prefix=".part-selection-", dir=root / "build") as temporary:
        directory = Path(temporary)
        for index, edit in enumerate(edits):
            staged = directory / str(index)
            staged.write_bytes(edit.after.encode("utf-8"))
            path = repo_path(root, edit.path)
            if path.exists():
                os.chmod(staged, path.stat().st_mode)
        try:
            for index, edit in enumerate(edits):
                _verify_snapshot(root, project_id, expected)
                path = repo_path(root, edit.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(directory / str(index), path)
                applied.append(edit)
                expected[edit.path] = _sha(edit.after)
            _verify_snapshot(root, project_id, expected)
        except (OSError, ValueError) as error:
            rollback_errors: list[str] = []
            for index, edit in enumerate(reversed(applied)):
                path = repo_path(root, edit.path)
                try:
                    if not path.is_file() or digest(path) != _sha(edit.after):
                        raise ValueError(f"{edit.path}: changed externally; retained for manual recovery")
                    if edit.before is None:
                        path.unlink()
                    else:
                        restored = directory / f"rollback-{index}"
                        restored.write_bytes(edit.before.encode("utf-8"))
                        os.chmod(restored, path.stat().st_mode)
                        os.replace(restored, path)
                except (OSError, ValueError) as rollback_error:
                    rollback_errors.append(str(rollback_error))
            if rollback_errors:
                raise ValueError(f"Selection failed: {error}. Rollback needs review: " + "; ".join(rollback_errors)) from error
            raise


def selection(root: Path, project_id: str, map_path: Path, output: Path,
              apply: bool = False) -> PartSelectionReport:
    root = root.resolve()
    edits: tuple[PartSourceEdit, ...] = ()
    pending: tuple[str, ...] = ()
    try:
        output = _receipt(root, output)
        map_path = map_path if map_path.is_absolute() else root / map_path
        spec = read_model(map_path, PartSelectionMap)
        if spec.project_id != project_id:
            raise ValueError("Selection map belongs to a different project")
        if apply and not spec.locked:
            raise ValueError("Apply requires the locked map from a successful source preview")
        _verify_snapshot(root, project_id, spec.preconditions)
        edits, pending = _planned_edits(root, project_id, spec)
        contract_guidance = _contract_guidance(root, project_id, spec)
        after_hashes = {edit.path: _sha(edit.after) for edit in edits}
        if spec.locked and dict(spec.after_hashes) != after_hashes:
            raise ValueError("Locked selection differs from recalculated edits; preview a fresh draft")
        if not spec.locked and spec.after_hashes:
            raise ValueError("A draft selection cannot supply locked after hashes")
        _verify_snapshot(root, project_id, spec.preconditions)
        diffs = "".join("".join(difflib.unified_diff(
            (edit.before or "").splitlines(keepends=True), edit.after.splitlines(keepends=True),
            fromfile=f"a/{edit.path}", tofile=f"b/{edit.path}",
        )) for edit in edits)
        (output / "selection.diff").write_text(diffs, encoding="utf-8")
        locked = PartSelectionMap(project_id=project_id, preconditions=spec.preconditions,
            assignments=spec.assignments, locked=True, after_hashes=after_hashes)
        locked_path = output / "selection-locked.json"
        locked_path.write_text(locked.model_dump_json(indent=2) + "\n", encoding="utf-8")
        status: Literal["PLAN", "APPLIED", "APPLIED_NEEDS_PCB_UPDATE", "BLOCKED"] = "PLAN"
        if apply:
            _apply_edits(root, project_id, edits, spec.preconditions)
            status = "APPLIED_NEEDS_PCB_UPDATE" if pending else "APPLIED"
        commands = ((f"python -B -m kicad_tooling.parts --project {project_id} --sync-models",) if pending else (
            f"python -B -m kicad_tooling.verify --project {project_id} --depth native",
            f"python -B -m kicad_tooling.visualize --project {project_id}",
            f"python -B -m kicad_tooling.parts --project {project_id}",
        )) if apply else (
            f"python -B -m kicad_tooling.parts --project {project_id} --selection {shlex.quote(str(locked_path))} --apply",
        )
        issues = (("Update PCB from Schematic (F8) in KiCad, save, then preview --sync-models for: "
                   + ", ".join(pending),) if pending else ()) + contract_guidance
        return PartSelectionReport(status=status, project_id=project_id, edits=edits,
            pending_references=pending, locked_map=str(locked_path), next_commands=commands,
            issues=issues, receipt_dir=str(output))
    except (OSError, ValueError, TypeError) as error:
        return PartSelectionReport(status="BLOCKED", project_id=project_id, edits=edits,
            pending_references=pending, issues=(str(error),), receipt_dir=str(output))


def resume_selection(root: Path, project_id: str, output: Path) -> PartSelectionReport:
    """Preview model synchronization using only already selected schematic PART_IDs."""
    root = root.resolve()
    try:
        output = _receipt(root, output)
        before = _snapshot(root, project_id)
        parts = {part.id: part for part in _catalog(root).parts}
        assignments = tuple(PartSelectionAssignment(reference=component.reference, part_id=component.part_id)
            for component in read_cad_components(root, project_id)
            if not component.dnp and not component.exclude_from_bom and component.part_id is not None
            and component.part_id in parts and parts[component.part_id].cad is not None)
        if not assignments:
            raise ValueError("No fitted schematic PART_ID has a reviewed CAD binding; choose parts in --picker first")
        spec = PartSelectionMap(project_id=project_id, preconditions=before, assignments=assignments)
        # The map is input to selection, so keep it outside the new empty receipt.
        with tempfile.TemporaryDirectory(prefix=".part-sync-", dir=root / "build") as temporary:
            path = Path(temporary) / "selection.json"
            path.write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
            return selection(root, project_id, path, output)
    except (OSError, ValueError, TypeError) as error:
        return PartSelectionReport(status="BLOCKED", project_id=project_id, issues=(str(error),),
                                   receipt_dir=str(output))
