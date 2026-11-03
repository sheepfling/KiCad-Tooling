"""Reconcile one native variant netlist against its fitted PCB positions."""

from __future__ import annotations

from .cross_probe_variant import VariantObservation
from .models import PurchasingComponent
from .variant_parts_review_models import VariantPopulationIssue


def reconcile_variant_population(
    observed: VariantObservation,
    native_components: tuple[PurchasingComponent, ...],
) -> tuple[tuple[PurchasingComponent, ...], tuple[VariantPopulationIssue, ...]]:
    """Keep only uniquely reconciled fitted parts and valid native exclusions."""
    accepted: list[PurchasingComponent] = []
    unresolved: list[VariantPopulationIssue] = []
    seen: set[str] = set()
    for component in native_components:
        key = component.reference.casefold()
        if key in seen:
            raise ValueError("Named variant netlist has duplicate case-insensitive references")
        seen.add(key)
        source = observed.schematic.get(key)
        if (
            source is None
            or source.part_id != component.part_id
            or source.value != component.value
            or source.footprint != component.footprint
            or (key in observed.schematic_dnp) != component.dnp
        ):
            raise ValueError(f"Named variant parsers disagree on {component.reference}")
        if component.dnp or component.exclude_from_bom:
            if key in observed.board_fitted:
                unresolved.append(
                    VariantPopulationIssue(
                        reference=component.reference,
                        reason="PCB fits a schematic DNP or BOM-excluded component.",
                    )
                )
            else:
                accepted.append(component)
            continue
        if key not in observed.board_fitted:
            unresolved.append(
                VariantPopulationIssue(
                    reference=component.reference,
                    reason="Fitted schematic component has no fitted PCB position.",
                )
            )
        elif (
            not component.footprint.strip() or not component.value.strip() or not component.part_id
        ):
            unresolved.append(
                VariantPopulationIssue(
                    reference=component.reference,
                    reason="Fitted component lacks a footprint, value, or PART_ID.",
                )
            )
        else:
            accepted.append(component)
    if seen != observed.schematic.keys():
        raise ValueError("Named variant parsers disagree on schematic population")
    for key in sorted(observed.board_fitted - seen):
        unresolved.append(
            VariantPopulationIssue(
                reference=observed.board_all[key],
                reason="Fitted PCB reference is absent from the variant schematic netlist.",
            )
        )
    return tuple(accepted), tuple(sorted(unresolved, key=lambda item: item.reference.casefold()))
