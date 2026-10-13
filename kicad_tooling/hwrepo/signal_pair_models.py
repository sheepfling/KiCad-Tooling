"""Typed aliases for project-reviewed complementary signal pair pins."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field, model_validator

from .model_primitives import NonEmptyText, StrictModel


class ComplementaryPinFunctionAlias(StrictModel):
    """Project-owned pin-function aliases for one exact KiCad symbol pair."""

    symbol: NonEmptyText
    family: NonEmptyText
    positive_functions: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    negative_functions: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    basis: NonEmptyText

    @model_validator(mode="after")
    def unambiguous_function_aliases(self) -> ComplementaryPinFunctionAlias:
        def key(value: str) -> str:
            return re.sub(r"[\s_./]", "", value.casefold()).replace("−", "-")

        positive = tuple(key(value) for value in self.positive_functions)
        negative = tuple(key(value) for value in self.negative_functions)
        if any(not value for value in (*positive, *negative)):
            raise ValueError("Complementary pin-function aliases must contain a letter or symbol")
        if len(set(positive)) != len(positive) or len(set(negative)) != len(negative):
            raise ValueError("Complementary pin-function aliases must be unique within each side")
        if set(positive) & set(negative):
            raise ValueError("A complementary pin-function alias cannot name both pair sides")
        return self


class ComplementaryPinFunctionAliasMap(StrictModel):
    """Opt-in function aliases scoped to exact native KiCad symbol identities."""

    entries: Annotated[tuple[ComplementaryPinFunctionAlias, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_symbols_families_and_functions(self) -> ComplementaryPinFunctionAliasMap:
        identities = tuple((item.symbol, item.family.casefold()) for item in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("Complementary pin-function alias symbol/family pairs must be unique")
        aliases: set[tuple[str, str]] = set()
        for item in self.entries:
            for function in (*item.positive_functions, *item.negative_functions):
                key = re.sub(r"[\s_./]", "", function.casefold()).replace("−", "-")
                identity = (item.symbol, key)
                if identity in aliases:
                    raise ValueError(
                        "A symbol pin-function alias can belong to only one pair family and side"
                    )
                aliases.add(identity)
        return self
