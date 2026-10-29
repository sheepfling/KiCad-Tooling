"""Authored parts catalog records and their reusable CAD bindings."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import StringConstraints, model_validator

from .model_primitives import Identifier, NonEmptyText, RepositoryPath, StrictModel


class PartStatus(str, Enum):
    TRAINING = "not_for_manufacture"
    APPROVED = "approved"


class PartCadBinding(StrictModel):
    """Reviewed symbol, value, package and source model for one catalog part."""

    symbol_id: NonEmptyText
    value: NonEmptyText
    footprint: Annotated[str, StringConstraints(pattern=r"^[^:\r\n]+:[^:\r\n]+$")]
    model: RepositoryPath
    digikey_sku: Annotated[str, StringConstraints(min_length=1)] | None = None

    @model_validator(mode="after")
    def exact_sku(self) -> PartCadBinding:
        if self.digikey_sku is not None and (
            self.digikey_sku != self.digikey_sku.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in self.digikey_sku)
        ):
            raise ValueError("DigiKey SKU must be exact text without padding or control characters")
        return self


class PartRecord(StrictModel):
    id: Identifier
    revision: Identifier
    description: NonEmptyText
    part_class: NonEmptyText
    unit: Literal["each"]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    datasheet_url: NonEmptyText
    lifecycle: NonEmptyText
    status: PartStatus
    approved_alternates: tuple[Identifier, ...] = ()
    cad: PartCadBinding | None = None


class PartsCatalog(StrictModel):
    schema_version: NonEmptyText
    parts: tuple[PartRecord, ...]
