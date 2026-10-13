"""Typed results for PCB references with no schematic component counterpart."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Identifier, NonEmptyText, StrictModel


class PcbBoardOnlyFootprint(StrictModel):
    """A native PCB footprint whose reference is absent from the schematic netlist."""

    reference: Identifier
    footprint: NonEmptyText


class PcbBoardOnlyFootprintCoverage(StrictModel):
    """Opt-in coverage state and review candidates for board-only references."""

    status: Literal["COMPLETE", "BLOCKED", "DISABLED"] = "DISABLED"
    mode: Literal["review", "block", "off"] = "off"
    footprints: tuple[PcbBoardOnlyFootprint, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_board_only_coverage(self) -> PcbBoardOnlyFootprintCoverage:
        references = [item.reference.casefold() for item in self.footprints]
        if len(references) != len(set(references)):
            raise ValueError("Board-only PCB footprint references must be unique")
        if self.status == "COMPLETE":
            if self.mode == "off" or self.issue is not None:
                raise ValueError("Complete board-only coverage needs an active mode and no issue")
        elif self.status == "BLOCKED":
            if self.mode == "off" or self.issue is None or self.footprints:
                raise ValueError("Blocked board-only coverage needs an active mode and issue")
        elif self.mode != "off" or self.issue is not None or self.footprints:
            raise ValueError("Disabled board-only coverage cannot contain findings or issues")
        return self
