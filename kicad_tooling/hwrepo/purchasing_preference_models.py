"""Project purchasing preferences and their source-write result."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NonNegativeCount,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)


class PurchasingSchemaModel(StrictModel):
    schema_version: Literal["1"] = "1"

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema_version(cls, value: object) -> str:
        if value != "1":
            raise ValueError("Unsupported purchasing schema version")
        return "1"


class PurchasingPreferences(PurchasingSchemaModel):
    """User-selected quantities and exact supplier IDs; no sourcing authority."""

    boards: PositiveCount = 1
    spare_percent: Annotated[int, Field(ge=0, le=100)] = 0
    spare_minimum: NonNegativeCount = 0
    digikey_skus: Mapping[Identifier, Annotated[str, StringConstraints(min_length=1)]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def exact_supplier_identifiers(self) -> PurchasingPreferences:
        for identifier in self.digikey_skus.values():
            if identifier != identifier.strip() or any(
                ord(character) < 32 or ord(character) == 127 for character in identifier
            ):
                raise ValueError(
                    "DigiKey identifiers must be exact text without padding or control characters"
                )
        return self


class McpPurchasingPreferencesResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    status: Literal["CREATED", "UPDATED"]
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest | None = None
    after_sha256: Digest
    readback_sha256: Digest
    preferences: PurchasingPreferences
