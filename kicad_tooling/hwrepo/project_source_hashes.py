"""Hash the project source roots declared for a verification operation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .model_primitives import Digest, RepositoryPath


def is_local_kicad_state(path: Path) -> bool:
    return path.suffix == ".kicad_prl" or path.name == "fp-info-cache"


def hash_project_sources(
    root: Path, source_roots: Sequence[RepositoryPath] | None = None
) -> dict[RepositoryPath, Digest]:
    """Return exact SHA-256 evidence for declared roots, rejecting unsafe scope."""
    root = root.resolve()
    roots = ("projects",) if source_roots is None else tuple(source_roots)
    if not roots or any(not item for item in roots):
        raise ValueError("source_roots must be a non-empty list of relative directories")
    result: dict[RepositoryPath, Digest] = {}
    for item in roots:
        directory = repo_path(root, item)
        if not directory.is_dir():
            raise ValueError(f"Declared source root is missing: {item}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Source symlink is not allowed: {path}")
            if path.is_file() and not is_local_kicad_state(path):
                # Git manifests use forward-slash repository paths on every OS.
                key: RepositoryPath = path.relative_to(root).as_posix()
                repo_path(root, key)  # Also reject linked/junction ancestors.
                if key in result:
                    raise ValueError(f"Overlapping source roots include: {key}")
                result[key] = digest(path)
    return result
