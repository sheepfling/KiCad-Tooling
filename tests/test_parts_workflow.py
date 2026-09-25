"""Integration guards for source-bound, local-only purchasing receipts."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ComponentIdentity,
    PartRecord,
    PartsCatalog,
    PartStatus,
    ProjectConfig,
    ProjectKind,
    ProjectManifest,
    PurchasingPreferences,
    PurchasingReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.parts_view import render_html
from kicad_tooling.hwrepo.parts_workflow import (
    init_preferences,
    input_hashes,
    load_preferences,
    new_receipt,
    prepare,
    save_report,
)
from kicad_tooling.validate import hashes
from tests.support import reference_root

NETLIST = """<export><components>
<comp ref="R1"><value>1k</value><footprint>Pilot:R_Test</footprint>
<fields><field name="PART_ID">resistor-1k</field></fields></comp>
<comp ref="R2"><value>1k</value><footprint>Pilot:R_Test</footprint>
<fields><field name="PART_ID">resistor-1k</field></fields></comp>
<comp ref="C1"><value>Unfitted</value><property name="dnp"/></comp>
</components><nets/></export>"""


def command(stdout: str = "") -> CommandEvidence:
    return CommandEvidence(
        argv=("synthetic-kicad-cli",), started_utc="2026-09-24T00:00:00+00:00",
        returncode=0, stdout=stdout,
    )


class FixtureRunner:
    selected_runner = "local"

    def __init__(self, during_export: Callable[[], None] | None = None) -> None:
        self.during_export = during_export

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence:
        return command(config.kicad_version + "\n")

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence:
        output.write_text(NETLIST, encoding="utf-8")
        if self.during_export is not None:
            self.during_export()
        return command()


class PartsWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="parts-workflow-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.project_id = "controller"
        self.manifest_path = self.root / "examples/projects/controller/project.json"
        self.island = self.manifest_path.parent
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(self.manifest_path, manifest.model_copy(update={
            "component_identity": ComponentIdentity(required=True, part_ids=("resistor-1k",)),
        }))
        self.catalog_path = self.root / "catalog/parts.json"
        write_model(self.catalog_path, PartsCatalog(schema_version="0.1", parts=(PartRecord(
            id="resistor-1k", revision="A", description="Integration-test identity only",
            part_class="resistor", unit="each", manufacturer="Vishay",
            mpn="MRS25000C1001FCT00", datasheet_url="https://example.invalid/test-only",
            lifecycle="active", status=PartStatus.APPROVED,
        ),)))
        self.config = load_config(self.root, self.manifest_path)
        self.native = self.root / "build/native/controller"
        self.native.mkdir(parents=True)
        self.write_summary()

    def write_summary(self, netlist: str = NETLIST) -> None:
        (self.native / "netlist.xml").write_text(netlist, encoding="utf-8")
        write_model(self.native / "netlist.command.json", command())
        current = hashes(self.root, self.config.source_roots)
        self.summary = ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00", checked_commit="LOCAL_UNBOUND",
            project_id=self.project_id, project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(status="PASS",
                    observed_version=self.config.kicad_version, image=self.config.image),
                "netlist": CheckEvidence(status="FAIL", returncode=0,
                    error="Independent electrical contract differs"),
            },
            status="FAIL", artifacts_sha256={
                "netlist.xml": digest(self.native / "netlist.xml"),
                "netlist.command.json": digest(self.native / "netlist.command.json"),
            },
        )
        write_model(self.native / "summary.json", self.summary)

    def review(self, **options: object) -> PurchasingReport:
        return prepare(self.root, self.project_id,
            new_receipt(self.root, self.project_id, None), FixtureRunner(),
            native_summary=self.native, **options)

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run((
            sys.executable, "-B", "-m", "kicad_tooling.parts", "--root", str(self.root),
            "--project", self.project_id, *arguments,
        ), cwd=self.root, text=True, capture_output=True, check=False)

    def test_native_metadata_review_preserves_source_and_authority_boundaries(self) -> None:
        original = hashes(self.root, self.config.source_roots)
        report = self.review(boards=10, spare_percent=10, spare_minimum=3)
        self.assertEqual(report.status, "READY_FOR_ORDER_REVIEW", report.issues)
        self.assertIsNotNone(report.plan)
        assert report.plan is not None
        self.assertEqual(report.plan.lines[0].quantity, 23)
        self.assertEqual(report.plan.excluded_references, ("C1",))
        self.assertFalse(report.purchase_authorized)
        self.assertFalse(report.build_authorized)
        self.assertEqual(report.native_status, "FAIL")
        self.assertEqual(hashes(self.root, self.config.source_roots), original)
        receipt = Path(report.receipt_dir)
        self.assertEqual(digest(receipt / "netlist.xml"), report.netlist_sha256)
        self.assertEqual((receipt / "netlist.xml").read_bytes(),
                         (self.native / "netlist.xml").read_bytes())
        self.assertTrue((receipt / "digikey.csv").is_file())
        save_report(receipt, report)
        self.assertEqual(read_model(receipt / "report.json", PurchasingReport), report)

    def test_source_catalog_and_preferences_drift_blocks_publication(self) -> None:
        preferences = self.island / "docs/purchasing.json"
        write_model(preferences, PurchasingPreferences(boards=4))
        paths = (self.island / "kicad/controller.kicad_sch", self.catalog_path, preferences)
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                def mutate(path: Path = path, original: bytes = original) -> None:
                    path.write_bytes(original + b"\n")

                runner = FixtureRunner(mutate)
                receipt = new_receipt(self.root, self.project_id, None)
                report = prepare(self.root, self.project_id, receipt, runner)
                self.assertEqual(report.status, "BLOCKED", report)
                self.assertIn("changed", " ".join(report.issues).lower())
                self.assertFalse((receipt / "digikey.csv").exists())
                path.write_bytes(original)

    def test_wrong_project_and_tampered_native_evidence_are_blocked(self) -> None:
        write_model(self.native / "summary.json", self.summary.model_copy(
            update={"project_id": "passive-signal-reference"},
        ))
        report = self.review()
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("another project", report.issues[0])
        write_model(self.native / "summary.json", self.summary)
        (self.native / "netlist.xml").write_text(NETLIST + "\n", encoding="utf-8")
        report = self.review()
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("artifact hash", report.issues[0])
        self.assertFalse(Path(report.receipt_dir, "digikey.csv").exists())

    def test_stale_native_source_is_blocked(self) -> None:
        source = self.island / "kicad/controller.kicad_sch"
        source.write_bytes(source.read_bytes() + b"\n")
        report = self.review()
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("source", report.issues[0].lower())

    def test_default_explicit_and_run_only_preferences(self) -> None:
        self.assertEqual(load_preferences(self.root, self.project_id, None, None, None, None),
                         PurchasingPreferences())
        path = self.island / "docs/purchasing.json"
        saved = PurchasingPreferences(boards=4, spare_percent=5, spare_minimum=2,
                                      digikey_skus={"resistor-1k": "541-1KABC-ND"})
        write_model(path, saved)
        self.assertEqual(load_preferences(self.root, self.project_id, None, None, None, None),
                         saved)
        original = path.read_bytes()
        overridden = load_preferences(self.root, self.project_id, path, 10, 20, 0)
        self.assertEqual((overridden.boards, overridden.spare_percent, overridden.spare_minimum),
                         (10, 20, 0))
        self.assertEqual(overridden.digikey_skus, saved.digikey_skus)
        self.assertEqual(path.read_bytes(), original)
        alternative = self.root / "build/other-preferences.json"
        write_model(alternative, PurchasingPreferences(boards=7))
        self.assertEqual(load_preferences(self.root, self.project_id, alternative,
                                         None, None, None).boards, 7)

    def test_malformed_preferences_return_readable_blocked_reports(self) -> None:
        path = self.island / "docs/purchasing.json"
        for raw in ("[]", "null", "5", '{"boards":true}', '{"boards":1,"boards":2}'):
            with self.subTest(raw=raw):
                path.write_text(raw, encoding="utf-8")
                report = self.review()
                self.assertEqual(report.status, "BLOCKED")
                self.assertIn(str(path), report.issues[0])
                self.assertFalse(Path(report.receipt_dir, "digikey.csv").exists())

    def test_hashes_follow_custom_declared_contract_path(self) -> None:
        manifest = read_model(self.manifest_path, ProjectManifest)
        original = self.island / manifest.checks
        custom = self.island / "tests/electrical-contract.json"
        original.rename(custom)
        write_model(self.manifest_path, manifest.model_copy(
            update={"checks": "tests/electrical-contract.json"},
        ))
        bound = input_hashes(self.root, self.project_id, None)
        self.assertIn(custom.relative_to(self.root).as_posix(), bound)
        self.assertNotIn(original.relative_to(self.root).as_posix(), bound)
        self.assertEqual(self.review().status, "READY_FOR_ORDER_REVIEW")

    def test_init_preferences_refuses_overwrite_and_paths_outside_island_docs(self) -> None:
        path = self.island / "docs/purchasing.json"
        saved = PurchasingPreferences(boards=3)
        self.assertEqual(init_preferences(self.root, self.project_id, path, saved), path)
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            init_preferences(self.root, self.project_id, path, PurchasingPreferences())
        self.assertEqual(path.read_bytes(), before)
        for unsafe in (Path("../escaped.json"), Path("catalog/preferences.json"),
                       self.root.parent / "escaped.json",
                       self.island / "docs/preferences.txt"):
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                init_preferences(self.root, self.project_id, unsafe, saved)
        self.assertFalse((self.root.parent / "escaped.json").exists())

    def test_receipts_are_fresh_and_confined_to_build(self) -> None:
        path = new_receipt(self.root, self.project_id, Path("build/parts-review"))
        with self.assertRaises(FileExistsError):
            new_receipt(self.root, self.project_id, path)
        for unsafe in (Path("build"), Path("docs/receipt"), Path("../receipt")):
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                new_receipt(self.root, self.project_id, unsafe)

    def test_direct_prepare_cannot_write_into_authored_docs(self) -> None:
        output = self.island / "docs"
        report = prepare(self.root, self.project_id, output, FixtureRunner(),
                         native_summary=self.native)
        self.assertEqual(report.status, "BLOCKED")
        self.assertFalse((output / "netlist.xml").exists())
        self.assertFalse((output / "digikey.csv").exists())

    def test_cli_applies_overrides_without_rewriting_preferences(self) -> None:
        path = self.island / "docs/purchasing.json"
        write_model(path, PurchasingPreferences(boards=2, spare_minimum=3))
        before = path.read_bytes()
        result = self.cli("--native-summary", str(self.native), "--preferences", str(path),
                          "--boards", "10", "--spare-percent", "10", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["plan"]["lines"][0]["quantity"], 23)
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue(Path(report["receipt_dir"], "index.html").is_file())

    def test_cli_errors_have_deliberate_exit_codes(self) -> None:
        for arguments in (("--boards", "0"), ("--spare-percent", "101"),
                          ("--boards", "1.5"), ("--output", "docs/no-output")):
            with self.subTest(arguments=arguments):
                result = self.cli(*arguments)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn("Traceback", result.stderr)
        result = self.cli("--runner", "local", "--cli", "missing-kicad-parts-test",
                          "--format", "json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_malformed_preferences_produces_blocked_receipt(self) -> None:
        (self.island / "docs/purchasing.json").write_text("null", encoding="utf-8")
        result = self.cli("--native-summary", str(self.native), "--format", "json")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(Path(report["receipt_dir"], "index.html").is_file())
        self.assertNotIn("Traceback", result.stderr)

    def test_html_escapes_source_text_and_exposes_failed_native_validation(self) -> None:
        self.write_summary(NETLIST.replace("<value>1k</value>",
            "<value>&lt;img src=x onerror=alert(1)&gt;</value>"))
        report = self.review()
        self.assertEqual(report.status, "READY_FOR_ORDER_REVIEW", report.issues)
        html = render_html(report)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("native validation failed", html.lower())
        self.assertIn('href="digikey.csv"', html)
