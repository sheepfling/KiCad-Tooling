"""Typed native Edge.Cuts identities retained with PCB snapshots."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

from .model_primitives import NonNegativeCount, StrictModel

PcbEdgeCutUuid = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
]


class PcbEdgeCutObservation(StrictModel):
    """Native identity and drawing width for one board-edge or cutout shape."""

    uuid: PcbEdgeCutUuid
    width_nm: NonNegativeCount
