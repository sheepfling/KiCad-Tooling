"""Selected project and catalog dependencies for governance lint."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .discovery import ProjectRegistrySnapshot
from .governance_lint_inputs import GovernanceLintSharedInputs
from .product import load_repository
from .product_models import ProductRecord
from .product_source_inputs import ProductRecordInput
from .project_models import ProjectRecord


@dataclass(frozen=True, slots=True)
class GovernanceLintProjectScope:
    """Project and catalog dependencies selected for one governance run."""

    project_ids: tuple[str, ...]
    selected_records: tuple[ProjectRecord, ...]
    part_ids: frozenset[str]
    interface_ids: frozenset[str]
    library_ids: frozenset[str]
    toolchain_ids: frozenset[str]
    product_record_inputs: tuple[ProductRecordInput, ...]


def resolve_governance_lint_project_scope(
    root: Path,
    selected: Sequence[str] | None,
    requested: tuple[str, ...],
    registry_snapshot: ProjectRegistrySnapshot,
    shared_inputs: GovernanceLintSharedInputs,
) -> GovernanceLintProjectScope:
    """Resolve selected projects, dependent products, and catalog record IDs."""
    project_entries = registry_snapshot.by_id
    project_ids = tuple(project_entries) if selected is None else requested
    selected_records = tuple(
        project_entries[identifier].record
        for identifier in project_ids
        if identifier in project_entries
    )
    parts = shared_inputs.parts_catalog.lookup.by_id
    interfaces = shared_inputs.interfaces_catalog.lookup.by_id
    libraries = shared_inputs.libraries_catalog.lookup.by_id
    toolchains = shared_inputs.toolchains_catalog.lookup.by_id
    product_record_inputs: tuple[ProductRecordInput, ...] = ()

    if selected is None:
        relevant_records = tuple(entry.record for entry in project_entries.values())
        relevant_products: tuple[ProductRecord, ...] = ()
        part_ids = set(parts)
        interface_ids = set(interfaces)
        library_ids = set(libraries)
        toolchain_ids = set(toolchains)
    else:
        # Keep global catalog structure checks separate from selected semantics.
        related = load_repository(
            root,
            requested,
            registry_snapshot=registry_snapshot,
            toolchains_catalog=shared_inputs.toolchains_document.value,
            product_index_document=shared_inputs.product_index,
            parts_catalog=shared_inputs.parts_document.value,
            interfaces_catalog=shared_inputs.interfaces_document.value,
        )
        product_record_inputs = related.record_inputs
        dependent_ids = set(requested)
        selected_ids = frozenset(requested)
        for member_ids in related.product_project_ids.values():
            if not selected_ids.isdisjoint(member_ids):
                dependent_ids.update(member_ids)
        relevant_records = tuple(
            project_entries[identifier].record
            for identifier in sorted(dependent_ids)
            if identifier in project_entries
        )
        relevant_products = related.products
        part_ids = {
            part_id
            for project in relevant_records
            for part_id in project.component_identity.part_ids
        }
        interface_ids = {
            identifier for project in relevant_records for identifier in project.interfaces
        }
        library_ids = {
            identifier for project in relevant_records for identifier in project.library_ids
        }
        toolchain_ids = {
            project_entries[project.id].manifest.toolchain_id for project in relevant_records
        }
        for product in relevant_products:
            interface_ids.update(
                terminal.interface_id
                for terminal in product.terminals
                if terminal.interface_id is not None
            )
            for assembly in product.assemblies:
                if assembly.purchase_part is not None:
                    part_ids.add(assembly.purchase_part)
                part_ids.update(member.item for member in assembly.members if member.item in parts)
        # Approved alternates are real sourcing dependencies of their parts.
        pending = list(part_ids)
        while pending:
            part = parts.get(pending.pop())
            if part is None:
                continue
            for alternate_id in part.approved_alternates:
                if alternate_id not in part_ids:
                    part_ids.add(alternate_id)
                    pending.append(alternate_id)

    return GovernanceLintProjectScope(
        project_ids=project_ids,
        selected_records=selected_records,
        part_ids=frozenset(part_ids),
        interface_ids=frozenset(interface_ids),
        library_ids=frozenset(library_ids),
        toolchain_ids=frozenset(toolchain_ids),
        product_record_inputs=product_record_inputs,
    )
