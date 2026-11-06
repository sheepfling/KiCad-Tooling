"""Product index capture stays attached to repository composition."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TypeVar, cast

import pytest
from pydantic import BaseModel

from kicad_tooling.hwrepo import (
    generation,
    generation_outputs,
    product,
    product_repository_models,
    release,
    releasing,
)
from kicad_tooling.hwrepo.layout import layout
from kicad_tooling.hwrepo.model_primitives import RepositoryPath
from kicad_tooling.hwrepo.product import load_repository
from kicad_tooling.hwrepo.product_models import ProductIndex
from kicad_tooling.hwrepo.product_repository_models import ProductRepository
from kicad_tooling.hwrepo.product_source_inputs import (
    ProductIndexDocument,
    read_product_index_document,
)
from kicad_tooling.hwrepo.release_contract_models import ReleaseManifest

ModelT = TypeVar("ModelT", bound=BaseModel)

ROOT = Path()


def test_repository_result_model_has_one_owning_module() -> None:
    owner = Path(product_repository_models.__file__)

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert product.ProductRepository is product_repository_models.ProductRepository
    assert release.ProductRepository is product_repository_models.ProductRepository
    assert releasing.ProductRepository is product_repository_models.ProductRepository


def test_generation_projection_imports_remain_compatible() -> None:
    for name in (
        "bom_rows",
        "csv_bytes",
        "csv_cell",
        "electrical_view",
        "expected_outputs",
        "harness_schedule",
        "harness_schedule_csv_bytes",
        "library_sbom",
        "model_json_bytes",
        "schema_json_bytes",
        "system_view",
    ):
        assert getattr(generation, name) is getattr(generation_outputs, name), name


def test_product_repository_retains_the_captured_index_document() -> None:
    document = read_product_index_document(ROOT, layout(ROOT).products)

    repository = load_repository(ROOT, (), product_index_document=document)

    assert repository.product_index_document is document


def test_product_repository_lookups_are_read_only_copies() -> None:
    product_project_ids: dict[str, tuple[str, ...]] = {"product": ("project",)}
    repository = ProductRepository(
        products=(),
        product_project_ids=product_project_ids,
        parts={},
        interfaces={},
        projects={},
        product_sources={},
        issues=(),
    )

    product_project_ids["later"] = ("other-project",)
    assert dict(repository.product_project_ids) == {"product": ("project",)}

    for lookup in (
        repository.product_project_ids,
        repository.parts,
        repository.interfaces,
        repository.projects,
        repository.product_sources,
    ):
        with pytest.raises(TypeError):
            cast(MutableMapping[object, object], lookup)["later"] = object()


def test_generation_does_not_reread_the_product_index(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read_model = generation_outputs.read_model

    def reject_product_index_read(path: Path, model: type[ModelT]) -> ModelT:
        if model is ProductIndex:
            raise AssertionError("generation reread the product index")
        return original_read_model(path, model)

    monkeypatch.setattr(generation, "read_model", reject_product_index_read)
    monkeypatch.setattr(generation_outputs, "read_model", reject_product_index_read)

    assert generation.expected_outputs(ROOT)
    assert isinstance(generation.drift(ROOT), tuple)


def test_snapshot_uses_one_captured_product_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_read_model = generation_outputs.read_model
    original_load_repository = generation.load_repository
    calls = 0

    def reject_product_index_read(path: Path, model: type[ModelT]) -> ModelT:
        if model is ProductIndex:
            raise AssertionError("snapshot reread the product index")
        return original_read_model(path, model)

    def count_repository_load(root: Path) -> ProductRepository:
        nonlocal calls
        calls += 1
        return original_load_repository(root)

    def fixture_git_state(_root: Path, *_args: str) -> str:
        return "fixture-git-state"

    monkeypatch.setattr(generation_outputs, "read_model", reject_product_index_read)
    monkeypatch.setattr(generation, "load_repository", count_repository_load)
    monkeypatch.setattr(generation, "_git", fixture_git_state)

    generation.snapshot(ROOT, tmp_path / "snapshot")

    assert calls == 1


def test_release_scope_passes_one_captured_index_to_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = read_product_index_document(ROOT, layout(ROOT).products)
    sentinel = cast(ProductRepository, object())
    captured_root: Path | None = None
    captured_project_ids: tuple[str, ...] | None = None
    captured_index_document: ProductIndexDocument | None = None

    def return_captured_document(_root: Path, _path: RepositoryPath) -> ProductIndexDocument:
        return document

    def capture_repository(
        root: Path,
        selected_project_ids: tuple[str, ...],
        *,
        product_index_document: ProductIndexDocument | None = None,
    ) -> ProductRepository:
        nonlocal captured_root, captured_project_ids, captured_index_document
        captured_root = root
        captured_project_ids = selected_project_ids
        captured_index_document = product_index_document
        return sentinel

    monkeypatch.setattr(release, "read_product_index_document", return_captured_document)
    monkeypatch.setattr(release, "load_repository", capture_repository)
    manifest = ReleaseManifest.model_construct(projects=(), variants=())

    result = release.load_release_repository(ROOT, manifest)

    assert result is sentinel
    assert captured_root == ROOT
    assert captured_project_ids == ()
    assert captured_index_document is document
