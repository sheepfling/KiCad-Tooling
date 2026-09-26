"""Discover project islands and adapt local manifests to shared policy contracts."""

from __future__ import annotations

import re
from pathlib import Path

from .contracts import read_model, repo_path
from .layout import RESERVED_DIRECTORIES, layout, source_directory
from .models import (
    ProjectConfig,
    ProjectDiscovery,
    ProjectManifest,
    ProjectRecord,
    ProjectRegistry,
    ProjectTestContract,
    ToolchainsCatalog,
)


def settings(root: Path) -> ProjectDiscovery:
    policy = read_model(repo_path(root, layout(root).discovery), ProjectDiscovery)
    bases = [source_directory(root, name) for name in policy.project_roots]
    if any(left != right and left.is_relative_to(right) for left in bases for right in bases):
        raise ValueError("Project discovery roots must not overlap")
    shared = [source_directory(root, name) for name in layout(root).library_roots]
    products = [source_directory(root, name) for name in layout(root).product_roots]
    if any(
        left.is_relative_to(right) or right.is_relative_to(left)
        for left in bases
        for right in (*shared, *products)
    ):
        raise ValueError("Project discovery roots must not overlap library or product roots")
    return policy


def manifest_paths(root: Path, project_id: str | None = None) -> tuple[Path, ...]:
    """Bounded discovery shared by inventory and malformed-manifest repair readers.

    Stop at each island: nesting groups does not make subprojects inside an island
    independent. Do not parse peer manifests when repairing one selected project.
    """
    root = root.resolve()
    if project_id is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must be one portable directory name")
    policy = settings(root)
    found: list[Path] = []
    visited = 0

    def visit(base: Path, depth: int) -> None:
        nonlocal visited
        if not base.exists():
            return
        if not base.is_dir():
            raise ValueError(f"Project root is not a directory: {base}")
        for child in sorted(base.iterdir()):
            visited += 1
            if visited > 10000:
                raise ValueError("Project discovery exceeded 10000 entries; use narrower roots")
            if child.name.startswith(".") or child.name.casefold() in RESERVED_DIRECTORIES:
                continue
            child = repo_path(root, child.relative_to(root).as_posix())
            if not child.is_dir():
                continue
            manifest = repo_path(root, (child / "project.json").relative_to(root).as_posix())
            if manifest.exists():
                if project_id is None or child.name == project_id:
                    if not manifest.is_file():
                        raise ValueError(f"Selected manifest is not a regular file: {manifest}")
                    found.append(manifest)
            elif depth < policy.project_depth:
                visit(child, depth + 1)

    for source_root in policy.project_roots:
        visit(repo_path(root, source_root), 1)
    return tuple(sorted(found))


def project_destination(root: Path, project_id: str) -> Path:
    """Require creation to land within exactly one configured discovery scope."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must be one portable directory name")
    root = root.resolve()
    policy = settings(root)
    destination = source_directory(root, f"{layout(root).new_project_root}/{project_id}")
    scopes = [repo_path(root, name) for name in policy.project_roots]
    if not any(
        destination.is_relative_to(base)
        and 1 <= len(destination.relative_to(base).parts) <= policy.project_depth
        for base in scopes
    ):
        raise ValueError(
            "new_project_root must place new islands within project_roots/project_depth"
        )
    for ancestor in destination.parents:
        if ancestor == root:
            break
        if repo_path(ancestor, "project.json").exists():
            raise ValueError("Cannot create a project inside an existing project island")
    return destination


def local_name(root: Path, directory: Path, name: str) -> str:
    """Resolve a portable project-local path without permitting parent traversal."""
    return repo_path(directory, name).relative_to(root.resolve()).as_posix()


def load_registry(root: Path) -> ProjectRegistry:
    root = root.resolve()
    policy = settings(root)
    records: list[ProjectRecord] = []
    seen: set[str] = set()
    for path in manifest_paths(root):
        manifest = read_model(path, ProjectManifest)
        if manifest.id.casefold() in seen:
            raise ValueError(f"Duplicate project id: {manifest.id}")
        seen.add(manifest.id.casefold())
        if path.parent.name != manifest.id:
            raise ValueError(f"Project directory must match id {manifest.id}: {path.parent.name}")
        records.append(
            ProjectRecord(
                id=manifest.id,
                kind=manifest.kind,
                status=manifest.status,
                assurance_profile=manifest.assurance_profile,
                config=path.relative_to(root).as_posix(),
                project=local_name(root, path.parent, manifest.project),
                component_identity=manifest.component_identity,
                tags=manifest.tags,
                interfaces=manifest.interfaces,
                library_ids=manifest.library_ids,
                mechanical_handoff=(
                    None
                    if manifest.mechanical_handoff is None
                    else local_name(root, path.parent, manifest.mechanical_handoff)
                ),
                governance_record=(
                    None
                    if manifest.governance_record is None
                    else local_name(root, path.parent, manifest.governance_record)
                ),
            )
        )
    return ProjectRegistry(
        schema_version="1",
        catalogs=policy.catalogs,
        projects=tuple(sorted(records, key=lambda record: record.id)),
    )


def load_config(root: Path, value: str | Path) -> ProjectConfig:
    root = root.resolve()
    relative = Path(value).relative_to(root).as_posix() if Path(value).is_absolute() else str(value)
    path = repo_path(root, relative)
    manifest = read_model(path, ProjectManifest)
    policy = settings(root)
    toolchains = read_model(repo_path(root, policy.catalogs.toolchains), ToolchainsCatalog)
    matching = [record for record in toolchains.toolchains if record.id == manifest.toolchain_id]
    if len(matching) != 1:
        raise ValueError(f"Need one declared toolchain: {manifest.toolchain_id}")
    toolchain = matching[0]
    contract = read_model(repo_path(path.parent, manifest.checks), ProjectTestContract)
    return ProjectConfig(
        schema_version="1",
        project_id=manifest.id,
        kind=manifest.kind,
        component_identity=manifest.component_identity,
        assurance_profile=manifest.assurance_profile,
        not_for_manufacture=manifest.assurance_profile != "production",
        toolchain_id=toolchain.id,
        kicad_version=toolchain.kicad_version,
        cli_profile=toolchain.cli_profile,
        image=toolchain.image,
        project=local_name(root, path.parent, manifest.project),
        source_roots=tuple(local_name(root, path.parent, name) for name in manifest.source_roots)
        + manifest.shared_source_roots,
        required_inputs=tuple(
            local_name(root, path.parent, name) for name in manifest.required_inputs
        )
        + manifest.shared_inputs,
        validation=contract.validation,
        electrical=(
            None
            if contract.electrical is None
            else local_name(root, path.parent, contract.electrical)
        ),
    )
