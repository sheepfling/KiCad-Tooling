"""Real Git/package lifecycle tests using explicitly synthetic check reports.

The hosted native lane separately prepares and restores a package from real KiCad.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.ci import static_pipeline
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.documentation import check as check_docs
from kicad_tooling.hwrepo.evidence import (
    digest,
    source_state,
    verify_native,
    verify_portable,
    verify_release_portable,
)
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    DeviationStatus,
    GenerationReport,
    ProjectStaticPipelineReport,
    ProjectTestsReport,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseClass,
    ReleaseDeviation,
    ReleaseEvidence,
    ReleaseManifest,
    ReleaseStatus,
    ScopedReleasePortableReport,
    StaticPipelineReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.packaging import package, restore, verify
from kicad_tooling.hwrepo.product import check as check_product
from kicad_tooling.hwrepo.release import check
from kicad_tooling.hwrepo.releasing import prepare, reference
from kicad_tooling.hwrepo.repository import check_repository
from kicad_tooling.lint_registry import lint
from tests.support import initialize_git, reference_root


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-release-test-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        initialize_git(self.root)
        self.git("-c", "user.name=Scaffold test fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Synthetic release test source")
        self.project_id = "passive-signal-reference"
        self.config = load_config(self.root, f"examples/projects/{self.project_id}/project.json")
        self.source = source_state(self.root)
        self.assertTrue(self.source.clean)
        self.directory = self.root / "build/releases/test"
        self.directory.mkdir(parents=True)
        command = CommandEvidence(argv=("synthetic-unit-test-evidence",),
                                  started_utc="2026-01-01T00:00:00Z", returncode=0)
        portable = StaticPipelineReport(status="PASS", source=self.source,
                    registry=lint(self.root), repository=check_repository(self.root),
                    documentation=check_docs(self.root), rumdl=command, mdrepo=command,
                    product=check_product(self.root),
                    generation=GenerationReport(status="PASS", issues=()),
                    ruff=command, pyright=command, unit_tests=command,
                    project_tests=ProjectTestsReport(status="PASS", commands={}))
        write_model(self.directory / "portable.json", portable)
        native = self.directory / "native"
        native.mkdir()
        (native / "schematic").mkdir()
        (native / "schematic/sheet.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        (native / "erc.json").write_text(json.dumps({
            "$schema": "https://schemas.kicad.org/erc.v1.json", "kicad_version": "10.0.5",
            "included_severities": ["error", "warning", "exclusion"],
            "ignored_checks": [{"key": name} for name in self.config.validation.expected_ignored_checks.erc],
            "sheets": [{"violations": []}],
        }), encoding="utf-8")
        for name in ("version", "erc", "schematic_svg"):
            write_model(native / f"{name}.command.json", command)
        hashes = {name: self.source.files_sha256[name] for name in self.config.required_inputs}
        checks = {name: CheckEvidence(status="PASS") for name in (
            "governance", "repository", "product_policy", "erc", "schematic_svg")}
        checks.update({"source_scope": CheckEvidence(status="PASS", source_hashes=hashes),
                       "source_unchanged": CheckEvidence(status="PASS", source_hashes=hashes),
                       "toolchain": CheckEvidence(status="PASS", observed_version="10.0.5", image=self.config.image)})
        self.native_path = native / "summary.json"
        write_model(self.native_path, ValidationSummary(timestamp_utc="2026-01-01T00:00:00Z",
                    source=self.source, checked_commit=self.source.commit or "", project_id=self.project_id,
                    project_kind=self.config.kind, assurance_profile="training", not_for_manufacture=True,
                    checks=checks, status="PASS", artifacts_sha256={
                        path.relative_to(native).as_posix(): digest(path) for path in native.rglob("*") if path.is_file()}))
        review = self.directory / "review.txt"
        review.write_text("Synthetic unit-test review record, not hardware approval.", encoding="utf-8")
        self.manifest = ReleaseManifest(release_id="test", release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE, source_commit=self.source.commit or "", toolchain_id="kicad-10.0.5",
            projects=(self.project_id,), libraries=(), interfaces=(),
            evidence=ReleaseEvidence(portable=reference(self.root, self.directory / "portable.json"),
                                     native={self.project_id: reference(self.root, self.native_path)}),
            artifacts=(ReleaseArtifact(id="review", kind=ReleaseArtifactKind.REVIEW_RECORD,
                       path=review.relative_to(self.root).as_posix(), sha256=digest(review),
                       intended_use="Synthetic unit-test record"),))
        self.manifest_name = "build/releases/test/manifest.json"
        write_model(self.root / self.manifest_name, self.manifest)

    def git(self, *args: str) -> str:
        return subprocess.run(("git", "-C", str(self.root), *args), check=True, capture_output=True,
                              text=True).stdout.strip()

    def test_standalone_release_restores_exact_commit_and_verified_evidence(self) -> None:
        self.assertEqual(check(self.root, self.manifest).status, "PASS", check(self.root, self.manifest).issues)
        archive = self.parent / "release.zip"
        packaged = package(self.root, self.manifest_name, archive)
        self.assertEqual(packaged.status, "PASS")
        self.assertEqual(packaged.package_sha256, digest(archive))
        destination = self.parent / "restored"
        restored = restore(archive, destination)
        self.assertEqual(restored.status, "PASS")
        self.assertEqual(restored.package_sha256, digest(archive))
        self.assertEqual(source_state(destination), self.source)
        verified = verify(archive)
        self.assertEqual(verified.status, "PASS")
        self.assertEqual(verified.package_sha256, digest(archive))
        with self.assertRaisesRegex(ValueError, "already exists"):
            restore(archive, destination)

    def test_legacy_portable_evidence_cannot_omit_tooling_quality_commands(self) -> None:
        path = self.directory / "portable.json"
        original = json.loads(path.read_text())
        self.assertEqual(original["scope"], "static_only")
        for field in ("ruff", "pyright", "unit_tests"):
            for remove in (True, False):
                with self.subTest(field=field, remove=remove):
                    changed = dict(original)
                    if remove:
                        changed.pop(field)
                    else:
                        changed[field] = None
                    path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, "Legacy full reports require"):
                        verify_portable(self.root, reference(self.root, path), self.source)

    def test_repository_evidence_binds_tooling_version_and_keeps_project_gates_required(self) -> None:
        path = self.directory / "portable.json"
        original = json.loads(path.read_text())
        original.update(scope="repository_static", tooling_version="0.1.0")
        for field in ("ruff", "pyright", "unit_tests"):
            original.pop(field)
        path.write_text(json.dumps(original))
        report = verify_portable(self.root, reference(self.root, path), self.source)
        self.assertEqual(report.tooling_version, "0.1.0")
        self.assertIsNone(report.unit_tests)
        for value in (None, ""):
            with self.subTest(version=value):
                changed = dict(original)
                changed["tooling_version"] = value
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    verify_portable(self.root, reference(self.root, path), self.source)
        absent = dict(original)
        absent.pop("tooling_version")
        path.write_text(json.dumps(absent))
        with self.assertRaisesRegex(ValueError, "identify the installed tooling version"):
            verify_portable(self.root, reference(self.root, path), self.source)
        failed = dict(original)
        failed["rumdl"] = {**original["rumdl"], "returncode": 1}
        path.write_text(json.dumps(failed))
        with self.assertRaisesRegex(ValueError, "failed or missing checks"):
            verify_portable(self.root, reference(self.root, path), self.source)

    def test_tag_is_added_after_source_commit_without_circular_manifest_commit(self) -> None:
        self.git("-c", "user.name=Scaffold test fixture", "-c", "user.email=fixture@example.invalid",
                 "tag", "-a", "test-review", "-m", "Synthetic unit-test tag")
        manifest = self.manifest.model_copy(update={"source_tag": "test-review"})
        write_model(self.root / self.manifest_name, manifest)
        archive = self.parent / "tagged.zip"
        self.assertEqual(package(self.root, self.manifest_name, archive).status, "PASS")
        self.assertEqual(restore(archive, self.parent / "restored").status, "PASS")

    def test_standalone_deviation_uses_retained_release_evidence(self) -> None:
        deviation = ReleaseDeviation(
            id="DV-standalone", scope=(self.project_id,), owner="Synthetic test owner",
            reason="Exercise standalone deviation evidence without a product record.",
            status=DeviationStatus.APPROVED, expires=date(9999, 12, 31), evidence=("review",),
        )
        manifest = self.manifest.model_copy(update={"deviations": (deviation,)})
        report = check(self.root, manifest)
        self.assertEqual(report.status, "PASS", report.issues)
        write_model(self.root / self.manifest_name, manifest)
        archive = self.parent / "deviation.zip"
        self.assertEqual(package(self.root, self.manifest_name, archive).status, "PASS")
        self.assertEqual(restore(archive, self.parent / "restored").status, "PASS")
        for field, value, code in (
            ("scope", ("unselected-board",), "DEVIATION_SCOPE"),
            ("evidence", ("missing-artifact",), "DEVIATION_EVIDENCE"),
            ("status", DeviationStatus.OPEN, "DEVIATION_STATUS"),
            ("expires", date(2000, 1, 1), "DEVIATION_EXPIRY"),
        ):
            with self.subTest(field=field):
                bad = manifest.model_copy(update={"deviations": (
                    deviation.model_copy(update={field: value}),)})
                self.assertIn(code, {issue.code for issue in check(self.root, bad).issues})

    def test_release_portable_scope_is_exact_and_cannot_claim_full_coverage(self) -> None:
        selected = (self.project_id,)
        self.assertIsInstance(
            verify_release_portable(
                self.root, reference(self.root, self.directory / "portable.json"),
                self.source, selected,
            ),
            StaticPipelineReport,
        )
        checks = static_pipeline(self.root, list(selected))
        self.assertIsInstance(checks, ProjectStaticPipelineReport)
        self.assertEqual(checks.status, "PASS")
        scoped = ScopedReleasePortableReport(source=self.source, projects=selected, checks=checks)
        path = self.directory / "selected-portable.json"
        write_model(path, scoped)
        retained = reference(self.root, path)
        self.assertEqual(
            verify_release_portable(self.root, retained, self.source, selected), scoped,
        )
        with self.assertRaisesRegex(ValueError, "scope differs"):
            verify_release_portable(self.root, retained, self.source, ("controller",))
        with self.assertRaises(ValueError):
            verify_portable(self.root, retained, self.source)

        # The bare focused CI result has neither the release scope nor commit
        # binding, even when every visible check says PASS.
        write_model(path, checks)
        with self.assertRaises(ValueError):
            verify_release_portable(self.root, reference(self.root, path), self.source, selected)

        failing = checks.model_copy(update={"project_tests": checks.project_tests.model_copy(
            update={"status": "FAIL"})})
        write_model(path, scoped.model_copy(update={"checks": failing}))
        with self.assertRaisesRegex(ValueError, "failed or missing"):
            verify_release_portable(self.root, reference(self.root, path), self.source, selected)

    def test_preparation_and_verification_ignore_unrelated_broken_island(self) -> None:
        unrelated = self.root / "examples/projects/controller/tests/test_legacy.py"
        unrelated.write_bytes(
            b"import unittest\n\nclass LegacyFailure(unittest.TestCase):\n"
            b"    def test_legacy(self):\n        self.fail('unrelated legacy failure')\n"
        )
        stray = self.root / "examples/projects/controller/undeclared.kicad_pro"
        stray.write_bytes(b"{}\n")
        unrelated_library = self.root / "examples/libraries/status-led/PROVENANCE.md"
        unrelated_library.write_bytes(
            unrelated_library.read_bytes() + b"\nStale unused catalog evidence.\n"
        )
        self.git("add", "--all")
        self.git("-c", "user.name=Scaffold test fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Unrelated legacy island is broken")
        self.source = source_state(self.root)
        self.assertTrue(self.source.clean)
        full_lint = lint(self.root)
        self.assertEqual(full_lint.status, "FAIL")
        self.assertTrue(any("provenance record hash" in issue for issue in full_lint.issues))
        selected_lint = lint(self.root, [self.project_id])
        self.assertEqual(selected_lint.status, "PASS", selected_lint.issues)

        native = read_model(self.native_path, ValidationSummary)
        write_model(self.native_path, native.model_copy(update={
            "source": self.source, "checked_commit": self.source.commit,
        }))

        def copy_native(_root: Path, _project: object, output: Path, _cli: str | None,
                        _dependencies: Path | None, export_only: bool = False) -> None:
            self.assertFalse(export_only)
            shutil.copytree(self.native_path.parent, output)

        with patch("kicad_tooling.hwrepo.releasing.run_native", side_effect=copy_native):
            prepared = prepare(self.root, "selected", (self.project_id,), cli="kicad-cli")
        self.assertEqual(prepared.evidence.portable.path, "build/releases/selected/portable.json")
        self.assertEqual(check(self.root, prepared).status, "PASS")
        portable = read_model(
            self.root / prepared.evidence.portable.path, ScopedReleasePortableReport,
        )
        self.assertEqual(portable.projects, (self.project_id,))
        self.assertEqual(portable.source, self.source)
        archive = self.parent / "selected.zip"
        self.assertEqual(
            package(self.root, "build/releases/selected/manifest.json", archive).status,
            "PASS",
        )
        self.assertEqual(verify(archive).status, "PASS")

    def test_stale_source_and_missing_reports_fail_even_with_pass_labels(self) -> None:
        path = self.root / self.config.required_inputs[0]
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertEqual(check(self.root, self.manifest).status, "FAIL")
        self.git("restore", "--", self.config.required_inputs[0])
        self.native_path.unlink()
        self.assertIn("RELEASE_EVIDENCE", {issue.code for issue in check(self.root, self.manifest).issues})

    def test_assume_unchanged_does_not_hide_modified_source(self) -> None:
        name = self.config.required_inputs[0]
        self.git("update-index", "--assume-unchanged", "--", name)
        path = self.root / name
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(source_state(self.root).clean)
        self.assertEqual(check(self.root, self.manifest).status, "FAIL")

    def test_native_failure_cannot_be_hidden_by_rehashing_summary(self) -> None:
        native = read_model(self.native_path, ValidationSummary)
        bad = dict(native.checks)
        bad["erc"] = CheckEvidence(status="FAIL", returncode=5, findings=1)
        write_model(self.native_path, native.model_copy(update={"checks": bad}))
        with self.assertRaisesRegex(ValueError, "failed or missing"):
            verify_native(self.root, reference(self.root, self.native_path), self.source, self.project_id)

    def test_tampering_missing_extra_and_unsafe_archive_members_fail(self) -> None:
        archive = self.parent / "good.zip"
        package(self.root, self.manifest_name, archive)
        with zipfile.ZipFile(archive) as incoming:
            originals = {name: incoming.read(name) for name in incoming.namelist()}
        review_name = "payload/build/releases/test/review.txt"
        mutations = (
            {**originals, review_name: b"tampered"},
            {name: content for name, content in originals.items() if name != review_name},
            {**originals, "extra.txt": b"extra"},
            {**originals, "../escape.txt": b"unsafe"},
            {**originals, "payload/.git/config": b"unsafe"},
        )
        for index, files in enumerate(mutations):
            with self.subTest(index=index):
                bad = self.parent / f"bad-{index}.zip"
                with zipfile.ZipFile(bad, "w") as outgoing:
                    for name, content in files.items():
                        outgoing.writestr(name, content)
                destination = self.parent / f"rejected-{index}"
                with self.assertRaises((ValueError, FileNotFoundError)):
                    restore(bad, destination)
                self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
