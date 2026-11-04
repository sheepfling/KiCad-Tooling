"""Compatibility export for the shared before/after comparison operation."""

from __future__ import annotations

from .comparison_change import change_state
from .comparison_change_models import Change

__all__ = ["Change", "change_state"]
