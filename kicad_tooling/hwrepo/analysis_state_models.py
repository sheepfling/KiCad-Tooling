"""Shared typed states for analyses that are pending or not applicable."""

from __future__ import annotations

from typing import Literal

from .model_primitives import NonEmptyText, StrictModel


class AnalysisPending(StrictModel):
    """An unanswered engineering question; this can never supply passing evidence."""

    mode: Literal["pending"] = "pending"
    reason: NonEmptyText


class AnalysisNotApplicable(StrictModel):
    mode: Literal["not_applicable"]
    reason: NonEmptyText
