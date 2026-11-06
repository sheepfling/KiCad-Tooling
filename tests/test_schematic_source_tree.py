"""Hash-bound schematic source trees and immutable source projections."""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.model_primitives import Digest, RepositoryPath
from kicad_tooling.hwrepo.schematic_geometry_models import (
    SchematicSourceFile,
    VerifiedSchematicSourceTree,
)
from kicad_tooling.hwrepo.schematic_source_tree import (
    schematic_instance_bindings,
    verified_schematic_sources,
)
from kicad_tooling.hwrepo.source_state_models import SourceHashInventory

pytestmark = [pytest.mark.architecture, pytest.mark.evidence_lint, pytest.mark.schematic_lint]

_REPO_ROOT = Path(__file__).parents[1]
_PROJECT_DIRECTORY = "tests/fixtures/cross_probe"
_ROOT_PATH = f"{_PROJECT_DIRECTORY}/root.kicad_sch"
_CHILD_PATH = f"{_PROJECT_DIRECTORY}/child.kicad_sch"


def _fixture_hashes() -> SourceHashInventory:
    return {
        path: hashlib.sha256((_REPO_ROOT / path).read_bytes()).hexdigest()
        for path in (_ROOT_PATH, _CHILD_PATH)
    }


def _verified_fixture_tree(
    source_hashes: SourceHashInventory | None = None,
) -> VerifiedSchematicSourceTree:
    hashes = _fixture_hashes() if source_hashes is None else source_hashes
    return verified_schematic_sources(
        _REPO_ROOT,
        _ROOT_PATH,
        _PROJECT_DIRECTORY,
        hashes,
    )


def test_verified_tree_keeps_each_digest_with_its_exact_bytes() -> None:
    hashes = _fixture_hashes()
    tree = _verified_fixture_tree(hashes)

    assert tree.root_path == _ROOT_PATH
    assert tree.project_directory == _PROJECT_DIRECTORY
    assert tree.source_hashes == hashes
    assert set(tree.source_files_by_path) == {_ROOT_PATH, _CHILD_PATH}
    assert tree.source_contents_by_path[_ROOT_PATH] == (_REPO_ROOT / _ROOT_PATH).read_bytes()
    assert tree.source_files_by_path[_CHILD_PATH].source_sha256 == hashes[_CHILD_PATH]

    with pytest.raises(TypeError):
        cast(MutableMapping[RepositoryPath, Digest], tree.source_hashes)[_ROOT_PATH] = "d" * 64
    with pytest.raises(TypeError):
        cast(MutableMapping[RepositoryPath, bytes], tree.source_contents_by_path)[_ROOT_PATH] = (
            b"changed"
        )


def test_reused_child_bindings_keep_the_admitted_digest_and_instance_paths() -> None:
    tree = _verified_fixture_tree()
    child_bindings = tuple(
        binding
        for binding in schematic_instance_bindings(tree)
        if binding.source_path == _CHILD_PATH
    )

    assert len(child_bindings) == 2
    assert {binding.source_sha256 for binding in child_bindings} == {
        tree.source_hashes[_CHILD_PATH]
    }
    assert len({binding.sheet_instance_path for binding in child_bindings}) == 2


def test_missing_or_mismatched_child_hash_blocks_tree_admission() -> None:
    hashes = _fixture_hashes()
    root_only: SourceHashInventory = {_ROOT_PATH: hashes[_ROOT_PATH]}

    with pytest.raises(ValueError, match="absent from the source-bound hashes"):
        _verified_fixture_tree(root_only)

    mismatched_child = {**hashes, _CHILD_PATH: "0" * 64}
    with pytest.raises(ValueError, match="Schematic differs from the source-bound hashes"):
        _verified_fixture_tree(mismatched_child)


def test_source_record_rejects_a_digest_that_does_not_match_its_bytes() -> None:
    contents = (_REPO_ROOT / _ROOT_PATH).read_bytes()

    with pytest.raises(ValidationError, match="does not match its retained bytes"):
        SchematicSourceFile(
            source_path=_ROOT_PATH,
            source_sha256="0" * 64,
            contents=contents,
        )
