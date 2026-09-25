"""Discover project islands and adapt local manifests to shared policy contracts."""
from __future__ import annotations

from pathlib import Path

from .contracts import read_model, repo_path
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
    return read_model(repo_path(root, "catalog/projects.json"), ProjectDiscovery)


def local_name(root: Path, directory: Path, name: str) -> str:
    """Resolve a portable project-local path without permitting parent traversal."""
    return repo_path(directory, name).relative_to(root.resolve()).as_posix()


def load_registry(root: Path) -> ProjectRegistry:
    root = root.resolve()
    policy = settings(root)
    records: list[ProjectRecord] = []
    seen: set[str] = set()
    for source_root in policy.project_roots:
        base = repo_path(root, source_root)
        if source_root not in {"projects", "examples/projects"}:
            raise ValueError(f"Project root must be projects or examples/projects: {source_root}")
        if not base.is_dir():
            if base.exists():
                raise ValueError(f"Project root is not a directory: {source_root}")
            continue
        for path in sorted(base.glob("*/project.json")):
            path = repo_path(root, path.relative_to(root).as_posix())
            manifest = read_model(path, ProjectManifest)
            if manifest.id.casefold() in seen:
                raise ValueError(f"Duplicate project id: {manifest.id}")
            seen.add(manifest.id.casefold())
            if path.parent.name != manifest.id:
                raise ValueError(f"Project directory must match id {manifest.id}: {path.parent.name}")
            records.append(ProjectRecord(
                id=manifest.id, kind=manifest.kind, status=manifest.status,
                assurance_profile=manifest.assurance_profile,
                config=path.relative_to(root).as_posix(),
                project=local_name(root, path.parent, manifest.project),
                component_identity=manifest.component_identity, tags=manifest.tags,
                interfaces=manifest.interfaces, library_ids=manifest.library_ids,
                mechanical_handoff=(None if manifest.mechanical_handoff is None else
                                    local_name(root, path.parent, manifest.mechanical_handoff)),
                governance_record=(None if manifest.governance_record is None else
                                   local_name(root, path.parent, manifest.governance_record)),
            ))
    return ProjectRegistry(schema_version="1", catalogs=policy.catalogs,
                           projects=tuple(sorted(records, key=lambda record: record.id)))


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
        schema_version="1", project_id=manifest.id, kind=manifest.kind,
        component_identity=manifest.component_identity,
        assurance_profile=manifest.assurance_profile,
        not_for_manufacture=manifest.assurance_profile != "production",
        toolchain_id=toolchain.id, kicad_version=toolchain.kicad_version, image=toolchain.image,
        project=local_name(root, path.parent, manifest.project),
        source_roots=tuple(local_name(root, path.parent, name) for name in manifest.source_roots)
                     + manifest.shared_source_roots,
        required_inputs=tuple(local_name(root, path.parent, name) for name in manifest.required_inputs)
                        + manifest.shared_inputs,
        validation=contract.validation,
        electrical=(None if contract.electrical is None else
                    local_name(root, path.parent, contract.electrical)),
    )
