"""Transport-neutral issue records shared by repository policy services."""

from __future__ import annotations

from .model_primitives import NonEmptyText, StrictModel


class PolicyIssue(StrictModel):
    code: NonEmptyText
    location: NonEmptyText
    message: NonEmptyText
