"""Recognize the disposable upstream license without touching adopter notices."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .contracts import repo_path

# Exact bytes of this scaffold's root 0BSD LICENSE. A different license, even one
# with similar wording, belongs to the adopter and must never be removed by init.
SCAFFOLD_LICENSE_SHA256 = "e81e2e6cad63fda42ebe09a98294d920ae6f2b4b1e857d5bf72f40d88e764fe6"


def template_license(root: Path) -> Path | None:
    """Return only the byte-matching root license; never inspect nested notices."""
    path = repo_path(root, "LICENSE")
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == SCAFFOLD_LICENSE_SHA256:
        return path
    return None
