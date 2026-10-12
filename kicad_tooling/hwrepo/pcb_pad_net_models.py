"""Typed findings for schematic-to-PCB pad net assignment comparison."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Identifier, NonEmptyText, StrictModel


class PcbSchematicBoardPadNetMismatch(StrictModel):
    """One schematic pin and its corresponding PCB pad have different net state."""

    reference: Identifier
    pin: NonEmptyText
    mismatch: Literal[
        "board_pad_missing",
        "board_pad_unassigned",
        "net_assignment_differs",
        "schematic_unconnected_board_assigned",
    ]
    schematic_net: NonEmptyText | None
    board_net: NonEmptyText | None

    @model_validator(mode="after")
    def net_state_matches_mismatch(self) -> PcbSchematicBoardPadNetMismatch:
        if self.mismatch == "board_pad_missing" or self.mismatch == "board_pad_unassigned":
            valid = self.schematic_net is not None and self.board_net is None
        elif self.mismatch == "net_assignment_differs":
            valid = self.schematic_net is not None and self.board_net is not None
        else:
            valid = self.schematic_net is None and self.board_net is not None
        if not valid:
            raise ValueError("PCB pad net mismatch kind does not match its observed net state")
        if self.mismatch == "net_assignment_differs" and self.schematic_net == self.board_net:
            raise ValueError("Matching PCB pad nets cannot be reported as a mismatch")
        return self
