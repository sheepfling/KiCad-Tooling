"""Deterministic typed review projections; procurement rows never authorize a build."""

from __future__ import annotations

import hashlib
import platform
import tempfile
from pathlib import Path

from ..git import git_output
from . import __version__
from .contracts import read_model, repo_path, write_model
from .discovery import settings
from .evidence import digest as file_digest
from .generation_outputs import (
    bom_rows,
    csv_bytes,
    csv_cell,
    electrical_view,
    expected_outputs,
    expected_outputs_from_repository,
    harness_schedule,
    harness_schedule_csv_bytes,
    library_sbom,
    model_json_bytes,
    schema_json_bytes,
    system_view,
)
from .layout import CONFIG_NAME, layout
from .models import (
    SnapshotManifest,
    SnapshotVerification,
)
from .product import load_repository
from .repository import ephemeral

__all__ = [
    "bom_rows",
    "check_generation",
    "csv_bytes",
    "csv_cell",
    "drift",
    "electrical_view",
    "expected_outputs",
    "generate",
    "harness_schedule",
    "harness_schedule_csv_bytes",
    "library_sbom",
    "model_json_bytes",
    "schema_json_bytes",
    "snapshot",
    "system_view",
    "verify_snapshot",
]


def drift(
    root: Path,
    selected_project_ids: tuple[str, ...] | None = None,
    *,
    output: Path | None = None,
) -> tuple[str, ...]:
    """Detect full or selected-product output drift without writing files."""
    repository = load_repository(root, selected_project_ids)
    outputs = expected_outputs_from_repository(root, repository, selected_project_ids)
    destination = root if output is None else output
    issues = [
        f"GENERATION_DRIFT: {name}"
        for name, expected in sorted(outputs.items())
        if not (path := repo_path(destination, name)).is_file() or path.read_bytes() != expected
    ]
    index_document = repository.product_index_document
    if index_document is None:
        raise ValueError("Cannot inspect stale outputs without a captured product index")
    directories = ["generated", "schemas"] if selected_project_ids is None else []
    directories.extend(
        f"{Path(entry.path).parent.as_posix()}/build"
        for entry in index_document.value.products
        if selected_project_ids is None or set(selected_project_ids).intersection(entry.project_ids)
    )
    found = {
        path.relative_to(destination).as_posix()
        for directory in directories
        for path in (destination / directory).rglob("*")
        if path.is_file()
        and path.relative_to(destination).as_posix()
        not in {"generated/README.md", "schemas/README.md"}
    }
    issues.extend(f"STALE_OUTPUT: {name}" for name in sorted(found - set(outputs)))
    return tuple(issues)


def generate(
    root: Path,
    output: Path | None = None,
    selected_project_ids: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Write validated projections only; intentional stale files remain for review."""
    outputs = expected_outputs(root, selected_project_ids)
    destination = root if output is None else output
    destinations = {name: repo_path(destination, name) for name in outputs}
    for path in destinations.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        destinations[name].write_bytes(content)
    return tuple(sorted(outputs))


def check_generation(
    root: Path, selected_project_ids: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Regenerate in isolation and compare an independent pass, without cached outputs."""
    with tempfile.TemporaryDirectory(prefix="kicad-generation-") as temporary:
        output = Path(temporary).resolve()
        generate(root, output, selected_project_ids)
        return drift(root, selected_project_ids, output=output)


def _git(root: Path, *args: str) -> str:
    return git_output(root, *args)


def snapshot(root: Path, output: Path) -> SnapshotManifest:
    """Write a retained integrity manifest; it explicitly is not release evidence."""
    repository = load_repository(root)
    outputs = expected_outputs_from_repository(root, repository)
    root, output = root.resolve(), output.resolve()
    if output == root or (root in output.parents and not output.is_relative_to(root / "build")):
        raise ValueError("In-repository review output must be under build/")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retained evidence: {output}")
    configuration = layout(root)
    policy = settings(root)
    sources: set[Path] = set()
    directories = {
        "catalog",
        "products",
        "projects",
        "examples",
        "libraries",
        "tools",
        "tests",
        ".github",
        "docs",
        "templates",
        *policy.project_roots,
        *configuration.product_roots,
        *configuration.library_roots,
        configuration.templates,
        configuration.workflow_docs,
    }
    for directory in sorted(directories):
        for path in repo_path(root, directory).rglob("*"):
            name = path.relative_to(root).as_posix()
            if ephemeral(name):
                continue
            path = repo_path(root, name)
            if path.is_file():
                sources.add(path)
    for name in (
        configuration.discovery,
        configuration.products,
        configuration.team_policy,
        policy.catalogs.parts,
        policy.catalogs.interfaces,
        policy.catalogs.libraries,
        policy.catalogs.toolchains,
        policy.catalogs.release_policies,
    ):
        path = repo_path(root, name)
        if path.is_file():
            sources.add(path)
    source_hashes = {
        path.relative_to(root).as_posix(): file_digest(path) for path in sorted(sources)
    }
    for name in (
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "CHANGELOG.md",
        ".gitattributes",
        ".gitignore",
        "pyproject.toml",
        "template-adoption.json",
        CONFIG_NAME,
    ):
        if (path := repo_path(root, name)).is_file():
            source_hashes[name] = file_digest(path)
    manifest = SnapshotManifest(
        commit=_git(root, "rev-parse", "HEAD"),
        working_tree_clean=not bool(
            _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        ),
        git_status=_git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        python_version=platform.python_version(),
        policy_version=__version__,
        products=tuple(product.id for product in repository.products),
        checks={
            "product_policy": "PASS",
            "kicad": "NOT_RUN",
            "mechanical_fit": "NOT_RUN",
            "human_review": "NOT_RUN",
        },
        sources_sha256=source_hashes,
        artifacts_sha256={
            name: hashlib.sha256(content).hexdigest() for name, content in sorted(outputs.items())
        },
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, content in outputs.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    write_model(output / "manifest.json", manifest)
    return manifest


def verify_snapshot(output: Path) -> SnapshotVerification:
    """Check retained bytes and inventory, not authenticity or source reproduction."""
    manifest = read_model(output / "manifest.json", SnapshotManifest)
    for name, expected in manifest.artifacts_sha256.items():
        if file_digest(repo_path(output, name)) != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    actual = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    if actual != set(manifest.artifacts_sha256) | {"manifest.json"}:
        raise ValueError("Retained artifact inventory differs")
    return SnapshotVerification(
        status="PASS",
        artifacts=len(manifest.artifacts_sha256),
        scope="artifact_integrity_only_not_authenticity_or_source_reconstruction",
    )
