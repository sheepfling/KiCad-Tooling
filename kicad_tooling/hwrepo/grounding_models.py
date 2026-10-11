"""Typed contracts for explicitly reviewed ground domains and return exceptions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class GroundDomain(StrictModel):
    net: NetName
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]


class GroundingAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    domains: Annotated[tuple[GroundDomain, ...], Field(min_length=1)]
    exempt_components: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)
    reviewed_return_exceptions: Mapping[NetName, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def distinct_domains(self) -> GroundingAnalysis:
        names = [domain.net for domain in self.domains]
        pins = [pin for domain in self.domains for pin in domain.pins]
        if len(set(names)) != len(names) or len(set(pins)) != len(pins):
            raise ValueError("Ground domains and their pins must be unique")
        if any(name.startswith("/") for name in (*names, *self.reviewed_return_exceptions)):
            raise ValueError("Use net names without the leading slash, as in the native contract")
        if set(names) & set(self.reviewed_return_exceptions):
            raise ValueError("A return net cannot be both a ground domain and an exception")
        return self
