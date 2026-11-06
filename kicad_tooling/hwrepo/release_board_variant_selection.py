"""Resolve product board variants with their exact product-source identity."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .product_models import ProductRecord
from .product_repository_models import ProductRepository
from .product_source_inputs import ProductFileIdentity, require_product_file_current
from .release_contract_models import ReleaseVariant

ReleaseBoardVariantState = Literal["DEFAULT", "ASSIGNED"]


@dataclass(frozen=True, slots=True)
class ReleaseBoardVariantSource:
    """One explicit product selection bound to its captured product-file bytes."""

    selection: ReleaseVariant
    product_source: ProductFileIdentity


@dataclass(frozen=True, slots=True)
class ReleaseBoardVariantChoice:
    """Board export choice for one selected project, including default semantics."""

    project_id: str
    state: ReleaseBoardVariantState
    variant_name: str | None
    assigned_by: tuple[ReleaseBoardVariantSource, ...] = ()

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("Release board-variant choices require a project identity")
        if self.state == "ASSIGNED":
            if not self.variant_name or not self.assigned_by:
                raise ValueError("Assigned board variants require a name and source selections")
            if any(not item.selection.product for item in self.assigned_by):
                raise ValueError("Board variant sources must identify their product")
        elif self.state == "DEFAULT":
            if self.variant_name is not None or self.assigned_by:
                raise ValueError("Default board variants cannot carry an authored assignment")
        else:
            raise ValueError(f"Unsupported release board-variant state {self.state!r}")


@dataclass(frozen=True, slots=True)
class ReleaseBoardVariantSelection:
    """Source-bound choices for every project in one release scope.

    ``DEFAULT`` means no selected product variant assigns an assembly variant
    to that project, so native export uses the project's configured default.
    ``selected_sources`` also retains product sources that contributed no
    assignment, making that absence interpretable against the captured inputs.
    """

    projects: tuple[ReleaseBoardVariantChoice, ...]
    selected_sources: tuple[ReleaseBoardVariantSource, ...]

    def __post_init__(self) -> None:
        if not self.projects:
            raise ValueError("Release board-variant selection requires a project scope")
        project_ids = tuple(choice.project_id for choice in self.projects)
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("Release board-variant choices must have unique projects")
        selection_keys = tuple(_selection_key(item.selection) for item in self.selected_sources)
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("Release board-variant sources must have unique selections")
        selected_by_key = {_selection_key(item.selection): item for item in self.selected_sources}
        for choice in self.projects:
            for source in choice.assigned_by:
                selected = selected_by_key.get(_selection_key(source.selection))
                if selected != source:
                    raise ValueError(
                        "Board variant assignment differs from its selected source identity"
                    )

    def for_project(self, project_id: str) -> ReleaseBoardVariantChoice:
        """Return the explicit assigned/default choice for one selected project."""
        for choice in self.projects:
            if choice.project_id == project_id:
                return choice
        raise KeyError(f"Project {project_id!r} is outside the release board-variant scope")


@dataclass(frozen=True, slots=True)
class _BoardVariantAssignment:
    project_id: str
    variant_name: str
    selections: tuple[ReleaseVariant, ...]


def _selection_key(selection: ReleaseVariant) -> tuple[str, str, str, str]:
    return (
        selection.product,
        selection.product_revision,
        selection.variant,
        selection.variant_revision,
    )


def _collect_assignments(
    products: tuple[ProductRecord, ...],
    selections: tuple[ReleaseVariant, ...],
    project_ids: tuple[str, ...],
) -> tuple[_BoardVariantAssignment, ...]:
    """Apply the established scope/conflict rules before projecting any map."""
    indexed = {product.id: product for product in products}
    allowed = set(project_ids)
    names: dict[str, str] = {}
    origins: dict[str, list[ReleaseVariant]] = {}
    for selection in selections:
        product = indexed.get(selection.product)
        if product is None:
            continue  # The release selection validator owns unknown-product findings.
        variant = next((item for item in product.variants if item.id == selection.variant), None)
        if variant is None:
            continue  # The release selection validator owns unknown-variant findings.
        for project_id, name in variant.board_variants.items():
            if project_id not in allowed:
                raise ValueError(
                    f"{selection.product}:{selection.variant} maps unselected board {project_id}"
                )
            previous = names.get(project_id)
            if previous is not None and previous != name:
                raise ValueError(
                    f"Conflicting KiCad assembly variants for {project_id}: "
                    f"{previous} and {name}; prepare separate candidates"
                )
            names[project_id] = name
            origins.setdefault(project_id, []).append(selection)
    return tuple(
        _BoardVariantAssignment(
            project_id=project_id,
            variant_name=names[project_id],
            selections=tuple(origins[project_id]),
        )
        for project_id in sorted(names)
    )


def project_board_variant_names(
    products: Iterable[ProductRecord],
    selections: tuple[ReleaseVariant, ...],
    project_ids: Iterable[str],
) -> dict[str, str]:
    """Compatibility projection of explicit assignments for existing callers."""
    assignments = _collect_assignments(tuple(products), selections, tuple(project_ids))
    return {item.project_id: item.variant_name for item in assignments}


def resolve_release_board_variants(
    repository: ProductRepository,
    selections: tuple[ReleaseVariant, ...],
    project_ids: Iterable[str],
) -> ReleaseBoardVariantSelection:
    """Bind selected export choices and default states to captured product sources."""
    if repository.issues:
        raise ValueError(
            f"Cannot resolve board variants from an invalid repository: {repository.issues}"
        )
    projects = tuple(project_ids)
    if not projects or len(projects) != len(set(projects)):
        raise ValueError("Release board-variant scope must contain unique selected projects")

    products = {product.id: product for product in repository.products}
    sources_by_key: dict[tuple[str, str, str, str], ReleaseBoardVariantSource] = {}
    for selection in selections:
        key = _selection_key(selection)
        if key in sources_by_key:
            raise ValueError("Duplicate product/variant selection")
        product = products.get(selection.product)
        if product is None:
            raise ValueError(f"Unknown selected product {selection.product!r}")
        if product.revision != selection.product_revision:
            raise ValueError(f"Selected product revision is stale: {selection.product}")
        source = repository.product_sources.get(product.id)
        if source is None:
            raise ValueError(f"Selected product has no captured source: {product.id}")
        if source.record != product:
            raise ValueError(f"Selected product differs from its captured source: {product.id}")
        variant = next((item for item in product.variants if item.id == selection.variant), None)
        if variant is None:
            raise ValueError(f"Unknown selected variant {selection.variant!r} for {product.id!r}")
        if variant.revision != selection.variant_revision:
            raise ValueError(f"Selected variant revision is stale: {product.id}:{variant.id}")
        sources_by_key[key] = ReleaseBoardVariantSource(
            selection=selection,
            product_source=ProductFileIdentity(path=source.path, sha256=source.sha256),
        )

    assignments = _collect_assignments(tuple(repository.products), selections, projects)
    assignment_by_project = {item.project_id: item for item in assignments}
    choices: list[ReleaseBoardVariantChoice] = []
    for project_id in projects:
        assignment = assignment_by_project.get(project_id)
        if assignment is None:
            choices.append(
                ReleaseBoardVariantChoice(
                    project_id=project_id,
                    state="DEFAULT",
                    variant_name=None,
                )
            )
            continue
        choices.append(
            ReleaseBoardVariantChoice(
                project_id=project_id,
                state="ASSIGNED",
                variant_name=assignment.variant_name,
                assigned_by=tuple(
                    sources_by_key[_selection_key(selection)] for selection in assignment.selections
                ),
            )
        )
    return ReleaseBoardVariantSelection(
        projects=tuple(choices),
        selected_sources=tuple(sources_by_key.values()),
    )


def require_release_board_variant_sources_current(
    root: Path,
    resolution: ReleaseBoardVariantSelection,
) -> None:
    """Require every product file behind assigned and default choices to stay current."""
    identities = {
        (source.product_source.path, source.product_source.sha256): source.product_source
        for source in resolution.selected_sources
    }
    for identity in identities.values():
        require_product_file_current(root, identity)
