"""Saved revision anchors keep check, finding, source, and artifact states distinct."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport, ReviewFinding
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    ProjectVerificationReport,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseClass,
    ReleaseManifest,
    ReleaseStatus,
    ValidationSummary,
)
from kicad_tooling.hwrepo.project_models import ProjectKind
from kicad_tooling.hwrepo.repository import checkout_input_hashes
from kicad_tooling.hwrepo.review_overview_models import (
    OverviewItem,
    OverviewLink,
    ReviewOverviewReport,
)
from kicad_tooling.hwrepo.verification_history import compare_verification_history
from kicad_tooling.hwrepo.verification_history_models import VerificationHistoryReport
from kicad_tooling.hwrepo.verification_receipts import save_verification_output_manifest
from kicad_tooling.validate import hashes
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.verify_support import native_summary

pytestmark = pytest.mark.template_checkout
MANIFEST = "examples/projects/controller/project.json"


def _saved_snapshot(root: Path, name: str, source: dict[str, str], *, later: bool) -> Path:
    native_dir = root / "build/native-history" / name
    native_dir.mkdir(parents=True)
    checks = {
        "source_scope": CheckEvidence(status="PASS", source_hashes=source),
        "source_unchanged": CheckEvidence(status="PASS", source_hashes=source),
        "erc": CheckEvidence(status="PASS" if later else "FAIL", findings=0 if later else 1),
        "drc": CheckEvidence(status="NOT_RUN" if later else "PASS"),
    }
    native = ValidationSummary(
        timestamp_utc="2026-10-30T00:00:00Z",
        checked_commit=("b" if later else "a") * 40,
        project_id="controller",
        project_kind=ProjectKind.PCB,
        checks=checks,
        status="PASS" if later else "FAIL",
        artifacts_sha256={},
    )
    write_model(native_dir / "summary.json", native)
    findings_dir = root / "build/findings-history" / name
    findings_dir.mkdir(parents=True)
    findings = FindingsViewReport(
        project_id="controller",
        native_status="PASS" if later else "FAIL",
        lint_status="NOT_SUPPLIED",
        native_summary=(native_dir / "summary.json").relative_to(root).as_posix(),
        native_summary_sha256=digest(native_dir / "summary.json"),
        source_hashes=source,
        findings=(
            ReviewFinding(
                origin="DESIGN_LINT",
                rule="power.return",
                severity="warning",
                title="Return path",
                fingerprint=("2" if later else "1") * 64,
                evidence={"net": ("GND" if later else "RETURN",)},
            ),
        ),
        output_directory=str(findings_dir),
    )
    write_model(findings_dir / "review.json", findings)
    directory = root / "build/review-overview" / name
    directory.mkdir(parents=True)
    (directory / "index.html").write_text("<html>saved overview</html>", encoding="utf-8")
    items = (
        OverviewItem(
            kind="native",
            selected_path=(native_dir / "summary.json").relative_to(root).as_posix(),
            status=native.status,
            freshness="CURRENT",
            report_sha256=digest(native_dir / "summary.json"),
            source_commit=native.checked_commit,
            source_hashes=source,
        ),
        OverviewItem(
            kind="findings",
            selected_path=(findings_dir / "review.json").relative_to(root).as_posix(),
            status="Native PASS" if later else "Native FAIL",
            freshness="CURRENT",
            report_sha256=digest(findings_dir / "review.json"),
            source_hashes=source,
        ),
    )
    report = ReviewOverviewReport(
        project_id="controller",
        project_manifest=MANIFEST,
        project_manifest_sha256=digest(root / MANIFEST),
        toolchain_id="kicad-10.0.5",
        kicad_version="10.0.5",
        current_source_hashes=source,
        items=items,
        output_directory=str(directory),
        artifacts_sha256={"index.html": digest(directory / "index.html")},
    )
    write_model(directory / "overview.json", report)
    return directory / "overview.json"


def _fixtures(root: Path) -> tuple[Path, Path, Path, Path]:
    from kicad_tooling.hwrepo.discovery import load_config

    config = load_config(root, MANIFEST)
    current = hashes(root, config.source_roots)
    historical = dict(current)
    changed_path = next(iter(historical))
    historical[changed_path] = "a" * 64
    baseline = _saved_snapshot(root, "baseline", historical, later=False)
    candidate = _saved_snapshot(root, "candidate", current, later=True)
    release_dir = root / "releases"
    release_dir.mkdir(exist_ok=True)
    output = root / "build/release-artifacts" / "candidate.txt"
    output.parent.mkdir(parents=True)
    output.write_text("candidate export", encoding="utf-8")
    for name, commit, sha in (
        ("baseline", "a" * 40, "0" * 64),
        ("candidate", "b" * 40, digest(output)),
    ):
        write_model(
            release_dir / f"{name}.json",
            ReleaseManifest(
                release_id=f"review-{name}",
                release_class=ReleaseClass.ENGINEERING_REVIEW,
                status=ReleaseStatus.CANDIDATE,
                source_commit=commit,
                toolchain_id="kicad-10.0.5",
                projects=("controller",),
                libraries=(),
                interfaces=(),
                artifacts=(
                    ReleaseArtifact(
                        id="drawing",
                        kind=ReleaseArtifactKind.SCHEMATIC_EXPORT,
                        path=output.relative_to(root).as_posix(),
                        sha256=sha,
                        intended_use="Synthetic history test",
                    ),
                ),
            ),
        )
    return baseline, candidate, release_dir / "baseline.json", release_dir / "candidate.json"


def _add_verification(
    root: Path, overview_path: Path, *, status: Literal["PASS", "FAIL"], with_native: bool
) -> Path:
    directory = root / "build/verify-history" / overview_path.parent.name
    directory.mkdir(parents=True)
    receipt = directory / "verification.json"
    write_model(
        receipt,
        ProjectVerificationReport(
            project_id="controller",
            depth="native" if with_native else "portable",
            status=status,
            run_directory=str(directory),
            native=native_summary("FAIL") if with_native else None,
        ),
    )
    overview = read_model(overview_path, ReviewOverviewReport)
    item = OverviewItem(
        kind="verification",
        selected_path=receipt.relative_to(root).as_posix(),
        status=status,
        freshness="UNKNOWN",
        report_sha256=digest(receipt),
    )
    write_model(overview_path, overview.model_copy(update={"items": (*overview.items, item)}))
    return receipt


def _bind_verification(root: Path, overview_path: Path, receipt: Path) -> None:
    directory = receipt.parent
    (directory / "verification.txt").write_text("Recorded outcome\n", encoding="utf-8")
    (directory / "run.json").write_text("{}\n", encoding="utf-8")
    (directory / "events.log").write_text("verification complete\n", encoding="utf-8")
    manifest = save_verification_output_manifest(root, directory, checkout_input_hashes(root))
    manifest_path = directory / "verification-artifacts.json"
    overview = read_model(overview_path, ReviewOverviewReport)
    items = tuple(
        item.model_copy(
            update={
                "freshness": "CURRENT",
                "source_hashes": dict(manifest.source_hashes),
                "links": (
                    OverviewLink(
                        label="Verification hash manifest",
                        path=manifest_path.relative_to(root).as_posix(),
                        sha256=digest(manifest_path),
                        receipt_bound=False,
                    ),
                ),
            }
        )
        if item.kind == "verification"
        else item
        for item in overview.items
    )
    write_model(overview_path, overview.model_copy(update={"items": items}))


def test_cross_revision_checks_findings_and_release_artifacts(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, old_release, new_release = _fixtures(root)
    report = compare_verification_history(
        root,
        "controller",
        baseline,
        candidate,
        baseline_release=old_release,
        candidate_release=new_release,
        output=Path("build/verification-history/compare"),
    )
    assert report.baseline.source_relation == "HISTORICAL"
    assert report.candidate.source_relation == "CURRENT"
    assert report.baseline.source_fingerprint != report.candidate.source_fingerprint
    assert len([item for item in report.source_changes if item.change == "CHANGED"]) == 1
    checks = {item.name: (item.before, item.after) for item in report.check_changes}
    assert checks["erc"] == ("FAIL", "PASS")
    assert checks["drc"] == ("PASS", "NOT_RUN")
    assert report.finding_changes[0].change == "CHANGED_FINGERPRINT"
    assert "net" in report.finding_changes[0].explanation
    assert report.baseline_release.source_relation == "MATCHED"
    assert report.candidate_release.source_relation == "MATCHED"
    assert report.artifact_changes[0].before is not None
    assert report.artifact_changes[0].after is not None
    assert report.artifact_changes[0].before.integrity == "STALE"
    assert report.artifact_changes[0].after.integrity == "CURRENT"
    assert not report.build_authorized
    output = Path(report.output_directory)
    assert read_model(output / "history.json", VerificationHistoryReport) == report
    assert digest(output / "index.html") == report.artifacts_sha256["index.html"]
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "HISTORICAL does not apply to the live source" in html
    assert "CHANGED_FINGERPRINT" in html and "STALE" in html


def test_missing_findings_do_not_look_resolved(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    old = read_model(baseline, ReviewOverviewReport)
    selected = next(item for item in old.items if item.kind == "findings")
    assert selected.selected_path is not None
    (root / selected.selected_path).unlink()
    report = compare_verification_history(root, "controller", baseline, candidate)
    evidence = next(item for item in report.evidence_changes if item.kind == "findings")
    assert evidence.before.integrity == "MISSING"
    assert evidence.after.integrity == "CURRENT"
    assert not report.finding_changes


def test_changed_native_receipt_is_stale_instead_of_passed(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    old = read_model(baseline, ReviewOverviewReport)
    selected = next(item for item in old.items if item.kind == "native")
    assert selected.selected_path is not None
    path = root / selected.selected_path
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    report = compare_verification_history(root, "controller", baseline, candidate)
    check = next(item for item in report.check_changes if item.name == "erc")
    assert check.before == "STALE" and check.after == "PASS"


def test_verification_stage_history_keeps_not_run_missing_and_stale_distinct(
    tmp_path: Path,
) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    old_receipt = _add_verification(root, baseline, status="FAIL", with_native=True)
    new_receipt = _add_verification(root, candidate, status="PASS", with_native=False)
    report = compare_verification_history(root, "controller", baseline, candidate)
    stages = {item.name: item for item in report.stage_changes}
    assert (stages["verification"].before, stages["verification"].after) == ("FAIL", "PASS")
    assert (stages["native"].before, stages["native"].after) == ("FAIL", "NOT_RUN")
    assert stages["electrical"].change == "UNCHANGED"
    assert "Verification stages" in (Path(report.output_directory) / "index.html").read_text()

    old_receipt.write_text(old_receipt.read_text() + " ", encoding="utf-8")
    new_receipt.unlink()
    changed = compare_verification_history(root, "controller", baseline, candidate)
    stages = {item.name: item for item in changed.stage_changes}
    assert (stages["verification"].before, stages["verification"].after) == (
        "STALE",
        "MISSING",
    )
    assert (stages["native"].before, stages["native"].after) == ("STALE", "MISSING")


def test_verification_history_rejects_another_project_even_with_matching_hash(
    tmp_path: Path,
) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    receipt = _add_verification(root, baseline, status="PASS", with_native=False)
    saved = read_model(receipt, ProjectVerificationReport)
    write_model(receipt, saved.model_copy(update={"project_id": "another-project"}))
    overview = read_model(baseline, ReviewOverviewReport)
    items = tuple(
        item.model_copy(update={"report_sha256": digest(receipt)})
        if item.kind == "verification"
        else item
        for item in overview.items
    )
    write_model(baseline, overview.model_copy(update={"items": items}))
    report = compare_verification_history(root, "controller", baseline, candidate)
    stage = next(item for item in report.stage_changes if item.name == "verification")
    assert (stage.before, stage.after) == ("STALE", "NOT_RUN")


def test_history_rechecks_bound_verification_manifest_and_stage_outputs(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    receipt = _add_verification(root, baseline, status="FAIL", with_native=True)
    _bind_verification(root, baseline, receipt)
    first = compare_verification_history(root, "controller", baseline, candidate)
    item = next(entry for entry in first.evidence_changes if entry.kind == "verification")
    assert item.before.integrity == "CURRENT"
    assert first.baseline.source_relation == "HISTORICAL"
    assert first.stage_changes[0].before == "FAIL"

    source = root / MANIFEST
    original_source = source.read_text(encoding="utf-8")
    source.write_text(original_source + "\n", encoding="utf-8")
    historical = compare_verification_history(root, "controller", baseline, candidate)
    evidence = next(entry for entry in historical.evidence_changes if entry.kind == "verification")
    assert evidence.before.integrity == "CURRENT"
    assert historical.candidate.source_relation == "HISTORICAL"
    source.write_text(original_source, encoding="utf-8")

    stage = receipt.parent / "verification.txt"
    original = stage.read_text(encoding="utf-8")
    stage.write_text(original + "changed\n", encoding="utf-8")
    changed = compare_verification_history(root, "controller", baseline, candidate)
    assert changed.stage_changes[0].before == "STALE"
    evidence = next(entry for entry in changed.evidence_changes if entry.kind == "verification")
    assert any("verification.txt" in issue for issue in evidence.before.issues)
    stage.write_text(original, encoding="utf-8")

    manifest_path = receipt.parent / "verification-artifacts.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(manifest_text + " ", encoding="utf-8")
    changed = compare_verification_history(root, "controller", baseline, candidate)
    assert changed.stage_changes[0].before == "STALE"
    manifest_path.write_text(manifest_text, encoding="utf-8")

    saved_overview = read_model(baseline, ReviewOverviewReport)
    items = tuple(
        entry.model_copy(update={"source_hashes": {MANIFEST: "0" * 64}})
        if entry.kind == "verification"
        else entry
        for entry in saved_overview.items
    )
    write_model(baseline, saved_overview.model_copy(update={"items": items}))
    mismatched = compare_verification_history(root, "controller", baseline, candidate)
    assert mismatched.stage_changes[0].before == "STALE"
    write_model(baseline, saved_overview)

    manifest_path.unlink()
    missing = compare_verification_history(root, "controller", baseline, candidate)
    assert missing.stage_changes[0].before == "STALE"


def test_release_commit_mismatch_is_explicit(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, old_release, _ = _fixtures(root)
    report = compare_verification_history(
        root, "controller", baseline, candidate, candidate_release=old_release
    )
    assert report.candidate_release.source_relation == "MISMATCH"
    assert report.candidate_release.issues
    assert report.baseline_release.status == "NOT_SELECTED"


def test_missing_or_unscoped_release_manifest_cannot_bind_a_revision(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    baseline, candidate, _, selected = _fixtures(root)
    missing = root / "releases/missing.json"
    report = compare_verification_history(
        root,
        "controller",
        baseline,
        candidate,
        baseline_release=missing,
        candidate_release=selected,
    )
    assert report.baseline_release.status == "MISSING"
    assert report.baseline_release.source_relation == "UNKNOWN"
    manifest = read_model(selected, ReleaseManifest)
    write_model(selected, manifest.model_copy(update={"projects": ("other-project",)}))
    unscoped = compare_verification_history(
        root, "controller", baseline, candidate, candidate_release=selected
    )
    assert unscoped.candidate_release.source_relation == "UNKNOWN"
    assert any("does not explicitly select" in issue for issue in unscoped.candidate_release.issues)


class _HistoryParity(McpParityHarness):
    async def _case_test_cli_mcp_verification_history_parity(self) -> None:
        baseline, candidate, _, _ = _fixtures(self.root)
        old = baseline.relative_to(self.root).as_posix()
        new = candidate.relative_to(self.root).as_posix()
        cli = await self.cli(
            "kicad_tooling.verification_history",
            VerificationHistoryReport,
            "--project",
            "controller",
            "--baseline",
            old,
            "--candidate",
            new,
            "--output",
            "build/verification-history/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "baseline": old,
            "candidate": new,
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("export_verification_history", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_verification_history", VerificationHistoryReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_verification_history_parity() -> None:
    run_mcp_parity(_HistoryParity, "_case_test_cli_mcp_verification_history_parity")
