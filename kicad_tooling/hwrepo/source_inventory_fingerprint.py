"""Canonical fingerprint for an exact repository source-hash inventory."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from .model_primitives import Digest, RepositoryPath


def source_inventory_sha256(source_hashes: Mapping[RepositoryPath, Digest]) -> Digest:
    """Hash sorted path and digest pairs using an unambiguous NUL/newline encoding."""
    return hashlib.sha256(
        "\n".join(f"{name}\0{value}" for name, value in sorted(source_hashes.items())).encode(
            "utf-8"
        )
    ).hexdigest()
