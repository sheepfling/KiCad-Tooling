"""Typed project-selection helpers for local and hosted automation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_registry
from .models import ProductIndex, ProjectRecord, ProjectRegistry


@dataclass(frozen=True)
class ProjectSelector:
    """OR-match project IDs, tags, and product members, then exclude tags."""

    project_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    excluded_tags: tuple[str, ...] = ()
    product_ids: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self.project_ids or self.tags or self.excluded_tags or self.product_ids)


def duplicate_values(values: tuple[str, ...], label: str) -> None:
    duplicates = {
        value
        for value in values
        if sum(candidate.casefold() == value.casefold() for candidate in values) > 1
    }
    if duplicates:
        raise ValueError(f"Duplicate {label}: {sorted(duplicates)}")


def select_projects(
    registry: ProjectRegistry,
    selector: ProjectSelector,
    product_index: ProductIndex | None = None,
) -> tuple[ProjectRecord, ...]:
    """Resolve deterministic project selection without scanning CAD sources."""
    duplicate_values(selector.project_ids, "project IDs")
    duplicate_values(selector.tags, "included tags")
    duplicate_values(selector.excluded_tags, "excluded tags")
    duplicate_values(selector.product_ids, "product IDs")
    available = {project.id: project for project in registry.projects}
    unknown = sorted(set(selector.project_ids) - set(available))
    if unknown:
        raise ValueError(f"Unknown project IDs: {unknown}")
    available_tags = {tag for project in registry.projects for tag in project.tags}
    unknown_tags = sorted(set(selector.tags) - available_tags)
    if unknown_tags:
        raise ValueError(f"Unknown included tags: {unknown_tags}")
    unknown_exclusions = sorted(set(selector.excluded_tags) - available_tags)
    if unknown_exclusions:
        raise ValueError(f"Unknown excluded tags: {unknown_exclusions}")
    product_members: set[str] = set()
    if selector.product_ids:
        if product_index is None:
            raise ValueError("Product selection requires catalog/products.json")
        indexed: dict[str, tuple[str, ...]] = {}
        for product in product_index.products:
            if product.id.casefold() in indexed:
                raise ValueError(f"Duplicate product ID in index: {product.id}")
            indexed[product.id.casefold()] = product.project_ids
        unknown_products = sorted(set(selector.product_ids) - {product.id for product in product_index.products})
        if unknown_products:
            raise ValueError(f"Unknown product IDs: {unknown_products}")
        for product_id in selector.product_ids:
            members = indexed[product_id.casefold()]
            duplicate_values(members, f"project IDs for product {product_id}")
            missing = sorted(set(members) - set(available))
            if missing:
                raise ValueError(f"Product {product_id} references unknown project IDs: {missing}")
            product_members.update(members)
    include_tags = frozenset(selector.tags)
    excluded_tags = frozenset(selector.excluded_tags)
    has_inclusions = bool(selector.project_ids or selector.tags or selector.product_ids)
    selected = tuple(
        project
        for project in registry.projects
        if (
            not has_inclusions
            or project.id in selector.project_ids
            or bool(include_tags & frozenset(project.tags))
            or project.id in product_members
        )
        and not (excluded_tags & frozenset(project.tags))
    )
    if not selected:
        raise ValueError("No projects matched the requested IDs/tags/products after exclusions")
    return selected


def resolve_project_ids(root: Path, selector: ProjectSelector) -> tuple[str, ...]:
    """Load the authoritative registry and return selected project identities."""
    registry = load_registry(root)
    product_index = (
        read_model(repo_path(root, "catalog/products.json"), ProductIndex)
        if selector.product_ids else None
    )
    return tuple(project.id for project in select_projects(registry, selector, product_index))
