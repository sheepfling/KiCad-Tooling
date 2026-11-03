"""Typed outcome for repository source and hygiene policy checks."""

from __future__ import annotations

from typing import Literal

from .model_primitives import NonEmptyText, StrictModel


class RepositoryPolicyReport(StrictModel):
    lane: Literal["REPOSITORY_POLICY"] = "REPOSITORY_POLICY"
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]
