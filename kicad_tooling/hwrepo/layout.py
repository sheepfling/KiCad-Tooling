"""Declarative repository adapters; the template layout remains the default."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field

from .contracts import parse_model_text, repo_path
from .models import RepositoryPath, StrictModel

CONFIG_NAME = "kicad-tooling.toml"
RESERVED_DIRECTORIES = frozenset({"build", "generated", "__pycache__", "releases", "restores"})


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


def source_directory(root: Path, value: str) -> Path:
    """Keep configurable source scopes out of hidden state and generated trees."""
    path = repo_path(root, value)
    if any(part.startswith(".") or part.casefold() in RESERVED_DIRECTORIES
           for part in Path(value).parts):
        raise ValueError(f"Source layout cannot use hidden or generated directories: {value}")
    return path


def within_roots(value: str, roots: tuple[str, ...]) -> bool:
    return any(value.startswith(f"{directory}/") for directory in roots)


def layout(root: Path) -> RepositoryLayout:
    """Read per-checkout TOML; never execute hooks or cache another root's settings."""
    path = repo_path(root, CONFIG_NAME)
    configuration = ToolingConfiguration()
    if path.exists():
        if not path.is_file() or path.stat().st_size > 64 * 1024:
            raise ValueError(f"{CONFIG_NAME} must be a regular TOML file under 64 KiB")
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
        try:
            configuration = parse_model_text(json.dumps(raw), ToolingConfiguration)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{CONFIG_NAME}: invalid configuration: {exc}") from exc
    result = configuration.layout
    for value in (result.discovery, result.products, result.team_policy, result.templates, result.workflow_docs,
                  result.new_project_root, *result.product_roots, *result.library_roots):
        source_directory(root, value)
    for roots in (result.product_roots, result.library_roots):
        if not roots or len({value.casefold() for value in roots}) != len(roots):
            raise ValueError("Layout roots must be nonempty and unique")
    return result


def workflow_guide(root: Path, value: str) -> str:
    """Map a built-in workflow guide to this checkout's documented guide location."""
    prefix = "docs/workflow/"
    return f"{layout(root).workflow_docs}/{value[len(prefix):]}" if value.startswith(prefix) else value
