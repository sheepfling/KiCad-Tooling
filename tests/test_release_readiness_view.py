"""Saved release checks remain linked to captured source and declared files."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest
from mcp import Client

from kicad_tooling.git import git_output
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    EvidenceFile,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseClass,
    ReleaseEvidence,
    ReleaseManifest,
    ReleaseStatus,
    ValidationSummary,
)
from kicad_tooling.hwrepo.release_readiness_view import capture_release_readiness
from kicad_tooling.hwrepo.release_readiness_view_models import ReleaseReadinessViewReport
from kicad_tooling.hwrepo.review_overview_models import ReviewOverviewReport
from kicad_tooling.hwrepo.verification_history import compare_verification_history
from kicad_tooling.hwrepo.verification_history_models import VerificationHistoryReport
from kicad_tooling.validate import hashes
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_verification_history import _saved_snapshot

pytestmark = pytest.mark.template_checkout


def _release(root: Path) -> Path:
    subprocess.run(
        ("git", "-C", str(root), "symbolic-ref", "HEAD", "refs/heads/master"), check=True
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Synthetic release source",
        ),
        check=True,
    )
    artifact = root / "build/release-artifacts/drawing.txt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("retained drawing", encoding="utf-8")
    manifest = root / "build/releases/readiness/manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    write_model(
        manifest,
        ReleaseManifest(
            release_id="readiness",
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE,
            source_commit=git_output(root, "rev-parse", "HEAD"),
            toolchain_id="kicad-10.0.5",
            projects=("controller",),
            libraries=(),
            interfaces=(),
            artifacts=(
                ReleaseArtifact(
                    id="drawing",
                    kind=ReleaseArtifactKind.SCHEMATIC_EXPORT,
                    path=artifact.relative_to(root).as_posix(),
                    sha256=digest(artifact),
                    intended_use="Synthetic history test",
                ),
            ),
        ),
    )
    return manifest


def _matching_overview(root: Path, name: str) -> Path:
    from kicad_tooling.hwrepo.discovery import load_config

    config = load_config(root, "examples/projects/controller/project.json")
    overview_path = _saved_snapshot(root, name, hashes(root, config.source_roots), later=True)
    overview = read_model(overview_path, ReviewOverviewReport)
    native_item = next(item for item in overview.items if item.kind == "native")
    assert native_item.selected_path is not None
    native_path = root / native_item.selected_path
    native = read_model(native_path, ValidationSummary)
    commit = git_output(root, "rev-parse", "HEAD")
    write_model(native_path, native.model_copy(update={"checked_commit": commit}))
    items = tuple(
        item.model_copy(update={"source_commit": commit, "report_sha256": digest(native_path)})
        if item.kind == "native"
        else item
        for item in overview.items
    )
    write_model(overview_path, overview.model_copy(update={"items": items}))
    return overview_path


def test_capture_links_computed_result_to_source_and_declared_artifact(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest = _release(root)
    receipt = capture_release_readiness(root, manifest, Path("build/release-readiness-view/test"))
    assert receipt.source_stable
    assert receipt.manifest_sha256 == digest(manifest)
    assert receipt.readiness.status == "FAIL"  # No retained native or portable release evidence.
    assert receipt.declared_files_sha256["build/release-artifacts/drawing.txt"]
    assert (
        digest(Path(receipt.output_directory) / "index.html")
        == receipt.artifacts_sha256["index.html"]
    )
    assert "RELEASE_EVIDENCE" in (issue.code for issue in receipt.readiness.issues)


def test_missing_declared_file_stays_explicit_in_complete_inventory(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest = _release(root)
    artifact = root / "build/release-artifacts/drawing.txt"
    artifact.unlink()

    receipt = capture_release_readiness(root, manifest)

    assert receipt.source_stable
    assert receipt.dependency_inventory_complete
    assert receipt.declared_files_sha256[artifact.relative_to(root).as_posix()] is None


def test_unreadable_nested_report_marks_artifact_enumeration_incomplete(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest_path = _release(root)
    native_report = root / "build/native/readiness/summary.json"
    native_report.parent.mkdir(parents=True)
    native_report.write_text("not-json", encoding="utf-8")
    manifest = read_model(manifest_path, ReleaseManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "evidence": ReleaseEvidence(
                    portable=EvidenceFile(path="build/portable/missing.json", sha256="0" * 64),
                    native={
                        "controller": EvidenceFile(
                            path=native_report.relative_to(root).as_posix(),
                            sha256=digest(native_report),
                        )
                    },
                )
            }
        ),
    )

    receipt = capture_release_readiness(root, manifest_path)

    assert not receipt.dependency_inventory_complete
    assert receipt.declared_files_sha256[native_report.relative_to(root).as_posix()]
    assert receipt.declared_files_sha256["build/portable/missing.json"] is None


def test_readiness_report_hash_indexes_are_immutable_and_serialize_as_mappings(
    tmp_path: Path,
) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest = _release(root)
    receipt = capture_release_readiness(root, manifest)
    source_hashes = cast(dict[str, str], receipt.source_hashes)
    declared_hashes = cast(dict[str, str | None], receipt.declared_files_sha256)
    artifact_hashes = cast(dict[str, str], receipt.artifacts_sha256)

    with pytest.raises(TypeError):
        source_hashes["new-source"] = "0" * 64
    with pytest.raises(TypeError):
        declared_hashes["new-dependency"] = "0" * 64
    with pytest.raises(TypeError):
        artifact_hashes["new-artifact"] = "0" * 64

    serialized = receipt.model_dump(mode="json")
    assert isinstance(serialized["source_hashes"], dict)
    assert isinstance(serialized["declared_files_sha256"], dict)
    assert isinstance(serialized["artifacts_sha256"], dict)


def test_capture_includes_nested_native_artifact_hashes(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest_path = _release(root)
    native_dir = root / "build/native/readiness"
    native_dir.mkdir(parents=True)
    artifact = native_dir / "erc.json"
    artifact.write_text("{}", encoding="utf-8")
    summary = native_dir / "summary.json"
    write_model(
        summary,
        ValidationSummary(
            timestamp_utc="2026-10-30T00:00:00Z",
            checked_commit=git_output(root, "rev-parse", "HEAD"),
            checks={},
            status="FAIL",
            artifacts_sha256={"erc.json": digest(artifact)},
        ),
    )
    manifest = read_model(manifest_path, ReleaseManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "evidence": ReleaseEvidence(
                    portable=EvidenceFile(path="build/portable/missing.json", sha256="0" * 64),
                    native={
                        "controller": EvidenceFile(
                            path=summary.relative_to(root).as_posix(), sha256=digest(summary)
                        )
                    },
                )
            }
        ),
    )
    receipt = capture_release_readiness(root, manifest_path)
    assert receipt.dependency_inventory_complete
    assert receipt.declared_files_sha256[artifact.relative_to(root).as_posix()] == digest(artifact)
    overview = _matching_overview(root, "nested-artifact")
    selected = Path(receipt.output_directory) / "readiness.json"
    artifact.write_text("changed", encoding="utf-8")
    changed = compare_verification_history(
        root,
        "controller",
        overview,
        overview,
        baseline_release=manifest_path,
        candidate_release=manifest_path,
        baseline_readiness=selected,
        candidate_readiness=selected,
    )
    assert changed.readiness_change.before.integrity == "STALE"
    assert not changed.readiness_change.comparison_available


def test_history_compares_saved_readiness_and_marks_changed_input_stale(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    manifest = _release(root)
    baseline = _matching_overview(root, "readiness-before")
    candidate = _matching_overview(root, "readiness-after")
    saved = capture_release_readiness(root, manifest, Path("build/release-readiness-view/saved"))
    selected = Path(saved.output_directory) / "readiness.json"
    comparison = compare_verification_history(
        root,
        "controller",
        baseline,
        candidate,
        baseline_release=manifest,
        candidate_release=manifest,
        baseline_readiness=selected,
        candidate_readiness=selected,
    )
    assert comparison.readiness_change.before.integrity == "CURRENT"
    assert comparison.readiness_change.after.status == "FAIL"
    assert comparison.readiness_change.comparison_available
    artifact = root / "build/release-artifacts/drawing.txt"
    artifact.write_text("changed drawing", encoding="utf-8")
    changed = compare_verification_history(
        root,
        "controller",
        baseline,
        candidate,
        baseline_release=manifest,
        candidate_release=manifest,
        baseline_readiness=selected,
        candidate_readiness=selected,
    )
    assert changed.readiness_change.before.integrity == "STALE"
    assert not changed.readiness_change.comparison_available
    assert changed.readiness_change.removed_issue_codes == ()
    assert any(
        "Declared release input changed" in issue
        for issue in changed.readiness_change.before.issues
    )
    missing = compare_verification_history(
        root,
        "controller",
        baseline,
        candidate,
        baseline_release=manifest,
        baseline_readiness=Path("build/release-readiness-view/missing/readiness.json"),
        candidate_release=manifest,
        candidate_readiness=selected,
    )
    assert missing.readiness_change.before.integrity == "MISSING"
    assert not missing.readiness_change.comparison_available


class _ReadinessParity(McpParityHarness):
    async def _case_test_cli_mcp_release_readiness_view_parity(self) -> None:
        manifest = _release(self.root).relative_to(self.root).as_posix()
        cli = await self.cli(
            "kicad_tooling.release_readiness_view",
            ReleaseReadinessViewReport,
            "--manifest",
            manifest,
            "--output",
            "build/release-readiness-view/cli",
        )
        arguments = {"manifest": manifest, "view_id": "mcp"}
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("export_release_readiness_view", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_release_readiness_view", ReleaseReadinessViewReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")

    async def _case_test_cli_mcp_history_readiness_parity(self) -> None:
        manifest = _release(self.root)
        before = _matching_overview(self.root, "history-before")
        after = _matching_overview(self.root, "history-after")
        captured = capture_release_readiness(
            self.root, manifest, Path("build/release-readiness-view/history")
        )
        receipt = Path(captured.output_directory) / "readiness.json"
        selected = {
            "baseline": before.relative_to(self.root).as_posix(),
            "candidate": after.relative_to(self.root).as_posix(),
            "baseline_release": manifest.relative_to(self.root).as_posix(),
            "candidate_release": manifest.relative_to(self.root).as_posix(),
            "baseline_readiness": receipt.relative_to(self.root).as_posix(),
            "candidate_readiness": receipt.relative_to(self.root).as_posix(),
        }
        cli_args = ["--project", "controller"]
        for key, value in selected.items():
            cli_args.extend((f"--{key.replace('_', '-')}", value))
        cli = await self.cli(
            "kicad_tooling.verification_history",
            VerificationHistoryReport,
            *cli_args,
            "--output",
            "build/verification-history/readiness-cli",
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "export_verification_history",
                VerificationHistoryReport,
                {"project_id": "controller", "view_id": "readiness-mcp", **selected},
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertTrue(cli.readiness_change.comparison_available)


def test_cli_mcp_release_readiness_view_parity() -> None:
    run_mcp_parity(_ReadinessParity, "_case_test_cli_mcp_release_readiness_view_parity")


def test_cli_mcp_history_readiness_parity() -> None:
    run_mcp_parity(_ReadinessParity, "_case_test_cli_mcp_history_readiness_parity")
