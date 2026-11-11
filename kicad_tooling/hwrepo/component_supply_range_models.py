"""Project-authored operating voltage ranges for exact IC supply pins."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    Reference,
    StrictModel,
)


class ComponentSupplyVoltageRangeRequirement(StrictModel):
    """Reviewed operating range and identity for one exact native supply pin."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pin: Reference
    expected_pin_function: NonEmptyText
    minimum_voltage_v: FiniteMeasure
    maximum_voltage_v: FiniteMeasure
    range_source: NonEmptyText
    range_conditions: NonEmptyText

    @model_validator(mode="after")
    def exact_supply_pin_and_ordered_range(self) -> ComponentSupplyVoltageRangeRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Supply-range pin must belong to its declared component")
        if self.minimum_voltage_v > self.maximum_voltage_v:
            raise ValueError("Supply operating range minimum must not exceed its maximum")
        return self


class ComponentSupplyVoltageRangeMap(StrictModel):
    """Exact project-selected IC supply pins and their reviewed operating ranges."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[ComponentSupplyVoltageRangeRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements_and_pins(self) -> ComponentSupplyVoltageRangeMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Supply-range requirement IDs must be unique")
        if len({item.pin.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each supply pin may have only one operating-range requirement")
        component_identities: dict[str, tuple[str, str, str]] = {}
        for requirement in self.requirements:
            key = requirement.reference.casefold()
            identity = (
                requirement.expected_symbol,
                requirement.expected_footprint,
                requirement.expected_part_id,
            )
            previous = component_identities.setdefault(key, identity)
            if previous != identity:
                raise ValueError(
                    "Supply-range requirements for one component must use consistent identity"
                )
        return self


def component_supply_voltage_range_map_sha256(
    requirements: ComponentSupplyVoltageRangeMap,
) -> Digest:
    """Return the digest used to bind findings to the exact authored map."""
    payload = requirements.model_dump(mode="json")
    payload["requirements"] = sorted(
        payload["requirements"], key=lambda item: (item["id"].casefold(), item["id"])
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
