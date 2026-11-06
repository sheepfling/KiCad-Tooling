"""Capture a computed release check with its selected manifest and input bytes."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote
from uuid import uuid4

from ..git import git_output
from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, read_model, relative_path_from, repo_path, write_model
from .electrical_report_models import ElectricalAnalysisReport
from .evidence import digest
from .model_primitives import Digest, RepositoryPath
from .models import ReleaseExportReport
from .native_project_validation_models import ValidationSummary
from .release import check
from .release_contract_models import ReleaseManifest
from .release_readiness_view_models import ReleaseDependencyInventory, ReleaseReadinessViewReport
from .repository import checkout_input_hashes


def declared_file_hashes(root: Path, manifest: ReleaseManifest) -> ReleaseDependencyInventory:
    """Record manifest inputs and nested artifacts from typed evidence reports."""
    paths: set[RepositoryPath] = {item.path for item in manifest.artifacts}
    artifact_enumeration_complete = True
    if manifest.evidence is not None:
        paths.add(manifest.evidence.portable.path)
        for collection, model in (
            (manifest.evidence.native, ValidationSummary),
            (manifest.evidence.exports, ReleaseExportReport),
            (manifest.evidence.electrical, ElectricalAnalysisReport),
        ):
            for item in collection.values():
                paths.add(item.path)
                try:
                    report_path = repo_path(root, item.path)
                    report = read_model(report_path, model)
                    paths.update(
                        (Path(item.path).parent / name).as_posix()
                        for name in report.artifacts_sha256
                    )
                except (OSError, TypeError, ValueError):
                    artifact_enumeration_complete = False
    result: dict[RepositoryPath, Digest | None] = {}
    if len(paths) > 5000:
        raise ValueError("Release dependency inventory exceeds the 5000-file limit")
    for name in sorted(paths):
        try:
            path = repo_path(root, name)
            result[name] = digest(path) if path.is_file() else None
        except (OSError, ValueError):
            result[name] = None
            artifact_enumeration_complete = False
    return ReleaseDependencyInventory(
        declared_files_sha256=result,
        artifact_enumeration_complete=artifact_enumeration_complete,
    )


def _render(root: Path, report: ReleaseReadinessViewReport) -> str:
    directory = Path(report.output_directory)
    manifest_link = escape(
        quote(
            relative_path_from(repo_path(root, report.manifest), directory).as_posix(), safe="/.-_"
        ),
        quote=True,
    )
    rows = (
        "".join(
            f"<tr><td>{escape(item.code)}</td><td>{escape(item.location)}</td>"
            f"<td>{escape(item.message)}</td></tr>"
            for item in report.readiness.issues
        )
        or '<tr><td colspan="3">No policy issues were reported.</td></tr>'
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Release readiness · {escape(report.readiness.release_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203145;background:#f3f6f9}}
body{{max-width:1100px;margin:32px auto;padding:0 20px}}main{{background:white;padding:24px;border:1px solid #d8e1e8;border-radius:12px}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #e2e8ee}}
code{{overflow-wrap:anywhere}}a{{color:#126477}}a:focus-visible{{outline:3px solid #318e9c}}
</style><main><h1>Release readiness · {escape(report.readiness.release_id)}</h1>
<p>Computed {escape(report.checked_on.isoformat())}: <strong>{escape(report.readiness.status)}</strong> ·
{len(report.readiness.issues)} issues · source stable: {str(report.source_stable).lower()} ·
evidence artifact inventory complete: {str(report.dependency_inventory_complete).lower()}.</p>
<p><a href="{manifest_link}">Selected release manifest</a> · SHA-256
<code>{report.manifest_sha256}</code></p>
<p>Checked source commit: <code>{report.source_commit}</code>. This saved result applies to
the captured inputs; it does not authorize a build, approval, package, or publication.</p>
<p><a href="readiness.json">Structured receipt</a></p>
<h2>Policy issues</h2><table><thead><tr><th>Code</th><th>Location</th><th>Message</th></tr></thead>
<tbody>{rows}</tbody></table></main></html>"""


def capture_release_readiness(
    root: Path,
    manifest_path: Path,
    output: Path | None = None,
    *,
    today: date | None = None,
) -> ReleaseReadinessViewReport:
    """Retain a check outcome, including failures, without granting release authority."""
    root = root.resolve()
    requested = manifest_path.relative_to(root) if manifest_path.is_absolute() else manifest_path
    path = repo_path(root, requested.as_posix())
    content, _ = read_regular_bytes(path, maximum=16 * 1024 * 1024)
    manifest = parse_model_text(content.decode("utf-8"), ReleaseManifest)
    source_hashes = checkout_input_hashes(root)
    dependency_inventory = declared_file_hashes(root, manifest)
    commit = git_output(root, "rev-parse", "HEAD")
    checked_on = today or datetime.now(UTC).date()
    readiness = check(root, manifest, checked_on)
    end_dependency_inventory = declared_file_hashes(root, manifest)
    source_stable = (
        source_hashes == checkout_input_hashes(root)
        and dependency_inventory.declared_files_sha256
        == end_dependency_inventory.declared_files_sha256
        and dependency_inventory.artifact_enumeration_complete
        == end_dependency_inventory.artifact_enumeration_complete
        and commit == git_output(root, "rev-parse", "HEAD")
        and hashlib.sha256(content).hexdigest() == digest(path)
    )
    target = (
        output or Path("build/release-readiness-view") / f"{manifest.release_id}-{uuid4().hex[:12]}"
    )
    directory = receipt_directory(root, manifest.release_id, target)
    report = ReleaseReadinessViewReport(
        manifest=requested.as_posix(),
        manifest_sha256=hashlib.sha256(content).hexdigest(),
        source_commit=commit,
        source_stable=source_stable,
        dependency_inventory_complete=dependency_inventory.artifact_enumeration_complete,
        checked_on=checked_on,
        source_hashes=source_hashes,
        declared_files_sha256=dependency_inventory.declared_files_sha256,
        readiness=readiness,
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(_render(root, report), encoding="utf-8")
    report = report.model_copy(
        update={
            "artifacts_sha256": MappingProxyType({"index.html": digest(directory / "index.html")})
        }
    )
    write_model(directory / "readiness.json", report)
    return report
