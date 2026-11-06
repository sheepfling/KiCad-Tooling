"""Resolve reviewed 3D model files into manifest and KiCad path references."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, NamedTuple

from .contracts import relative_path_from, repo_path
from .model_primitives import RepositoryPath
from .project_models import ProjectManifest

AUTHORABLE_SUFFIXES = frozenset({".step", ".stp", ".igs", ".iges", ".wrl"})


class ModelSourceResolution(NamedTuple):
    """Resolved model bytes and their exact manifest/reference projections."""

    model_path: Path
    manifest_field: Literal["required_inputs", "shared_inputs"]
    manifest_input_path: RepositoryPath
    kicad_reference: str


def resolve_model_source_path(
    root: Path, manifest_dir: Path, board_dir: Path, manifest: ProjectManifest, name: str
) -> ModelSourceResolution:
    """Resolve one authored model path inside exactly one declared source root."""
    if Path(name).suffix.casefold() not in AUTHORABLE_SUFFIXES:
        raise ValueError(
            f"{name}: assign STEP/STP/IGS/IGES/WRL source; IDF and exports are not viewable model inputs"
        )
    if "$" in name:
        raise ValueError(f"{name}: model filenames must not contain KiCad variable syntax")
    path = repo_path(root, name)
    if not path.is_file():
        raise ValueError(f"{name}: reviewed model file is missing")
    local_roots = tuple(repo_path(manifest_dir, item) for item in manifest.source_roots)
    shared_roots = tuple(repo_path(root, item) for item in manifest.shared_source_roots)
    local = any(path.is_relative_to(source) for source in local_roots)
    shared = any(path.is_relative_to(source) for source in shared_roots)
    if local == shared:
        raise ValueError(
            f"{name}: model must belong to exactly one declared project-local or shared source root"
        )
    inventory_field = "required_inputs" if local else "shared_inputs"
    inventory_name: RepositoryPath = path.relative_to(manifest_dir).as_posix() if local else name
    relative = relative_path_from(path, board_dir).as_posix()
    return ModelSourceResolution(
        model_path=path,
        manifest_field=inventory_field,
        manifest_input_path=inventory_name,
        kicad_reference="${KIPRJMOD}/" + relative,
    )
