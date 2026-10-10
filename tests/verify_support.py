"""Shared disposable-project setup for verification regression suites."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    GovernanceLintReport,
    ProductPolicyReport,
    ProjectCheckSummary,
    RepositoryPolicyReport,
)
from tests.support import initialize_git, reference_root


def native_summary(status: str = "PASS") -> CheckAllSummary:
    return CheckAllSummary(
        governance=GovernanceLintReport(projects=("controller",), issues=(), status="PASS"),
        repository=RepositoryPolicyReport(status="PASS", issues=()),
        product_policy=ProductPolicyReport(status="PASS", products=(), open_items={}, issues=()),
        projects=(
            ProjectCheckSummary(
                id="controller",
                status=status,
                summary="controller/summary.json",
            ),
        ),
        status=status,
    )


class VerifyFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-verify-")
        self.addCleanup(temporary.cleanup)
        self.root = (Path(temporary.name) / "repository").resolve()
        create_reference_project(self.root)

    @staticmethod
    @contextmanager
    def runner_environment(local_version: str | None, docker: bool = False) -> Iterator[None]:
        with runner_environment(local_version, docker):
            yield


def create_reference_project(destination: Path) -> Path:
    """Copy and initialize the public template in a disposable test directory."""
    root = destination.resolve()
    shutil.copytree(reference_root(), root, ignore=shutil.ignore_patterns(".git"))
    initialize_git(root)
    return root


@contextmanager
def runner_environment(local_version: str | None, docker: bool = False) -> Iterator[None]:
    """Patch the tool discovery surface used by one-command verification tests."""

    def which(name: str) -> str | None:
        if name == "git":
            return "/usr/bin/git"
        if name == "docker" and docker:
            return "/usr/bin/docker"
        return None

    def output(argv: tuple[str, ...]) -> str | None:
        if "--version" in argv:
            return "git version 2.54.0"
        if "rev-parse" in argv:
            return "true"
        if "version" in argv:
            return "27.5.1"
        return None

    with (
        patch("kicad_tooling.hwrepo.doctor.shutil.which", side_effect=which),
        patch("kicad_tooling.hwrepo.doctor.command_output", side_effect=output),
        patch("kicad_tooling.hwrepo.doctor.observed_version", return_value=local_version),
    ):
        yield
