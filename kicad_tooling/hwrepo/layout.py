"""Declarative repository adapters; the template layout remains the default."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from .contracts import parse_model_text, read_regular_bytes, repo_path, repo_path_is_within
from .model_primitives import Digest, RepositoryPath, StrictModel

CONFIG_NAME = "kicad-tooling.toml"
RESERVED_DIRECTORIES = frozenset({"build", "generated", "__pycache__", "releases", "restores"})


def default_project_root() -> Path:
    """Use the caller's checkout as the CLI default when ``--root`` is omitted."""
    return Path.cwd()


class RepositoryLayout(StrictModel):
    discovery: RepositoryPath = "catalog/projects.json"
    products: RepositoryPath = "catalog/products.json"
    team_policy: RepositoryPath = "catalog/team-policy.json"
    templates: RepositoryPath = "templates"
    workflow_docs: RepositoryPath = "docs/workflow"
    new_project_root: RepositoryPath = "projects"
    product_roots: tuple[RepositoryPath, ...] = ("products", "examples/products")
    library_roots: tuple[RepositoryPath, ...] = ("libraries", "examples/libraries")


class ToolingConfiguration(StrictModel):
    schema_version: Literal["1"] = "1"
    layout: RepositoryLayout = Field(default_factory=RepositoryLayout)


@dataclass(frozen=True, slots=True)
class RepositoryLayoutSourceIdentity:
    """Identify authored adapter bytes or the explicit built-in default."""

    state: Literal["AUTHORED", "DEFAULTED"]
    path: RepositoryPath
    sha256: Digest | None

    def __post_init__(self) -> None:
        if self.state not in {"AUTHORED", "DEFAULTED"}:
            raise ValueError("Repository layout source state must be AUTHORED or DEFAULTED")
        if self.path != CONFIG_NAME:
            raise ValueError(f"Repository layout source path must be {CONFIG_NAME}")
        if self.state == "AUTHORED" and self.sha256 is None:
            raise ValueError("Authored repository layout requires a source digest")
        if self.state == "DEFAULTED" and self.sha256 is not None:
            raise ValueError("Defaulted repository layout cannot have a source digest")


@dataclass(frozen=True, slots=True)
class RepositoryLayoutDocument:
    """Validated repository layout configuration paired with its source state."""

    source: RepositoryLayoutSourceIdentity
    value: ToolingConfiguration


def source_directory(root: Path, value: str) -> Path:
    """Keep configurable source scopes out of hidden state and generated trees."""
    path = repo_path(root, value)
    if any(
        part.startswith(".") or part.casefold() in RESERVED_DIRECTORIES
        for part in Path(value).parts
    ):
        raise ValueError(f"Source layout cannot use hidden or generated directories: {value}")
    return path


def within_roots(value: str, roots: tuple[str, ...]) -> bool:
    return any(repo_path_is_within(value, directory) for directory in roots)


def _validate_layout(root: Path, result: RepositoryLayout) -> None:
    """Validate every declared source scope against this checkout."""
    for value in (
        result.discovery,
        result.products,
        result.team_policy,
        result.templates,
        result.workflow_docs,
        result.new_project_root,
        *result.product_roots,
        *result.library_roots,
    ):
        source_directory(root, value)
    for roots in (result.product_roots, result.library_roots):
        if not roots or len({value.casefold() for value in roots}) != len(roots):
            raise ValueError("Layout roots must be nonempty and unique")


def read_repository_layout(root: Path) -> RepositoryLayoutDocument:
    """Read and identify authored adapter bytes or the absence-based default."""
    root = root.resolve()
    path = repo_path(root, CONFIG_NAME)
    try:
        path.lstat()
    except FileNotFoundError:
        configuration = ToolingConfiguration()
        source = RepositoryLayoutSourceIdentity(
            state="DEFAULTED",
            path=CONFIG_NAME,
            sha256=None,
        )
    except OSError as exc:
        raise ValueError(f"{CONFIG_NAME}: cannot inspect configuration: {exc}") from exc
    else:
        try:
            content, _ = read_regular_bytes(path, maximum=64 * 1024)
            raw = tomllib.loads(content.decode("utf-8"))
            configuration = parse_model_text(json.dumps(raw), ToolingConfiguration)
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            raise ValueError(f"{CONFIG_NAME}: invalid configuration: {exc}") from exc
        source = RepositoryLayoutSourceIdentity(
            state="AUTHORED",
            path=CONFIG_NAME,
            sha256=hashlib.sha256(content).hexdigest(),
        )
    _validate_layout(root, configuration.layout)
    return RepositoryLayoutDocument(source=source, value=configuration)


def require_repository_layout_current(root: Path, captured: RepositoryLayoutDocument) -> None:
    """Reject an operation whose adapter source changed after it was captured."""
    try:
        current = read_repository_layout(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot verify {CONFIG_NAME} freshness: {exc}") from exc
    if current.source != captured.source:
        raise ValueError(f"{CONFIG_NAME} changed after its repository layout was captured")


def layout(root: Path) -> RepositoryLayout:
    """Compatibility projection for callers that need only the path layout."""
    return read_repository_layout(root).value.layout


def workflow_guide(root: Path, value: str) -> str:
    """Map a built-in workflow guide to this checkout's documented guide location."""
    prefix = "docs/workflow/"
    return (
        f"{layout(root).workflow_docs}/{value[len(prefix) :]}"
        if value.startswith(prefix)
        else value
    )
