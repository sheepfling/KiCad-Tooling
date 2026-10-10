"""Resolve project-authored roles for exact custom component identities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from .models import ComponentRoleBinding, ComponentRoleMap, NetlistContract


@dataclass(frozen=True)
class ComponentRoleResolution:
    """Exact mapped component identities and any stale project declarations."""

    by_reference: Mapping[str, ComponentRoleBinding]
    issues: tuple[str, ...]


def component_role_binding_digest(binding: ComponentRoleBinding) -> str:
    """Return a stable digest for the complete reviewed identity and basis."""
    payload = binding.model_dump(mode="json")
    payload["pins"] = sorted(
        payload["pins"], key=lambda item: (item["number"].casefold(), item["number"])
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def component_role_binding_evidence(
    binding: ComponentRoleBinding,
) -> dict[str, tuple[str, ...]]:
    """Format the exact authored role identity used to classify a finding."""
    pins = tuple(
        f"{pin.number}={pin.function}/{pin.electrical_type}"
        for pin in sorted(binding.pins, key=lambda item: (item.number.casefold(), item.number))
    )
    return {
        "classified_role": (binding.role,),
        "role_part_id": (binding.part_id,),
        "role_symbol": (binding.symbol,),
        "role_footprint": (binding.footprint,),
        "role_pin_inventory": pins,
        "role_basis": (binding.basis,),
        "role_binding_sha256": (component_role_binding_digest(binding),),
    }


def resolve_component_role_map(
    observed: NetlistContract, role_map: ComponentRoleMap | None
) -> ComponentRoleResolution:
    """Resolve only exact project-authored part, symbol, footprint and pin identities."""
    if role_map is None:
        return ComponentRoleResolution(by_reference={}, issues=())

    components = {reference.casefold(): item for reference, item in observed.components.items()}
    references_by_part_id: dict[str, list[str]] = {}
    for reference, component in observed.components.items():
        if component.part_id is not None:
            references_by_part_id.setdefault(component.part_id, []).append(reference)
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    pin_types = {pin.casefold(): value for pin, value in observed.pin_electrical_types.items()}

    resolved: dict[str, ComponentRoleBinding] = {}
    issues: list[str] = []
    for binding in sorted(
        role_map.entries, key=lambda item: (item.part_id.casefold(), item.part_id)
    ):
        references = tuple(
            sorted(
                references_by_part_id.get(binding.part_id, ()),
                key=lambda item: (item.casefold(), item),
            )
        )
        if not references:
            issues.append(
                f"Component role map for PART_ID {binding.part_id!r} is stale: "
                "no native component uses this exact PART_ID."
            )
            continue

        expected_pins = tuple(
            sorted(binding.pins, key=lambda item: (item.number.casefold(), item.number))
        )
        for reference in references:
            key = reference.casefold()
            component = components[key]
            actual_symbol = symbols.get(key)
            if actual_symbol != binding.symbol:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    f"native symbol is {actual_symbol or '<missing>'!r}, "
                    f"expected {binding.symbol!r}."
                )
                continue
            if component.footprint != binding.footprint:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    f"native footprint is {component.footprint or '<missing>'!r}, "
                    f"expected {binding.footprint!r}."
                )
                continue

            actual_numbers = inventories.get(key, ())
            actual_pins = tuple(
                (
                    number,
                    pin_functions.get(f"{reference}.{number}".casefold()),
                    pin_types.get(f"{reference}.{number}".casefold()),
                )
                for number in actual_numbers
            )
            expected_signature = tuple(
                (item.number, item.function, item.electrical_type.casefold())
                for item in expected_pins
            )
            actual_signature = tuple(
                (number, function, electrical_type.casefold() if electrical_type else None)
                for number, function, electrical_type in sorted(
                    actual_pins, key=lambda item: (item[0].casefold(), item[0])
                )
            )
            if actual_signature != expected_signature:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    "the complete native pin number, function, and electrical-type inventory "
                    "does not match."
                )
                continue
            resolved[key] = binding
    return ComponentRoleResolution(by_reference=resolved, issues=tuple(issues))
