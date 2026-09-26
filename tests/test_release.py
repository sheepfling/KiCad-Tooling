"""Release-readiness tests; all release checks remain read-only and non-authorizing."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    DeviationStatus,
    InterfacesCatalog,
    LibrariesCatalog,
    PolicyIssue,
    ProductIndex,
    ProductIndexEntry,
    ProductRecord,
    ProjectKind,
    ProjectManifest,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseClass,
    ReleaseDeviation,
    ReleaseExportReport,
    ReleaseInterface,
    ReleaseLibrary,
    ReleaseManifest,
    ReleasePackageReport,
    ReleaseReadinessReport,
    ReleaseStatus,
    ReleaseVariant,
    SourceState,
)
from kicad_tooling.hwrepo.release import check, load_release_repository, selected_project_records
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.release import main as release_main
from tests.support import reference_root

ROOT = reference_root()
COMMIT = "a" * 40


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="release-readiness-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "template"
        shutil.copytree(
            ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
        )
        product_path = self.root / "examples/products/status-indicator-system/product.json"
        product = read_model(product_path, ProductRecord)
        write_model(product_path, product.model_copy(update={"maturity": "engineering_review"}))

    def manifest(self, **updates: object) -> ReleaseManifest:
        artifact_path = self.root / "docs/workflow/PRODUCT_WORKFLOW.md"
        base = ReleaseManifest(
            release_id="status-review-A",
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE,
            source_commit=COMMIT,
            toolchain_id="kicad-10.0.5",
            variants=(
                ReleaseVariant(
                    product="status-indicator-system",
                    product_revision="A",
                    variant="STANDARD",
                    variant_revision="A",
                ),
            ),
            libraries=tuple(
                ReleaseLibrary(
                    id=library.id,
                    version=library.version,
                    provenance_sha256=library.provenance_sha256,
                    licensing_sha256=library.licensing_sha256,
                )
                for library in read_model(
                    self.root / "catalog/libraries.json", LibrariesCatalog
                ).libraries
            ),
            interfaces=tuple(
                ReleaseInterface(id=interface.id, revision=interface.revision)
                for interface in read_model(
                    self.root / "catalog/interfaces.json", InterfacesCatalog
                ).interfaces
            ),
            checks={
                "repository": "PASS",
                "product_model": "PASS",
                "generation_drift": "PASS",
                "harness": "PASS",
                "kicad": "PASS",
            },
            artifacts=(
                ReleaseArtifact(
                    id="review-workflow-record",
                    kind=ReleaseArtifactKind.REVIEW_RECORD,
                    path="docs/workflow/PRODUCT_WORKFLOW.md",
                    sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    intended_use="Independent engineering review workflow record.",
                ),
            ),
        )
        return base.model_copy(update=updates)

    def git(self, _root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return COMMIT
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        raise AssertionError(f"Unexpected Git query: {args}")

    def test_self_declared_passing_checks_cannot_supply_release_evidence(self) -> None:
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, self.manifest())
        self.assertEqual(report.status, "FAIL", report.issues)
        self.assertIn("RELEASE_EVIDENCE", {finding.code for finding in report.issues})
        self.assertFalse(report.build_authorized)

    def test_commit_mismatch_and_open_deviation_fail(self) -> None:
        deviation = ReleaseDeviation(
            id="DV-1",
            scope=("training-uno-indicator",),
            owner="Configuration manager",
            reason="Demonstrates a blocked release deviation.",
            status=DeviationStatus.OPEN,
            expires=date(2026, 9, 8),
            evidence=(),
        )
        manifest = self.manifest(source_commit="b" * 40, deviations=(deviation,))
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, manifest, today=date(2026, 9, 7))
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(
            {finding.code for finding in report.issues},
            {"RELEASE_COMMIT", "DEVIATION_STATUS", "DEVIATION_EVIDENCE", "RELEASE_EVIDENCE"},
        )

    def test_prototype_rejects_candidate_training_level_controls(self) -> None:
        manifest = self.manifest(release_class=ReleaseClass.PROTOTYPE)
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, manifest)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(
            {"RELEASE_MATURITY", "RELEASE_STATUS", "RELEASE_APPROVAL", "RELEASE_TAG"}.issubset(
                {finding.code for finding in report.issues}
            )
        )

    def test_release_class_enforces_the_catalogued_assurance_floor(self) -> None:
        product_path = self.root / "examples/products/status-indicator-system/product.json"
        product = read_model(product_path, ProductRecord)
        write_model(product_path, product.model_copy(update={"maturity": "prototype"}))
        manifest = self.manifest(release_class=ReleaseClass.PROTOTYPE)
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, manifest)
        self.assertIn("RELEASE_ASSURANCE", {finding.code for finding in report.issues})

    def test_pcb_only_project_cannot_enter_a_build_release(self) -> None:
        created = new_project(self.root, "legacy-layout", ProjectKind.PCB_ONLY, "kicad-10.0.5")
        self.assertEqual(created.status, "PASS", created.issues)
        manifest = self.manifest(
            release_class=ReleaseClass.PROTOTYPE,
            projects=("legacy-layout",),
        )
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, manifest)
        self.assertIn("RELEASE_PROJECT_KIND", {finding.code for finding in report.issues})

    def test_variant_release_includes_every_declared_product_project(self) -> None:
        repository = load_release_repository(self.root, self.manifest())
        selected = selected_project_records(repository, repository.products)
        self.assertEqual(
            {project.id for project in selected},
            {
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
                "status-indicator-wiring",
                "status-indicator-harness-interface",
            },
        )

    def test_variant_release_rejects_product_view_omitted_from_index(self) -> None:
        index_path = self.root / "catalog/products.json"
        index = read_model(index_path, ProductIndex)
        entry = next(item for item in index.products if item.id == "status-indicator-system")
        shortened = entry.model_copy(
            update={
                "project_ids": tuple(
                    name for name in entry.project_ids if name != "status-indicator-wiring"
                ),
            }
        )
        write_model(
            index_path,
            index.model_copy(
                update={
                    "products": tuple(
                        shortened if item.id == entry.id else item for item in index.products
                    ),
                }
            ),
        )
        with self.assertRaisesRegex(
            ValueError, "omits product-view project status-indicator-wiring"
        ):
            load_release_repository(self.root, self.manifest())
        self.assertIn(
            "RELEASE_DEPENDENCY",
            {finding.code for finding in check(self.root, self.manifest()).issues},
        )

    def test_revision_and_library_binding_cannot_be_stale(self) -> None:
        base = self.manifest()
        variant = base.variants[0].model_copy(update={"variant_revision": "B"})
        library = base.libraries[0].model_copy(update={"version": "0.1.1"})
        manifest = base.model_copy(update={"variants": (variant,), "libraries": (library,)})
        with patch("kicad_tooling.hwrepo.release.git", side_effect=self.git):
            report = check(self.root, manifest)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(
            {"RELEASE_VARIANT_REVISION", "RELEASE_LIBRARY"}.issubset(
                {finding.code for finding in report.issues}
            )
        )

    def test_prepare_json_is_one_document_and_default_output_remains_human(self) -> None:
        manifest = self.manifest()
        argv = [
            "kicad_tooling.release",
            "prepare",
            "--root",
            str(self.root),
            "--release-id",
            manifest.release_id,
            "--project",
            "passive-signal-reference",
        ]
        with patch("kicad_tooling.hwrepo.releasing.prepare", return_value=manifest):
            machine_output = StringIO()
            with patch.object(sys, "argv", [*argv, "--json"]), redirect_stdout(machine_output):
                self.assertEqual(release_main(), 0)
            self.assertEqual(
                json.loads(machine_output.getvalue()), manifest.model_dump(mode="json")
            )

            alias_output = StringIO()
            with (
                patch.object(sys, "argv", [*argv, "--format", "json"]),
                redirect_stdout(alias_output),
            ):
                self.assertEqual(release_main(), 0)
            self.assertEqual(alias_output.getvalue(), machine_output.getvalue())

            human_output = StringIO()
            with patch.object(sys, "argv", argv), redirect_stdout(human_output):
                self.assertEqual(release_main(), 0)
        self.assertEqual(
            human_output.getvalue(),
            f"Prepared engineering_review candidate {manifest.release_id}\n"
            f"Source: {manifest.source_commit}; toolchain: {manifest.toolchain_id}\n"
            f"Retained {len(manifest.artifacts)} artifacts. Review is required before manufacture.\n"
            f"Candidate written to build/releases/{manifest.release_id}/manifest.json\n",
        )

        with (
            patch.object(sys, "argv", [*argv, "--json", "--format", "text"]),
            redirect_stderr(StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            release_main()
        self.assertEqual(error.exception.code, 2)

    def test_prepare_variant_lookup_skips_unrelated_product_and_names_bad_selection(self) -> None:
        index_path = self.root / "catalog/products.json"
        index = read_model(index_path, ProductIndex)
        broken_path = self.root / "examples/products/broken-legacy/product.json"
        broken_path.parent.mkdir(parents=True)
        broken_path.write_bytes(b"{bad JSON")
        write_model(
            index_path,
            index.model_copy(
                update={
                    "products": (
                        *index.products,
                        ProductIndexEntry(
                            id="broken-legacy",
                            path="examples/products/broken-legacy/product.json",
                            project_ids=(),
                        ),
                    )
                }
            ),
        )
        argv = [
            "kicad_tooling.release",
            "prepare",
            "--root",
            str(self.root),
            "--release-id",
            "scoped-variant",
            "--variant",
            "status-indicator-system:STANDARD",
        ]
        with (
            patch(
                "kicad_tooling.hwrepo.releasing.prepare", return_value=self.manifest()
            ) as prepared,
            patch.object(sys, "argv", argv),
            redirect_stdout(StringIO()),
        ):
            self.assertEqual(release_main(), 0)
        self.assertEqual(prepared.call_args.args[3][0].product, "status-indicator-system")

        for selection, expected in (
            ("unknown:STANDARD", "Unknown release product"),
            ("status-indicator-system:missing", "Unknown variant"),
        ):
            with self.subTest(selection=selection):
                error_text = StringIO()
                with (
                    patch.object(sys, "argv", [*argv[:-1], selection]),
                    redirect_stderr(error_text),
                    self.assertRaises(SystemExit) as error,
                ):
                    release_main()
                self.assertEqual(error.exception.code, 2)
                self.assertIn(expected, error_text.getvalue())

    def test_release_check_text_shows_issues_and_default_remains_json(self) -> None:
        manifest = self.manifest()
        manifest_name = "release-cli-test.json"
        write_model(self.root / manifest_name, manifest)
        issue = PolicyIssue(
            code="RELEASE_EVIDENCE",
            location="evidence.native",
            message="Native evidence is missing",
        )
        report = ReleaseReadinessReport(
            release_id=manifest.release_id,
            release_class=manifest.release_class,
            status="FAIL",
            issues=(issue,),
        )
        argv = [
            "kicad_tooling.release",
            "check",
            "--root",
            str(self.root),
            "--manifest",
            manifest_name,
        ]
        with patch("kicad_tooling.release.check", return_value=report):
            human_output = StringIO()
            with (
                patch.object(sys, "argv", [*argv, "--format", "text"]),
                redirect_stdout(human_output),
            ):
                self.assertEqual(release_main(), 1)
            self.assertIn("FAIL: release readiness", human_output.getvalue())
            self.assertIn(
                "RELEASE_EVIDENCE at evidence.native: Native evidence is missing",
                human_output.getvalue(),
            )

            machine_output = StringIO()
            with patch.object(sys, "argv", argv), redirect_stdout(machine_output):
                self.assertEqual(release_main(), 1)
            self.assertEqual(json.loads(machine_output.getvalue()), report.model_dump(mode="json"))

    def test_export_and_package_operations_accept_text_format(self) -> None:
        project = read_model(
            self.root / "examples/projects/arduino-uno-status-led/project.json", ProjectManifest
        )
        self.assertIsNotNone(project.release_exports)
        assert project.release_exports is not None
        export_report = ReleaseExportReport(
            project_id=project.id,
            source=SourceState(commit=COMMIT, clean=True),
            toolchain_id=project.toolchain_id,
            settings=project.release_exports,
            commands={},
            artifacts_sha256={},
            status="PASS",
        )
        output = self.root / "build/export-cli-test"
        with patch("kicad_tooling.hwrepo.exports.export", return_value=export_report):
            captured = StringIO()
            argv = [
                "kicad_tooling.release",
                "export",
                "--root",
                str(self.root),
                "--project",
                project.id,
                "--output",
                str(output),
                "--format",
                "text",
            ]
            with patch.object(sys, "argv", argv), redirect_stdout(captured):
                self.assertEqual(release_main(), 0)
            self.assertIn(f"PASS: release export for {project.id}", captured.getvalue())
            self.assertIn(f"Output: {output}", captured.getvalue())

        package_report = ReleasePackageReport(
            status="PASS",
            source_commit=COMMIT,
            package="/tmp/release.zip",
            package_sha256="b" * 64,
            manifest="build/releases/test/manifest.json",
        )
        for command, arguments in (
            ("package", ["--manifest", package_report.manifest, "--output", "/tmp/release.zip"]),
            ("verify", ["--archive", package_report.package]),
            ("restore", ["--archive", package_report.package, "--destination", "/tmp/restored"]),
        ):
            with (
                self.subTest(command=command),
                patch(f"kicad_tooling.hwrepo.packaging.{command}", return_value=package_report),
            ):
                captured = StringIO()
                argv = [
                    "kicad_tooling.release",
                    command,
                    "--root",
                    str(self.root),
                    *arguments,
                    "--format",
                    "text",
                ]
                with patch.object(sys, "argv", argv), redirect_stdout(captured):
                    self.assertEqual(release_main(), 0)
                self.assertIn(f"PASS: release {command}", captured.getvalue())
                self.assertIn("SHA-256: " + package_report.package_sha256, captured.getvalue())
                if command == "restore":
                    self.assertIn(f"Restored to: {Path('/tmp/restored')}", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
