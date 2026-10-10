"""Shared disposable project setup for hosted CI behavior tests."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support import reference_root


def copy_reference_checkout(destination: Path) -> Path:
    """Copy the public reference project into a disposable test checkout."""
    return shutil.copytree(
        reference_root(),
        destination,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )


class HostedRepoTestCase(unittest.TestCase):
    """Provide one disposable public reference checkout to hosted tests."""

    root: Path

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="hosted-ci-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        copy_reference_checkout(self.root)
