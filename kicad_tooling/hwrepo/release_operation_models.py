"""Typed requests for release-candidate operations."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import Identifier, StrictModel
from .release_contract_models import ReleaseVariant
from .release_model_types import ReleaseClass


class ReleasePreparationRequest(StrictModel):
    """Select the reviewed project scope and execution inputs for one candidate."""

    release_id: Identifier
    project_ids: tuple[Identifier, ...] = ()
    variants: tuple[ReleaseVariant, ...] = ()
    release_class: ReleaseClass = ReleaseClass.ENGINEERING_REVIEW
    cli: str | None = None
    portable: Path | None = None
    ngspice: str = "ngspice"
