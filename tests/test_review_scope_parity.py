"""CLI/MCP engineering-review selection parity with explicitly synthetic native evidence."""
from __future__ import annotations

import csv
import json
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from mcp import Client

from kicad_tooling import release as release_cli
from kicad_tooling.hwrepo import mcp_workflow as workflow
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ReleaseClass,
    ReleaseManifest,
    ReleaseStatus,
)
from kicad_tooling.hwrepo.product import load_repository
from kicad_tooling.hwrepo.release import expected_board_population
from tests import test_release_evidence


class ReviewScopeParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixture = test_release_evidence.ReleaseEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def synthetic_native(self, _root, project, output, _cli, _dependencies, export_only=False,
                         assembly_variant=None):
        """Selection evidence only; these minimal records cannot establish release readiness."""
        output.mkdir(parents=True)
        filename = "exports.json" if export_only else "summary.json"
        (output / filename).write_text(json.dumps({"synthetic_project": project.id}), encoding="utf-8")
        if export_only:
            product = load_repository(self.root).products[0]
            population = expected_board_population(product, "UNO_ONLY", project.id) or {}
            (output / "assembly").mkdir()
            with (output / "assembly/bom.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(("Reference", "Value", "Footprint", "PartID", "DNP"))
                for reference, part_id in sorted(population.items()):
                    writer.writerow((reference, "Synthetic", "Synthetic:Footprint", part_id, ""))

    def cli(self, *arguments: str) -> tuple[int, str]:
        output = StringIO()
        with (patch.object(sys, "argv", ["kicad_tooling.release", "prepare", "--root", str(self.root),
                                        "--format", "json", *arguments]), redirect_stdout(output)):
            code = release_cli.main()
        return code, output.getvalue()

    async def test_actual_cli_and_mcp_prepare_same_project_variant_scope(self) -> None:
        projects = ("passive-signal-reference", "arduino-uno-status-led")
        variants = ("status-indicator-system:UNO_ONLY",)
        with (patch("kicad_tooling.hwrepo.releasing.run_native", side_effect=self.synthetic_native),
              patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli", return_value="kicad-cli")):
            status, output = self.cli(
                "--release-id", "cli-scope", "--project", projects[0], "--project", projects[1],
                "--variant", variants[0], "--cli", "kicad-cli",
            )
            self.assertEqual(status, 0, output)
            cli = ReleaseManifest.model_validate_json(output)
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                result = await client.call_tool("prepare_review_scope", {
                    "release_id": "mcp-scope", "project_ids": list(projects),
                    "variants": list(variants), "runner": "local",
                })
            self.assertFalse(result.is_error, result.content)
            mcp = ReleaseManifest.model_validate_json(json.dumps(result.structured_content))
        self.assertEqual(cli.projects, mcp.projects)
        self.assertEqual(cli.variants, mcp.variants)
        self.assertEqual(cli.toolchain_id, mcp.toolchain_id)
        self.assertEqual(cli.source_commit, mcp.source_commit)
        self.assertEqual(set(cli.evidence.native), set(mcp.evidence.native))
        self.assertEqual(len(mcp.evidence.native), 5)
        self.assertEqual(cli.evidence.exports.keys(), mcp.evidence.exports.keys())
        for manifest in (cli, mcp):
            self.assertEqual(manifest.release_class, ReleaseClass.ENGINEERING_REVIEW)
            self.assertEqual(manifest.status, ReleaseStatus.CANDIDATE)
            self.assertIsNone(manifest.approval)
        product = "products/status-indicator-system/UNO_ONLY.bom.csv"
        self.assertEqual((self.root / "build/releases/cli-scope" / product).read_bytes(),
                         (self.root / "build/releases/mcp-scope" / product).read_bytes())

    def test_invalid_scope_and_mixed_toolchains_fail_before_runner_or_output(self) -> None:
        invalid = (
            ((), ()), (("missing-project",), ()),
            (("passive-signal-reference", "passive-signal-reference"), ()),
            (("controller", "passive-signal-reference"), ()),
            ((), ("malformed",)), ((), ("missing-product:STANDARD",)),
            ((), ("status-indicator-system:missing",)),
            ((), ("status-indicator-system:STANDARD", "status-indicator-system:STANDARD")),
        )
        for index, (projects, variants) in enumerate(invalid):
            with self.subTest(projects=projects, variants=variants):
                with patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli") as runner:
                    with self.assertRaises(ValueError):
                        workflow.prepare_review_scope(self.root, f"invalid-{index}", projects, variants)
                    runner.assert_not_called()
                self.assertFalse((self.root / f"build/releases/invalid-{index}").exists())

    def test_saved_portable_and_valid_native_evidence_support_same_package_lifecycle(self) -> None:
        def copy_native(_root, _project, output, _cli, _dependencies, export_only=False):
            self.assertFalse(export_only)
            shutil.copytree(self.fixture.native_path.parent, output)

        with (patch("kicad_tooling.hwrepo.releasing.run_native", side_effect=copy_native),
              patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli", return_value="kicad-cli")):
            result = workflow.prepare_review_scope(
                self.root, "retained-scope", (self.fixture.project_id,),
                portable="build/releases/test/portable.json", runner="local",
            )
        self.assertEqual(result.evidence.portable.path, "build/releases/test/portable.json")
        self.assertIsNone(result.approval)
        manifest = "build/releases/retained-scope/manifest.json"
        self.assertEqual(workflow.check_release(self.root, manifest).status, "PASS")
        self.assertEqual(workflow.package_release(self.root, manifest, "scope-package").status, "PASS")
        self.assertEqual(workflow.verify_package(self.root, "build/packages/scope-package.zip").status, "PASS")
        self.assertEqual(workflow.restore_package(
            self.root, "build/packages/scope-package.zip", "scope-restored",
        ).status, "PASS")

    def test_saved_portable_paths_and_stale_source_are_rejected_before_runner(self) -> None:
        outside = self.root.parent / "portable.json"
        shutil.copy2(self.root / "build/releases/test/portable.json", outside)
        linked = self.root / "build/linked-portable.json"
        try:
            linked.symlink_to(outside)
        except OSError as exc:
            self.skipTest(str(exc))
        for index, portable in enumerate((
            "../portable.json", str(outside), "catalog/projects.json", "build/linked-portable.json",
        )):
            with self.subTest(portable=portable):
                with patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli") as runner:
                    with self.assertRaises(ValueError):
                        workflow.prepare_review_scope(
                            self.root, f"bad-portable-{index}", (self.fixture.project_id,), portable=portable,
                        )
                    runner.assert_not_called()
                self.assertFalse((self.root / f"build/releases/bad-portable-{index}").exists())
        portable = self.root / "build/releases/test/portable.json"
        data = json.loads(portable.read_text())
        data["source"]["commit"] = "a" * 40
        portable.write_text(json.dumps(data), encoding="utf-8")
        with patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli") as runner:
            with self.assertRaises(ValueError):
                workflow.prepare_review_scope(
                    self.root, "stale-portable", (self.fixture.project_id,),
                    portable=portable.relative_to(self.root).as_posix(),
                )
            runner.assert_not_called()
        self.assertFalse((self.root / "build/releases/stale-portable").exists())

    def test_container_scope_preserves_selection_and_captures_nonprotocol_stdout(self) -> None:
        project = self.fixture.project_id
        variant = "status-indicator-system:STANDARD"
        from kicad_tooling.hwrepo.releasing import resolve_variants

        selection = resolve_variants(self.root, (variant,))
        expected = self.fixture.manifest.model_copy(update={
            "release_id": "container-scope", "projects": (project,), "variants": selection,
        })

        def command(root, argv, timeout):
            self.assertEqual(timeout, 1800)
            self.assertIn("--variant", argv)
            self.assertIn(variant, argv)
            self.assertIn("--project", argv)
            self.assertIn(project, argv)
            self.assertNotIn("--cli", argv)
            output = root / "build/releases/container-scope"
            output.mkdir(parents=True)
            write_model(output / "manifest.json", expected)
            return CommandEvidence(argv=argv, started_utc="2026-01-01T00:00:00Z", returncode=0,
                                   stdout="Dependency progress, not protocol JSON\n")

        stdout = StringIO()
        with (patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli", return_value=None),
              patch("kicad_tooling.hwrepo.mcp_workflow.run_command", side_effect=command),
              redirect_stdout(stdout)):
            report = workflow.prepare_review_scope(
                self.root, "container-scope", (project,), (variant,), runner="container",
            )
        self.assertEqual(report, expected)
        self.assertEqual(stdout.getvalue(), "")
        receipt = read_model(self.root / "build/releases/container-scope.command.json", CommandEvidence)
        self.assertIn("not protocol JSON", receipt.stdout)

    async def test_review_scope_is_unavailable_without_both_startup_capabilities(self) -> None:
        for options in ({}, {"allow_checks": True}, {"allow_exports": True}):
            with self.subTest(options=options):
                async with Client(create_server(self.root, **options), mode="legacy") as client:
                    result = await client.call_tool("prepare_review_scope", {
                        "release_id": "disabled", "project_ids": [self.fixture.project_id],
                    })
                self.assertTrue(result.is_error)
        self.assertFalse((self.root / "build/releases/disabled").exists())


if __name__ == "__main__":
    unittest.main()
