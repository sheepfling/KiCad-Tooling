"""Compare contact connectivity across raster-grid phases."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fabrication_connectivity_raster import RasterAnalysis


def different_raster_contact_partitions(
    reference: RasterAnalysis, candidate: RasterAnalysis
) -> tuple[str, ...]:
    """Return contacts whose copper-island memberships vary between raster phases."""
    reference_groups, reference_missing = _contact_partition(reference)
    candidate_groups, candidate_missing = _contact_partition(candidate)
    labels = set(reference_groups) | set(candidate_groups) | reference_missing | candidate_missing
    return tuple(
        sorted(
            label
            for label in labels
            if reference_groups.get(label, ()) != candidate_groups.get(label, ())
            or (label in reference_missing) != (label in candidate_missing)
        )
    )


def _contact_partition(
    analysis: RasterAnalysis,
) -> tuple[dict[str, tuple[tuple[str, ...], ...]], set[str]]:
    component_contacts: dict[int, set[str]] = {}
    contact_components: dict[str, list[int]] = {}
    no_copper = {f"{contact.net}:{contact.label}" for contact in analysis.no_copper}
    for assignment in analysis.assignments:
        label = f"{assignment.contact.net}:{assignment.contact.label}"
        roots = contact_components.setdefault(label, [])
        for component in assignment.components:
            roots.append(component)
            component_contacts.setdefault(component, set()).add(label)
    partitions = {
        label: tuple(
            sorted(
                {
                    tuple(sorted(component_contacts[root]))
                    for root in roots
                    if root in component_contacts
                }
            )
        )
        for label, roots in contact_components.items()
    }
    return partitions, no_copper
