"""Typed source identities for outer-surface PCB drill openings."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import StringConstraints, model_validator

from .model_primitives import (
    Digest,
    NonEmptyText,
    PositiveCount,
    Reference,
    StrictModel,
)

PcbDrillHolePadUuid = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
]


class PcbDrillHoleObservation(StrictModel):
    """One fitted pad or via drill opening available from an outer PCB surface."""

    id: NonEmptyText
    kind: Literal["pad", "via"]
    pad: Reference | None = None
    pad_uuid: PcbDrillHolePadUuid | None = None
    via_id: Digest | None = None
    footprint_reference: Reference | None = None
    footprint: NonEmptyText | None = None
    position_nm: tuple[int, int]
    drill_size_nm: tuple[PositiveCount, PositiveCount]
    shape: Literal["circle", "oval", "other"]
    surfaces: tuple[Literal["front", "back"], ...]

    @model_validator(mode="after")
    def complete_identity(self) -> PcbDrillHoleObservation:
        if not self.surfaces or len(set(self.surfaces)) != len(self.surfaces):
            raise ValueError("Native drill-hole surfaces must be nonempty and unique")
        if self.kind == "pad":
            if (
                self.pad_uuid is None
                or self.via_id is not None
                or self.footprint_reference is None
                or self.footprint is None
            ):
                raise ValueError("Native pad drill hole needs its UUID and footprint identity")
            if self.id != f"pad:{self.pad_uuid}":
                raise ValueError("Native pad drill-hole ID must match its UUID")
        elif (
            self.via_id is None
            or self.pad is not None
            or self.pad_uuid is not None
            or self.footprint_reference is not None
            or self.footprint is not None
        ):
            raise ValueError("Native via drill hole needs only its canonical via identity")
        elif self.id != f"via:{self.via_id}":
            raise ValueError("Native via drill-hole ID must match its canonical via identity")
        width_nm, height_nm = self.drill_size_nm
        if self.shape == "circle" and width_nm != height_nm:
            raise ValueError("Native circular drill-hole dimensions must be equal")
        return self
