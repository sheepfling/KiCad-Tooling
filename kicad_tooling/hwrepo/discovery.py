"""Discover project islands and adapt local manifests to shared policy contracts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from .contracts import parse_model_text, read_model, read_regular_bytes, repo_path
from .layout import (
    RESERVED_DIRECTORIES,
    RepositoryLayout,
    RepositoryLayoutDocument,
    layout,
    read_repository_layout,
    require_repository_layout_current,
    source_directory,
)
from .model_primitives import Digest, RepositoryPath
from .project_models import (
    ProjectConfig,
    ProjectDiscovery,
    ProjectManifest,
    ProjectRecord,
    ProjectRegistry,
    ProjectTestContract,
    ToolchainsCatalog,
)

MAX_PROJECT_DISCOVERY_ENTRIES = 10_000


@dataclass(frozen=True, slots=True)
class ProjectManifestSourceIdentity:
    """Repository path and digest of the exact bytes parsed as one manifest."""

    path: RepositoryPath
    sha256: Digest


@dataclass(frozen=True, slots=True)
class ProjectDiscoverySourceIdentity:
    """Repository path and digest of the exact project-discovery policy bytes."""

    path: RepositoryPath
    sha256: Digest


@dataclass(frozen=True, slots=True)
class ProjectTestContractSourceIdentity:
    """Repository path and digest of one manifest-selected test contract."""

    path: RepositoryPath
    sha256: Digest


@dataclass(frozen=True, slots=True)
class ProjectTestContractDocument:
    """Validated test contract paired with the exact bytes from which it was parsed."""

    source: ProjectTestContractSourceIdentity
    value: ProjectTestContract


@dataclass(frozen=True, slots=True)
class ProjectConfigDocument:
    """Project configuration and the check-contract source it incorporates."""

    project_id: str
    test_contract: ProjectTestContractDocument
    value: ProjectConfig


@dataclass(frozen=True, slots=True)
class ProjectDiscoveryDocument:
    """Discovery policy and repository-layout adapter paired with their sources."""

    source: ProjectDiscoverySourceIdentity
    repository_configuration: RepositoryLayoutDocument
    value: ProjectDiscovery


@dataclass(frozen=True, slots=True)
class ProjectRegistryEntry:
    """Typed projection tied to the authored manifest that produced it."""

    record: ProjectRecord
    manifest: ProjectManifest
    source: ProjectManifestSourceIdentity

    def __post_init__(self) -> None:
        if self.manifest.id != self.record.id:
            raise ValueError("Project manifest and registry record IDs must match")
        if self.source.path != self.record.config:
            raise ValueError("Project registry source path must match its manifest path")


@dataclass(frozen=True, slots=True)
class ProjectRegistrySnapshot:
    """Registry projection tied to one discovery policy and its manifest sources."""

    discovery: ProjectDiscoveryDocument
    registry: ProjectRegistry
    entries: tuple[ProjectRegistryEntry, ...]
    by_id: Mapping[str, ProjectRegistryEntry] = field(init=False)

    def __post_init__(self) -> None:
        if self.registry.catalogs != self.discovery.value.catalogs:
            raise ValueError("Project registry catalogs must match the discovery policy")
        entries = tuple(self.entries)
        if tuple(entry.record for entry in entries) != self.registry.projects:
            raise ValueError("Project registry entries must match the projected registry")
        lookup: dict[str, ProjectRegistryEntry] = {}
        normalized_ids: set[str] = set()
        for entry in entries:
            normalized_id = entry.record.id.casefold()
            if normalized_id in normalized_ids:
                raise ValueError(f"Duplicate project id: {entry.record.id}")
            normalized_ids.add(normalized_id)
            lookup[entry.record.id] = entry
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "by_id", MappingProxyType(lookup))


def _require_source_current(
    root: Path,
    path: RepositoryPath,
    expected_sha256: Digest,
    label: str,
) -> None:
    """Reject an authored registry input that changed after its typed read."""
    source_path = repo_path(root, path)
    try:
        content, _ = read_regular_bytes(source_path)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} source is unavailable: {path}: {exc}") from exc
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"{label} source changed during operation: {path}")


def require_project_registry_snapshot_current(
    root: Path,
    snapshot: ProjectRegistrySnapshot,
) -> None:
    """Recheck the adapter, discovery policy, and manifests in one registry snapshot."""
    root = root.resolve()
    require_repository_layout_current(root, snapshot.discovery.repository_configuration)
    _require_source_current(
        root,
        snapshot.discovery.source.path,
        snapshot.discovery.source.sha256,
        "Project discovery policy",
    )
    for entry in snapshot.entries:
        _require_source_current(
            root,
            entry.source.path,
            entry.source.sha256,
            f"Project manifest {entry.record.id}",
        )


def require_project_config_document_current(
    root: Path,
    document: ProjectConfigDocument,
) -> None:
    """Reject a project configuration whose authored test contract has changed."""
    _require_source_current(
        root.resolve(),
        document.test_contract.source.path,
        document.test_contract.source.sha256,
        f"Project test contract for {document.project_id}",
    )


def _validate_discovery_policy(
    root: Path, policy: ProjectDiscovery, repository_layout: RepositoryLayout
) -> None:
    bases = [source_directory(root, name) for name in policy.project_roots]
    if any(left != right and left.is_relative_to(right) for left in bases for right in bases):
        raise ValueError("Project discovery roots must not overlap")
    shared = [source_directory(root, name) for name in repository_layout.library_roots]
    products = [source_directory(root, name) for name in repository_layout.product_roots]
    if any(
        left.is_relative_to(right) or right.is_relative_to(left)
        for left in bases
        for right in (*shared, *products)
    ):
        raise ValueError("Project discovery roots must not overlap library or product roots")


def read_project_discovery(
    root: Path,
    *,
    repository_configuration: RepositoryLayoutDocument | None = None,
) -> ProjectDiscoveryDocument:
    """Read discovery policy using one captured repository-layout document."""
    root = root.resolve()
    repository_configuration = repository_configuration or read_repository_layout(root)
    repository_layout = repository_configuration.value.layout
    path = repo_path(root, repository_layout.discovery)
    try:
        content, _ = read_regular_bytes(path)
        policy = parse_model_text(content.decode("utf-8"), ProjectDiscovery)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{path}: invalid project discovery policy: {exc}") from exc
    _validate_discovery_policy(root, policy, repository_layout)
    return ProjectDiscoveryDocument(
        source=ProjectDiscoverySourceIdentity(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        repository_configuration=repository_configuration,
        value=policy,
    )


def settings(root: Path) -> ProjectDiscovery:
    """Compatibility projection for callers that need only the policy model."""
    return read_project_discovery(root).value


def _manifest_paths(
    root: Path, policy: ProjectDiscovery, project_id: str | None = None
) -> tuple[Path, ...]:
    if project_id is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must be one portable directory name")
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
            if visited > MAX_PROJECT_DISCOVERY_ENTRIES:
                raise ValueError(
                    "Project discovery exceeded "
                    f"{MAX_PROJECT_DISCOVERY_ENTRIES} entries; use narrower roots"
                )
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


def manifest_paths(root: Path, project_id: str | None = None) -> tuple[Path, ...]:
    """Bounded discovery shared by inventory and malformed-manifest repair readers.

    Stop at each island: nesting groups does not make subprojects inside an island
    independent. Do not parse peer manifests when repairing one selected project.
    """
    root = root.resolve()
    return _manifest_paths(root, settings(root), project_id)


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


def _project_record(root: Path, path: Path, manifest: ProjectManifest) -> ProjectRecord:
    return ProjectRecord(
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


def load_registry_snapshot(root: Path) -> ProjectRegistrySnapshot:
    """Load project records and retain the exact authored manifest identities."""
    root = root.resolve()
    discovery = read_project_discovery(root)
    policy = discovery.value
    entries: list[ProjectRegistryEntry] = []
    seen: set[str] = set()
    for path in _manifest_paths(root, policy):
        try:
            content, _ = read_regular_bytes(path)
            manifest = parse_model_text(content.decode("utf-8"), ProjectManifest)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
        if manifest.id.casefold() in seen:
            raise ValueError(f"Duplicate project id: {manifest.id}")
        seen.add(manifest.id.casefold())
        if path.parent.name != manifest.id:
            raise ValueError(f"Project directory must match id {manifest.id}: {path.parent.name}")
        record = _project_record(root, path, manifest)
        entries.append(
            ProjectRegistryEntry(
                record=record,
                manifest=manifest,
                source=ProjectManifestSourceIdentity(
                    path=path.relative_to(root).as_posix(),
                    sha256=hashlib.sha256(content).hexdigest(),
                ),
            )
        )
    ordered_entries = tuple(sorted(entries, key=lambda entry: entry.record.id))
    registry = ProjectRegistry(
        schema_version="1",
        catalogs=policy.catalogs,
        projects=tuple(entry.record for entry in ordered_entries),
    )
    snapshot = ProjectRegistrySnapshot(
        discovery=discovery,
        registry=registry,
        entries=ordered_entries,
    )
    require_project_registry_snapshot_current(root, snapshot)
    return snapshot


def load_registry(root: Path) -> ProjectRegistry:
    """Compatibility projection for callers that need only the registry model."""
    return load_registry_snapshot(root).registry


def _build_project_config(
    root: Path,
    manifest_path: RepositoryPath,
    manifest: ProjectManifest,
    toolchains: ToolchainsCatalog,
    contract: ProjectTestContract,
) -> ProjectConfig:
    path = repo_path(root, manifest_path)
    matching = [record for record in toolchains.toolchains if record.id == manifest.toolchain_id]
    if len(matching) != 1:
        raise ValueError(f"Need one declared toolchain: {manifest.toolchain_id}")
    toolchain = matching[0]
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
        design_lint=contract.design_lint,
        interfaces=manifest.interfaces,
        connector_reviews=manifest.connector_reviews,
        connector_inventory_review=manifest.connector_inventory_review,
    )


def _read_project_test_contract(
    root: Path,
    manifest_path: RepositoryPath,
    manifest: ProjectManifest,
) -> ProjectTestContractDocument:
    """Read the manifest-selected contract once and retain its exact identity."""
    root = root.resolve()
    project_path = repo_path(root, manifest_path)
    contract_path = repo_path(project_path.parent, manifest.checks)
    try:
        content, _ = read_regular_bytes(contract_path)
        contract = parse_model_text(content.decode("utf-8"), ProjectTestContract)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(
            f"{contract_path}: invalid project test contract for {manifest.id}: {exc}"
        ) from exc
    return ProjectTestContractDocument(
        source=ProjectTestContractSourceIdentity(
            path=contract_path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        value=contract,
    )


def load_project_config_document_from_snapshot(
    root: Path,
    entry: ProjectRegistryEntry,
    toolchains: ToolchainsCatalog,
) -> ProjectConfigDocument:
    """Build a project config from one captured manifest and exact contract read."""
    root = root.resolve()
    test_contract = _read_project_test_contract(root, entry.source.path, entry.manifest)
    config = _build_project_config(
        root,
        entry.source.path,
        entry.manifest,
        toolchains,
        test_contract.value,
    )
    return ProjectConfigDocument(
        project_id=entry.record.id,
        test_contract=test_contract,
        value=config,
    )


def load_config_from_snapshot(
    root: Path,
    entry: ProjectRegistryEntry,
    toolchains: ToolchainsCatalog,
) -> ProjectConfig:
    """Build one project config from captured registry and catalog values."""
    return load_project_config_document_from_snapshot(root, entry, toolchains).value


def load_config(root: Path, value: str | Path) -> ProjectConfig:
    """Compatibility reader for callers without a registry snapshot."""
    root = root.resolve()
    relative = Path(value).relative_to(root).as_posix() if Path(value).is_absolute() else str(value)
    path = repo_path(root, relative)
    manifest = read_model(path, ProjectManifest)
    discovery = read_project_discovery(root)
    toolchains = read_model(
        repo_path(root, discovery.value.catalogs.toolchains),
        ToolchainsCatalog,
    )
    contract = _read_project_test_contract(root, relative, manifest)
    config = _build_project_config(root, relative, manifest, toolchains, contract.value)
    require_repository_layout_current(root, discovery.repository_configuration)
    return config
