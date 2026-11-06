"""Admit and recheck the authored sources used by part selection and CAD plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .evidence import digest
from .layout import CONFIG_NAME, layout
from .model_population import validate_shared_model_roots
from .model_population_sources import (
    ModelSourceResolution,
    resolve_model_source_path,
)
from .model_primitives import Digest, Identifier, RepositoryPath
from .part_catalog_models import PartRecord, PartsCatalog, PartStatus
from .parts_workflow import preferences_path, selected_project
from .project_models import ProjectManifest
from .project_source_hashes import hash_project_sources
from .purchasing import is_placeholder_purchase_identity, safe_spreadsheet_cell
from .source_state_models import SourcePreconditionInventory


@dataclass(frozen=True, slots=True)
class PartCadSourceSnapshot:
    """Immutable source preconditions bound to one selected project."""

    project_id: Identifier
    preconditions: SourcePreconditionInventory

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "preconditions",
            MappingProxyType(dict(sorted(self.preconditions.items()))),
        )


def read_parts_catalog(root: Path) -> PartsCatalog:
    """Read the unique-ID parts catalog used by the picker and CAD selectors."""
    registry = load_registry(root)
    catalog = read_model(repo_path(root, registry.catalogs.parts), PartsCatalog)
    if len({part.id for part in catalog.parts}) != len(catalog.parts):
        raise ValueError(
            "Parts catalog repeats PART_IDs; repair duplicate records before selecting"
        )
    return catalog


def part_candidate_problem(part: PartRecord) -> str | None:
    """Explain why a catalog entry is not eligible for reviewed CAD selection."""
    if part.cad is None:
        return "No reviewed CAD binding is recorded."
    if part.status != PartStatus.APPROVED:
        return "Catalog part is training or unapproved."
    if is_placeholder_purchase_identity(part.manufacturer) or is_placeholder_purchase_identity(
        part.mpn
    ):
        return "Catalog manufacturer or MPN is a placeholder."
    if part.cad.digikey_sku is not None and is_placeholder_purchase_identity(part.cad.digikey_sku):
        return "Catalog DigiKey SKU is a placeholder."
    try:
        safe_spreadsheet_cell(part.manufacturer)
        safe_spreadsheet_cell(part.mpn)
        if part.cad.digikey_sku is not None:
            safe_spreadsheet_cell(part.cad.digikey_sku)
    except ValueError as error:
        return str(error)
    return None


def resolve_part_cad_model(
    root: Path, project_id: Identifier, part: PartRecord
) -> ModelSourceResolution:
    """Resolve the reviewed model and its manifest input slot for one catalog part."""
    project = selected_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    if part.cad is None:
        raise ValueError(f"{part.id}: reviewed CAD metadata is missing")
    validate_shared_model_roots(root, load_registry(root), manifest)
    return resolve_model_source_path(
        root,
        manifest_path.parent,
        repo_path(root, project.project).parent,
        manifest,
        part.cad.model,
    )


def capture_part_cad_source_snapshot(root: Path, project_id: Identifier) -> PartCadSourceSnapshot:
    """Capture project, policy, and eligible model sources, including absent inputs."""
    root = root.resolve()
    registry = load_registry(root)
    project = selected_project(root, project_id)
    config = load_config(root, project.config)
    result: dict[RepositoryPath, Digest | None] = dict(
        hash_project_sources(root, config.source_roots)
    )
    manifest = read_model(repo_path(root, project.config), ProjectManifest)
    names: set[RepositoryPath] = {
        layout(root).discovery,
        registry.catalogs.parts,
        registry.catalogs.libraries,
        registry.catalogs.toolchains,
        registry.catalogs.interfaces,
        registry.catalogs.release_policies,
        project.config,
        (Path(project.config).parent / manifest.checks).as_posix(),
        CONFIG_NAME,
    }
    # Shared model review consumes every registered project manifest.
    names.update(record.config for record in registry.projects)
    names.add(preferences_path(root, project_id, None).relative_to(root).as_posix())
    for name in sorted(names):
        path = repo_path(root, name)
        result[name] = digest(path) if path.is_file() else None

    # Candidate model assets are part of the selection contract and already
    # belong to one of the declared source roots.
    for part in read_parts_catalog(root).parts:
        if part_candidate_problem(part) is not None:
            continue
        try:
            path, _, _, _ = resolve_part_cad_model(root, project_id, part)
        except ValueError:
            continue
        result[path.relative_to(root).as_posix()] = digest(path)
    return PartCadSourceSnapshot(project_id=project_id, preconditions=result)


def require_part_cad_source_snapshot_current(
    root: Path,
    project_id: Identifier,
    expected: PartCadSourceSnapshot,
) -> None:
    """Reject cross-project, stale, or incomplete preconditions before CAD edits."""
    if expected.project_id != project_id:
        raise ValueError("CAD source snapshot belongs to another project")
    current = capture_part_cad_source_snapshot(root, project_id)
    if current.preconditions == expected.preconditions:
        return
    changed = sorted(
        name
        for name in set(current.preconditions) | set(expected.preconditions)
        if name not in current.preconditions
        or name not in expected.preconditions
        or current.preconditions.get(name) != expected.preconditions.get(name)
    )
    raise ValueError(
        "Source or selection inputs changed, or preconditions are incomplete: "
        + ", ".join(changed[:8])
        + ". Create and review a fresh selection."
    )


def require_part_cad_preconditions_current(
    root: Path,
    project_id: Identifier,
    preconditions: SourcePreconditionInventory,
) -> None:
    """Validate a persisted plan's map using the project-bound snapshot contract."""
    require_part_cad_source_snapshot_current(
        root,
        project_id,
        part_cad_snapshot_from_preconditions(project_id, preconditions),
    )


def part_cad_snapshot_from_preconditions(
    project_id: Identifier,
    preconditions: Mapping[RepositoryPath, Digest | None],
) -> PartCadSourceSnapshot:
    """Bind a persisted plan's legacy map fields to the internal snapshot contract."""
    return PartCadSourceSnapshot(project_id=project_id, preconditions=preconditions)
