"""Source identity for the authored manifests behind a project registry."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.discovery import (
    load_project_config_document_from_snapshot,
    load_registry,
    load_registry_snapshot,
    require_project_config_document_current,
    require_project_registry_snapshot_current,
)
from kicad_tooling.hwrepo.project_models import (
    CatalogPaths,
    ComponentIdentity,
    IgnoredChecks,
    PcbValidationContract,
    ProjectDiscovery,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    ToolchainRecord,
    ToolchainsCatalog,
)


def _project_root(root: Path) -> tuple[Path, ProjectManifest]:
    (root / "catalog").mkdir()
    (root / "projects/board-a").mkdir(parents=True)
    catalogs = CatalogPaths(
        parts="catalog/parts.json",
        interfaces="catalog/interfaces.json",
        libraries="catalog/libraries.json",
        toolchains="catalog/toolchains.json",
        release_policies="catalog/release-policies.json",
    )
    write_model(
        root / "catalog/projects.json",
        ProjectDiscovery(catalogs=catalogs, project_roots=("projects",)),
    )
    manifest = ProjectManifest(
        id="board-a",
        kind=ProjectKind.PCB,
        status="training_fixture",
        assurance_profile="training",
        toolchain_id="kicad-test",
        project="board.kicad_pro",
        source_roots=("src",),
        required_inputs=(),
        component_identity=ComponentIdentity(required=False, part_ids=()),
    )
    write_model(root / "projects/board-a/project.json", manifest)
    return root, manifest


def test_snapshot_binds_project_projection_to_exact_manifest_bytes_and_is_read_only(
    tmp_path: Path,
) -> None:
    root, manifest = _project_root(tmp_path)
    source_path = root / "projects/board-a/project.json"
    source_bytes = source_path.read_bytes()

    snapshot = load_registry_snapshot(root)

    entry = snapshot.by_id["board-a"]
    discovery_path = root / "catalog/projects.json"
    assert entry.manifest == manifest
    assert entry.record.id == entry.manifest.id
    assert entry.source.path == "projects/board-a/project.json"
    assert entry.record.config == entry.source.path
    assert entry.source.sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert snapshot.discovery.source.path == "catalog/projects.json"
    assert (
        snapshot.discovery.source.sha256 == hashlib.sha256(discovery_path.read_bytes()).hexdigest()
    )
    assert snapshot.registry.catalogs == snapshot.discovery.value.catalogs
    assert snapshot.registry.projects == (entry.record,)
    assert snapshot.discovery.repository_configuration.source.state == "DEFAULTED"
    assert snapshot.discovery.repository_configuration.source.path == "kicad-tooling.toml"
    assert snapshot.discovery.repository_configuration.source.sha256 is None
    with pytest.raises(TypeError):
        snapshot.by_id["board-b"] = entry  # type: ignore[index]


def test_load_registry_remains_the_snapshot_projection(tmp_path: Path) -> None:
    root, _ = _project_root(tmp_path)

    snapshot = load_registry_snapshot(root)

    assert load_registry(root) == snapshot.registry


def test_snapshot_binds_authored_repository_layout_configuration(tmp_path: Path) -> None:
    root, _ = _project_root(tmp_path)
    config = root / "kicad-tooling.toml"
    config.write_text(
        'schema_version = "1"\n[layout]\ndiscovery = "catalog/projects.json"\n',
        encoding="utf-8",
    )
    config_bytes = config.read_bytes()

    snapshot = load_registry_snapshot(root)

    source = snapshot.discovery.repository_configuration.source
    assert source.state == "AUTHORED"
    assert source.path == "kicad-tooling.toml"
    assert source.sha256 == hashlib.sha256(config_bytes).hexdigest()


def test_snapshot_freshness_rejects_changed_discovery_policy(tmp_path: Path) -> None:
    root, _ = _project_root(tmp_path)
    snapshot = load_registry_snapshot(root)
    discovery_path = root / snapshot.discovery.source.path
    discovery = snapshot.discovery.value.model_copy(update={"project_depth": 2})
    write_model(discovery_path, discovery)

    with pytest.raises(ValueError, match="Project discovery policy source changed"):
        require_project_registry_snapshot_current(root, snapshot)


def test_snapshot_freshness_rejects_changed_project_manifest(tmp_path: Path) -> None:
    root, manifest = _project_root(tmp_path)
    snapshot = load_registry_snapshot(root)
    manifest_path = root / snapshot.by_id["board-a"].source.path
    write_model(manifest_path, manifest.model_copy(update={"tags": ("changed",)}))

    with pytest.raises(ValueError, match="Project manifest board-a source changed"):
        require_project_registry_snapshot_current(root, snapshot)


def test_project_config_binds_and_rechecks_manifest_selected_contract_bytes(
    tmp_path: Path,
) -> None:
    root, manifest = _project_root(tmp_path)
    manifest = manifest.model_copy(update={"checks": "quality/checks.json"})
    write_model(root / "projects/board-a/project.json", manifest)
    contract_path = root / "projects/board-a/quality/checks.json"
    contract_path.parent.mkdir()
    contract = ProjectTestContract(
        validation=PcbValidationContract(
            kind=ProjectKind.PCB,
            components={},
            nets={},
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        )
    )
    write_model(contract_path, contract)
    contract_bytes = contract_path.read_bytes()
    toolchains = ToolchainsCatalog(
        schema_version="1",
        toolchains=(
            ToolchainRecord(
                id="kicad-test",
                kicad_version="10.0.0",
                image="example/kicad@sha256:" + "0" * 64,
                desktop_edit_policy="reviewed",
                installer_source="synthetic fixture",
                migration_policy="review before use",
            ),
        ),
    )
    snapshot = load_registry_snapshot(root)

    document = load_project_config_document_from_snapshot(
        root,
        snapshot.by_id["board-a"],
        toolchains,
    )

    assert document.value.project_id == "board-a"
    assert document.value.validation == contract.validation
    assert document.test_contract.source.path == "projects/board-a/quality/checks.json"
    assert document.test_contract.source.sha256 == hashlib.sha256(contract_bytes).hexdigest()
    require_project_config_document_current(root, document)

    contract_path.write_bytes(contract_bytes + b"\n")
    with pytest.raises(
        ValueError,
        match="Project test contract for board-a source changed during operation",
    ):
        require_project_config_document_current(root, document)
