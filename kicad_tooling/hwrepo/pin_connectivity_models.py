"""Typed contracts for exact project-authored relationships between schematic pins."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class PinRelationshipRule(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["common_net", "separate_nets", "assigned", "unconnected"]
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    net: NetName | None = None

    @model_validator(mode="after")
    def valid_relationship(self) -> PinRelationshipRule:
        if len(set(self.pins)) != len(self.pins):
            raise ValueError("Pin relationship pins must be unique")
        if self.topology in {"common_net", "separate_nets"} and len(self.pins) < 2:
            raise ValueError("Connected pin relationships need at least two pins")
        if self.topology != "common_net" and self.net is not None:
            raise ValueError("Only common-net relationships can name one net")
        if self.net is not None and self.net.startswith("/"):
            raise ValueError("Use the native net name without a leading slash")
        return self


class PinConnectivityAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    rules: Annotated[tuple[PinRelationshipRule, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_rules(self) -> PinConnectivityAnalysis:
        identifiers = [rule.id for rule in self.rules]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Pin relationship IDs must be unique")
        return self
