"""MCP release-readiness and package workflows over typed release services."""

from __future__ import annotations

from pathlib import Path

from . import packaging
from .contracts import read_model
from .mcp_workflow_paths import artifact_file, fresh_output
from .release import check as release_check
from .release_contract_models import ReleaseManifest
from .release_report_models import ReleasePackageReport, ReleaseReadinessReport


def check_release(root: Path, manifest: str) -> ReleaseReadinessReport:
    """Check a selected manifest through the native release service."""
    return release_check(root, read_model(artifact_file(root, manifest), ReleaseManifest))


def package_release(root: Path, manifest: str, package_id: str) -> ReleasePackageReport:
    """Create the requested package under its validated output path."""
    path = artifact_file(root, manifest)
    output = fresh_output(root, "packages", package_id, ".zip")
    return packaging.package(root, path.relative_to(root).as_posix(), output)


def verify_package(root: Path, archive: str) -> ReleasePackageReport:
    """Verify a package archive selected from the project checkout."""
    return packaging.verify(artifact_file(root, archive))


def restore_package(root: Path, archive: str, restore_id: str) -> ReleasePackageReport:
    """Restore a verified package into a newly allocated output directory."""
    path = artifact_file(root, archive)
    output = fresh_output(root, "restores", restore_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    return packaging.restore(path, output)
