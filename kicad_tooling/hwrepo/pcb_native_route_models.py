"""Typed native PCB route results shared by route-oriented checks."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import NativePcbUuid, NonNegativeCount, PositiveCount, StrictModel


class PcbNativeRoutePath(StrictModel):
    """One exact, unambiguous native pad-to-pad copper route measurement."""

    status: Literal["RESOLVED", "INCOMPLETE"]
    track_uuids: tuple[NativePcbUuid, ...] = ()
    track_geometry_kinds: tuple[Literal["segment", "arc"], ...] = ()
    track_midpoints_nm: tuple[tuple[int, int] | None, ...] = ()
    track_lengths_nm: tuple[PositiveCount | None, ...] = ()
    vertices_nm: tuple[tuple[int, int], ...] = ()
    length_nm: NonNegativeCount | None = None
    issue: str | None = None

    @model_validator(mode="after")
    def exact_route_measurement(self) -> PcbNativeRoutePath:
        if self.status == "RESOLVED":
            if (
                not self.track_uuids
                or self.length_nm is None
                or len(self.vertices_nm) != len(self.track_uuids) + 1
                or len(self.track_geometry_kinds) != len(self.track_uuids)
                or len(self.track_midpoints_nm) != len(self.track_uuids)
                or len(self.track_lengths_nm) != len(self.track_uuids)
                or self.issue is not None
                or any(length is None for length in self.track_lengths_nm)
                or sum(length for length in self.track_lengths_nm if length is not None)
                != self.length_nm
            ):
                raise ValueError("A resolved native route needs complete, summed track evidence")
        elif self.length_nm is not None or self.issue is None:
            raise ValueError("An incomplete native route must explain its missing measurement")
        return self
