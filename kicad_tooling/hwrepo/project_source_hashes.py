"""Hash the project source roots declared for a verification operation."""

from __future__ import annotations

import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from .contracts import repo_path
from .evidence import digest
from .model_primitives import Digest, RepositoryPath
from .source_state_models import SourceHashInventory

ProjectSourceInputState = Literal["MISSING", "UNAVAILABLE", "EVALUATED"]


@dataclass(frozen=True, slots=True)
class ProjectSourceInventoryInput:
    """Operation-local source inventory with explicit availability state."""

    source_roots: tuple[RepositoryPath, ...]
    state: ProjectSourceInputState
    inventory: SourceHashInventory
    issue: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_roots", tuple(self.source_roots))
        object.__setattr__(self, "inventory", MappingProxyType(dict(self.inventory)))
        if self.state == "EVALUATED":
            if self.issue is not None:
                raise ValueError("Evaluated source inventories cannot have an availability issue")
        elif self.inventory or self.issue is None:
            raise ValueError("Unavailable source inventories require an issue and no hashes")


def is_local_kicad_state(path: Path) -> bool:
    return path.suffix == ".kicad_prl" or path.name == "fp-info-cache"


def _source_root_state(root: Path, value: RepositoryPath) -> ProjectSourceInputState:
    try:
        mode = repo_path(root, value).stat().st_mode
    except FileNotFoundError:
        return "MISSING"
    except (OSError, ValueError):
        return "UNAVAILABLE"
    return "EVALUATED" if stat.S_ISDIR(mode) else "UNAVAILABLE"


def hash_project_sources(
    root: Path, source_roots: Sequence[RepositoryPath] | None = None
) -> SourceHashInventory:
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


def capture_project_source_inventory(
    root: Path, source_roots: Sequence[RepositoryPath]
) -> ProjectSourceInventoryInput:
    """Capture exact source membership and hashes while retaining failure state."""
    root = root.resolve()
    roots = tuple(source_roots)
    if not roots or any(not item for item in roots):
        return ProjectSourceInventoryInput(
            roots,
            "UNAVAILABLE",
            {},
            "source_roots must be a non-empty list of relative directories",
        )
    for item in roots:
        state = _source_root_state(root, item)
        if state == "MISSING":
            return ProjectSourceInventoryInput(
                roots, "MISSING", {}, f"Declared source root is missing: {item}"
            )
        if state == "UNAVAILABLE":
            return ProjectSourceInventoryInput(
                roots, "UNAVAILABLE", {}, f"Declared source root is not available: {item}"
            )
    try:
        inventory = hash_project_sources(root, roots)
    except (OSError, ValueError) as exc:
        message = str(exc)
        state: ProjectSourceInputState = (
            "MISSING"
            if any(_source_root_state(root, item) == "MISSING" for item in roots)
            else "UNAVAILABLE"
        )
        return ProjectSourceInventoryInput(roots, state, {}, message)
    return ProjectSourceInventoryInput(roots, "EVALUATED", inventory, None)


def project_source_inventory_issues(
    project_id: str,
    captured: ProjectSourceInventoryInput,
    required_inputs: Sequence[RepositoryPath],
) -> tuple[str, ...]:
    """Report capture failures or source-root/input-contract membership differences."""
    if captured.state != "EVALUATED":
        return (f"project {project_id}: invalid source scope: {captured.issue}",)
    observed = set(captured.inventory)
    required = set(required_inputs)
    if observed == required:
        return ()
    message = (
        f"project {project_id}: input inventory (required_inputs) differs from source_roots: "
        f"{sorted(observed ^ required)}"
    )
    return (message,)


def project_source_inventory_freshness_issues(
    root: Path,
    project_id: str,
    captured: ProjectSourceInventoryInput,
) -> tuple[str, ...]:
    """Require the captured source scope and path-to-digest inventory to stay current."""
    current = capture_project_source_inventory(root, captured.source_roots)
    if current.state != captured.state:
        message = (
            f"project {project_id}: source scope changed state during operation "
            f"({captured.state} to {current.state})"
        )
        return (message,)
    if captured.state == "EVALUATED" and current.inventory != captured.inventory:
        return (f"project {project_id}: source inventory changed during operation",)
    return ()
