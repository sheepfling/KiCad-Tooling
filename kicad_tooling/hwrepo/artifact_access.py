"""Repository-scoped generated artifacts and stable regular-file reads.

These checks are shared by local workflows and transport adapters. Project
source and restored files are deliberately outside the artifact read scope.
"""

from __future__ import annotations

from pathlib import Path

from .contracts import file_fingerprint as _file_fingerprint
from .contracts import read_model, repo_path
from .contracts import read_regular_bytes as _read_regular_bytes
from .discovery import manifest_paths
from .layout import layout, within_roots
from .product_models import ProductIndex

file_fingerprint = _file_fingerprint
read_regular_bytes = _read_regular_bytes


def artifact_path(root: Path, value: str) -> Path:
    """Confine generated paths to configured build trees without traversal or links."""
    path = repo_path(root, value)
    parts = path.relative_to(root.resolve()).parts
    boundary: int | None = None
    if parts[0] == "build":
        boundary = 0
    else:
        for index, component in enumerate(parts):
            if component != "build" or index == 0:
                continue
            owner = "/".join(parts[:index])
            if any(path.parent == root.resolve() / owner for path in manifest_paths(root)):
                boundary = index
                break
            if within_roots(owner, layout(root).product_roots):
                products = read_model(repo_path(root, layout(root).products), ProductIndex)
                if any(Path(entry.path).parent.as_posix() == owner for entry in products.products):
                    boundary = index
                    break
    if boundary is None or "restores" in parts[boundary + 1 :]:
        raise ValueError(
            "Artifacts must be under a direct repository/project/product build/; "
            "restored source is not an artifact read scope"
        )
    return path


def artifact_file(root: Path, value: str) -> Path:
    """Require an existing generated artifact file."""
    path = artifact_path(root, value)
    if not path.is_file():
        raise ValueError(f"Select an existing generated artifact file: {value}")
    return path
