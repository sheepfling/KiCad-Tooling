"""Safe template preflight, bootstrap and migration planning services."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .contracts import read_model, repo_path, write_model
from .licensing import template_license
from .models import (
    PolicyIssue,
    TemplateAdoptionRecord,
    TemplateBootstrapReport,
    TemplateContract,
    TemplatePreflightReport,
    TemplateUpgrade,
    TemplateUpgradePlan,
    TemplateUpgradesCatalog,
)
from .repository import ephemeral, generated_artifact

CONTRACT_PATH = "templates/template-contract.json"
ADOPTION_RECORD_PATH = "template-adoption.json"


def finding(code: str, location: str, message: str) -> PolicyIssue:
    """Build a concise, typed template-control finding."""
    return PolicyIssue(code=code, location=location, message=message)


def load_contract(root: Path) -> TemplateContract:
    """Load the one authoritative template contract at the file boundary."""
    return read_model(repo_path(root, CONTRACT_PATH), TemplateContract)


def preflight(root: Path) -> TemplatePreflightReport:
    """Confirm the live template owns every declared bootstrap input."""
    resolved_root = root.resolve()
    issues: list[PolicyIssue] = []
    try:
        contract = load_contract(resolved_root)
        for value in (*contract.required_paths, contract.adoption_guide, contract.upgrades_catalog):
            path = repo_path(resolved_root, value)
            if not path.exists():
                issues.append(finding("TEMPLATE_REQUIRED_PATH", value, "Required template path is missing"))
        if not issues:
            read_model(repo_path(resolved_root, contract.upgrades_catalog), TemplateUpgradesCatalog)
    except (OSError, ValueError) as exc:
        issues.append(finding("TEMPLATE_CONTRACT", CONTRACT_PATH, str(exc)))
        contract = None
    return TemplatePreflightReport(
        template_version=None if contract is None else contract.template_version,
        status="FAIL" if issues else "PASS",
        issues=tuple(issues),
    )


def working_tree_is_clean(root: Path) -> bool:
    """Read Git status; a bootstrap must never copy a half-edited template state."""
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return not result.stdout


def bootstrap(root: Path, destination: Path, project_id: str) -> TemplateBootstrapReport:
    """Copy a clean template into a new directory and record adoption as pending.

    The method never overwrites a destination, initializes a remote, creates a Git
    commit, or changes KiCad sources. It omits the exact upstream root license,
    preserving all other license records. It first writes a sibling staging directory
    and atomically renames it only after the typed adoption record is present.
    """
    resolved_root = root.resolve()
    resolved_destination = destination.resolve()
    report = preflight(resolved_root)
    issues = list(report.issues)
    if resolved_destination.exists():
        issues.append(
            finding("TEMPLATE_DESTINATION", str(resolved_destination), "Destination already exists")
        )
    if not resolved_destination.parent.is_dir():
        issues.append(
            finding("TEMPLATE_DESTINATION", str(resolved_destination.parent), "Parent directory is missing")
        )
    if resolved_root == resolved_destination or resolved_root in resolved_destination.parents:
        issues.append(
            finding(
                "TEMPLATE_DESTINATION",
                str(resolved_destination),
                "Destination must be outside the source template",
            )
        )
    if not issues:
        try:
            if not working_tree_is_clean(resolved_root):
                issues.append(
                    finding(
                        "TEMPLATE_DIRTY",
                        "repository",
                        "Bootstrap requires a clean committed template source",
                    )
                )
        except (OSError, subprocess.SubprocessError) as exc:
            issues.append(finding("TEMPLATE_GIT", "repository", str(exc)))
    adoption: TemplateAdoptionRecord | None = None
    if not issues and report.template_version is not None:
        try:
            adoption = TemplateAdoptionRecord(
                template_version=report.template_version,
                project_id=project_id,
            )
        except ValueError as exc:
            issues.append(finding("TEMPLATE_PROJECT_ID", project_id, str(exc)))
    if issues or report.template_version is None or adoption is None:
        return TemplateBootstrapReport(
            template_version=report.template_version,
            destination=str(resolved_destination),
            status="FAIL",
            issues=tuple(issues),
        )

    staging_parent = Path(tempfile.mkdtemp(prefix="kicad-template-bootstrap-", dir=resolved_destination.parent))
    staging = staging_parent / resolved_destination.name
    removed: tuple[str, ...] = ()
    try:
        tracked = subprocess.run(
            ["git", "-c", f"safe.directory={resolved_root.as_posix()}",
             "-C", str(resolved_root), "ls-files", "-z"],
            capture_output=True, text=True, check=True,
        )
        staging.mkdir()
        for name in tracked.stdout.split("\0"):
            if not name or ephemeral(name) or generated_artifact(name):
                continue
            source = repo_path(resolved_root, name)
            target = repo_path(staging, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        license_path = template_license(staging)
        if license_path is not None:
            license_path.unlink()
            removed = ("LICENSE",)
        write_model(
            staging / ADOPTION_RECORD_PATH,
            adoption,
        )
        os.replace(staging, resolved_destination)
        staging_parent.rmdir()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        shutil.rmtree(staging_parent, ignore_errors=True)
        return TemplateBootstrapReport(
            template_version=report.template_version,
            destination=str(resolved_destination),
            status="FAIL",
            issues=(finding("TEMPLATE_BOOTSTRAP", str(resolved_destination), str(exc)),),
        )
    return TemplateBootstrapReport(
        template_version=report.template_version,
        destination=str(resolved_destination),
        status="PASS",
        issues=(),
        removed=removed,
    )


def version_key(value: str) -> tuple[int, int, int]:
    """Compare the strict semantic-version subset accepted by the template model."""
    major, minor, patch = value.split(".")
    return (int(major), int(minor), int(patch))


def upgrade_paths(
    upgrades: tuple[TemplateUpgrade, ...], current: str, target: str
) -> tuple[tuple[TemplateUpgrade, ...], ...]:
    """Return all forward, acyclic catalog paths between two template versions."""
    paths: list[tuple[TemplateUpgrade, ...]] = []

    def visit(version: str, selected: tuple[TemplateUpgrade, ...]) -> None:
        if version == target:
            paths.append(selected)
            return
        seen = {upgrade.from_version for upgrade in selected}
        for upgrade in upgrades:
            if (
                upgrade.from_version == version
                and version_key(upgrade.to_version) > version_key(upgrade.from_version)
                and upgrade.to_version not in seen
                and version_key(upgrade.to_version) <= version_key(target)
            ):
                visit(upgrade.to_version, (*selected, upgrade))

    visit(current, ())
    return tuple(paths)


def plan_upgrade(root: Path, target_version: str) -> TemplateUpgradePlan:
    """Produce a typed migration plan; deliberate human edits remain separate."""
    resolved_root = root.resolve()
    report = preflight(resolved_root)
    issues = list(report.issues)
    if report.template_version is None:
        return TemplateUpgradePlan(
            current_version=None,
            target_version=target_version,
            status="FAIL",
            upgrades=(),
            issues=tuple(issues),
        )
    current = report.template_version
    try:
        adoption_path = repo_path(resolved_root, ADOPTION_RECORD_PATH)
        if adoption_path.is_file():
            current = read_model(adoption_path, TemplateAdoptionRecord).template_version
        if version_key(target_version) < version_key(current):
            issues.append(finding("TEMPLATE_UPGRADE", target_version, "Downgrades are not supported"))
        elif target_version == current:
            return TemplateUpgradePlan(
                current_version=current,
                target_version=target_version,
                status="FAIL" if issues else "PASS",
                upgrades=(),
                issues=tuple(issues),
            )
        catalog = read_model(
            repo_path(resolved_root, load_contract(resolved_root).upgrades_catalog),
            TemplateUpgradesCatalog,
        )
        paths = upgrade_paths(catalog.upgrades, current, target_version)
        if len(paths) != 1:
            issues.append(
                finding(
                    "TEMPLATE_UPGRADE_PATH",
                    target_version,
                    "Need exactly one forward, reviewed migration path",
                )
            )
            selected: tuple[TemplateUpgrade, ...] = ()
        else:
            selected = paths[0]
    except (OSError, ValueError) as exc:
        issues.append(finding("TEMPLATE_UPGRADE", target_version, str(exc)))
        selected = ()
    return TemplateUpgradePlan(
        current_version=current,
        target_version=target_version,
        status="FAIL" if issues else "PASS",
        upgrades=selected,
        issues=tuple(issues),
    )
