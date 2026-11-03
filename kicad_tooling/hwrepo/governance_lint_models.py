"""Typed outcome for authored project and catalog governance checks."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Identifier, NonEmptyText, StrictModel


class GovernanceLintReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["STATIC_GOVERNANCE_LINT"] = "STATIC_GOVERNANCE_LINT"
    projects: tuple[Identifier, ...]
    issues: tuple[NonEmptyText, ...]
    status: Literal["PASS", "FAIL"]
