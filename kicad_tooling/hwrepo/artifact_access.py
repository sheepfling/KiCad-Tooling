"""Repository-scoped generated artifacts and stable regular-file reads.

These checks are shared by local workflows and transport adapters. Project
source and restored files are deliberately outside the artifact read scope.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import manifest_paths
from .layout import layout, within_roots
from .models import ProductIndex


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


def file_fingerprint(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def read_regular_bytes(path: Path, maximum: int | None = None) -> tuple[bytes, os.stat_result]:
    """Read a stable regular file without following a final-component symlink."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Select a regular file without symlinks")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Select a regular file")
        if maximum is not None and before.st_size > maximum:
            raise ValueError(f"File exceeds the {maximum}-byte limit")
        data = stream.read() if maximum is None else stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if file_fingerprint(before) != file_fingerprint(after):
            raise ValueError("File changed while reading; retry from fresh metadata")
        if maximum is not None and len(data) > maximum:
            raise ValueError(f"File exceeds the {maximum}-byte limit")
    return data, after
