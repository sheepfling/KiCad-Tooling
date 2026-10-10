"""Exact project-authored component bonds between reference domains."""

from __future__ import annotations

from pydantic import model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class ReferenceBondRequirement(StrictModel):
    """One exact fitted two-pin component mapped between distinct reference nets."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    side_a_pin: Reference
    side_b_pin: Reference
    side_a_net: NetName
    side_b_net: NetName

    @model_validator(mode="after")
    def component_sides_are_distinct(self) -> ReferenceBondRequirement:
        if self.side_a_net.casefold() == self.side_b_net.casefold():
            raise ValueError("USB reference bonds must span distinct schematic nets")
        if self.side_a_pin.casefold() == self.side_b_pin.casefold():
            raise ValueError("USB reference-bond sides must use distinct pins")
        for pin in (self.side_a_pin, self.side_b_pin):
            if "." not in pin or pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("USB reference-bond pins must belong to the declared component")
        return self
