"""Typed local prerequisite checks for project and native-runner readiness."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Identifier, NonEmptyText, StrictModel


class EnvironmentCheck(StrictModel):
    id: Identifier
    required: bool
    status: Literal["PASS", "FAIL", "OPTIONAL"]
    expected: NonEmptyText
    observed: NonEmptyText | None = None
    next_action: NonEmptyText


class TemplateDoctorReport(StrictModel):
    """Local prerequisites and native-runner readiness without changing the repository."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_DOCTOR"] = "TEMPLATE_DOCTOR"
    build_authorized: Literal[False] = False
    native_requested: bool
    electrical_requested: bool = False
    checks: tuple[EnvironmentCheck, ...]
    status: Literal["PASS", "FAIL"]
    next_actions: tuple[NonEmptyText, ...] = ()
