"""Typed request and response contracts for the DigiKey supplier API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel, StringConstraints

from .model_primitives import NonEmptyText, PositiveCount, StrictModel


class DigiKeyHandoffQuantity(StrictModel):
    quantity: PositiveCount


class DigiKeyHandoffPart(StrictModel):
    requested_part_number: Annotated[NonEmptyText, Field(alias="requestedPartNumber")]
    quantities: Annotated[tuple[DigiKeyHandoffQuantity, ...], Field(min_length=1)]
    customer_reference: Annotated[str, Field(alias="customerReference")]
    notes: str


class DigiKeyHandoffPayload(RootModel[tuple[DigiKeyHandoffPart, ...]]):
    """DigiKey's third-party API accepts a root array of order lines."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffUrl(RootModel[str]):
    """DigiKey returns a JSON string, validated as an allowed URL by the adapter."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffReply(StrictModel):
    single_use_url: Annotated[
        str,
        StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
    ]


class DigiKeyHandoffResult(StrictModel):
    status: Literal["READY", "BLOCKED", "ERROR"]
    single_use_url: str | None = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False
