"""Shared exact-image marker for processes running inside native KiCad containers."""

from __future__ import annotations

import os

NATIVE_CONTAINER_IMAGE_ENV = "KICAD_TOOLING_NATIVE_CONTAINER_IMAGE"


def native_container_image_marker() -> str | None:
    """Return the digest-pinned image passed by the host container runner, if present."""
    return os.environ.get(NATIVE_CONTAINER_IMAGE_ENV)
