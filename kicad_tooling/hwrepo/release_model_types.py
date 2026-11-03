"""Shared release contract enums owned outside the compatibility registry."""

from __future__ import annotations

from enum import Enum


class ReleaseClass(str, Enum):
    ENGINEERING_REVIEW = "engineering_review"
    PROTOTYPE = "prototype"
    PILOT = "pilot"
    PRODUCTION = "production"
