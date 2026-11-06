"""Source-bound release board-variant assignments and default states."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.product import load_repository
from kicad_tooling.hwrepo.product_repository_models import ProductRepository
from kicad_tooling.hwrepo.product_source_inputs import ProductFileIdentity, ProductSourceIdentity
from kicad_tooling.hwrepo.release_board_variant_selection import (
    ReleaseBoardVariantChoice,
    ReleaseBoardVariantSelection,
    ReleaseBoardVariantSource,
    project_board_variant_names,
    require_release_board_variant_sources_current,
    resolve_release_board_variants,
)
from kicad_tooling.hwrepo.release_contract_models import ReleaseVariant
from tests.support import reference_root


def _repository(
    root: Path,
    board_variants: dict[str, str] | None = None,
    *,
    include_source: bool = True,
) -> ProductRepository:
    captured = load_repository(reference_root())
    original = captured.products[0]
    selected_variant = original.variants[0].model_copy(
        update={"board_variants": board_variants or {}}
    )
    product = original.model_copy(update={"variants": (selected_variant, *original.variants[1:])})
    path = root / "products" / f"{product.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_model(path, product)
    content = path.read_bytes()
    source_path = path.relative_to(root).as_posix()
    sources = (
        {
            product.id: ProductSourceIdentity(
                record=product,
                path=source_path,
                sha256=hashlib.sha256(content).hexdigest(),
            )
        }
        if include_source
        else {}
    )
    return ProductRepository(
        products=(product,),
        product_project_ids={product.id: captured.product_project_ids[product.id]},
        parts=captured.parts,
        interfaces=captured.interfaces,
        projects=captured.projects,
        product_sources=sources,
        issues=(),
    )


def _selection(repository: ProductRepository, variant_index: int = 0) -> ReleaseVariant:
    product = repository.products[0]
    variant = product.variants[variant_index]
    return ReleaseVariant(
        product=product.id,
        product_revision=product.revision,
        variant=variant.id,
        variant_revision=variant.revision,
    )


def test_resolver_keeps_assignment_provenance_and_explicit_project_default(
    tmp_path: Path,
) -> None:
    project_id = "arduino-uno-status-led"
    repository = _repository(tmp_path, {project_id: "Pilot A"})
    selection = _selection(repository)

    resolution = resolve_release_board_variants(
        repository, (selection,), (project_id, "another-selected-project")
    )

    assigned = resolution.for_project(project_id)
    assert assigned == ReleaseBoardVariantChoice(
        project_id=project_id,
        state="ASSIGNED",
        variant_name="Pilot A",
        assigned_by=(resolution.selected_sources[0],),
    )
    assert assigned.assigned_by[0].selection == selection
    assert assigned.assigned_by[0].product_source.path == (
        f"products/{repository.products[0].id}.json"
    )
    assert (
        assigned.assigned_by[0].product_source.sha256
        == hashlib.sha256(
            (tmp_path / assigned.assigned_by[0].product_source.path).read_bytes()
        ).hexdigest()
    )
    assert resolution.for_project("another-selected-project") == ReleaseBoardVariantChoice(
        project_id="another-selected-project",
        state="DEFAULT",
        variant_name=None,
    )
    require_release_board_variant_sources_current(tmp_path, resolution)


def test_default_state_retains_selected_product_source_and_legacy_map_stays_empty(
    tmp_path: Path,
) -> None:
    project_id = "arduino-uno-status-led"
    repository = _repository(tmp_path)
    selection = _selection(repository)

    resolution = resolve_release_board_variants(repository, (selection,), (project_id,))

    assert resolution.for_project(project_id).state == "DEFAULT"
    assert len(resolution.selected_sources) == 1
    assert project_board_variant_names(repository.products, (selection,), (project_id,)) == {}


def test_source_freshness_rejects_product_bytes_changed_after_resolution(
    tmp_path: Path,
) -> None:
    project_id = "arduino-uno-status-led"
    repository = _repository(tmp_path, {project_id: "Pilot A"})
    resolution = resolve_release_board_variants(
        repository, (_selection(repository),), (project_id,)
    )
    source_path = tmp_path / resolution.selected_sources[0].product_source.path
    source_path.write_bytes(source_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="changed during operation"):
        require_release_board_variant_sources_current(tmp_path, resolution)


def test_resolver_rejects_missing_source_and_stale_selection_revision(tmp_path: Path) -> None:
    project_id = "arduino-uno-status-led"
    repository = _repository(tmp_path, include_source=False)

    with pytest.raises(ValueError, match="no captured source"):
        resolve_release_board_variants(repository, (_selection(repository),), (project_id,))

    stale = _selection(repository).model_copy(update={"product_revision": "stale"})
    with pytest.raises(ValueError, match="product revision is stale"):
        resolve_release_board_variants(_repository(tmp_path), (stale,), (project_id,))


def test_conflicting_selected_variants_keep_the_existing_rejection(tmp_path: Path) -> None:
    project_id = "arduino-uno-status-led"
    repository = _repository(tmp_path, {project_id: "Pilot A"})
    product = repository.products[0]
    second = product.variants[1].model_copy(update={"board_variants": {project_id: "Pilot B"}})
    edited = product.model_copy(update={"variants": (product.variants[0], second)})
    source_path = tmp_path / f"products/{product.id}.json"
    write_model(source_path, edited)
    content = source_path.read_bytes()
    updated = ProductRepository(
        products=(edited,),
        product_project_ids=repository.product_project_ids,
        parts=repository.parts,
        interfaces=repository.interfaces,
        projects=repository.projects,
        product_sources={
            edited.id: ProductSourceIdentity(
                record=edited,
                path=source_path.relative_to(tmp_path).as_posix(),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        },
        issues=(),
    )

    with pytest.raises(ValueError, match="Conflicting KiCad assembly variants"):
        resolve_release_board_variants(
            updated,
            (_selection(updated, 0), _selection(updated, 1)),
            (project_id,),
        )


def test_selection_model_requires_assignment_source_identity_match(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    selection = _selection(repository)
    product = repository.products[0]
    captured = repository.product_sources[product.id]
    source = ReleaseBoardVariantSource(
        selection=selection,
        product_source=ProductFileIdentity(path=captured.path, sha256=captured.sha256),
    )
    mismatched_source = ReleaseBoardVariantSource(
        selection=selection,
        product_source=ProductFileIdentity(path=captured.path, sha256="b" * 64),
    )

    with pytest.raises(ValueError, match="differs from its selected source identity"):
        ReleaseBoardVariantSelection(
            projects=(
                ReleaseBoardVariantChoice(
                    project_id="board",
                    state="ASSIGNED",
                    variant_name="Pilot A",
                    assigned_by=(mismatched_source,),
                ),
            ),
            selected_sources=(source,),
        )
