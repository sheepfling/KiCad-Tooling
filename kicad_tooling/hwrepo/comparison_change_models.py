"""Shared state labels for retained before/after comparisons."""

from __future__ import annotations

from typing import Literal

Change = Literal["ADDED", "REMOVED", "CHANGED", "UNCHANGED"]
