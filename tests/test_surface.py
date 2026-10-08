"""Public declaration coverage must not silently drift between CLI and MCP."""

from __future__ import annotations

import builtins
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.models import (
    ToolMcpSnapshot,
    ToolSurfaceReport,
    ToolSurfacesCatalog,
)
from kicad_tooling.hwrepo.surface import (
    CATALOG,
    discover_mcp,
    inspect_tool_surfaces,
)
from tests.support import SOURCE_ROOT, TEST_ROOT, reference_root


class ToolSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kicad-surfaces-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        shutil.copytree(
            SOURCE_ROOT / "kicad_tooling",
            self.root / "kicad_tooling",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(
            TEST_ROOT, self.root / "tests", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copy2(TEST_ROOT.parent / "pyproject.toml", self.root / "pyproject.toml")
        (self.root / "catalog").mkdir()
        shutil.copy2(SOURCE_ROOT / CATALOG, self.root / CATALOG)
        for attribute, value in (
            ("SOURCE_ROOT", self.root),
            ("PACKAGE_ROOT", self.root / "kicad_tooling"),
        ):
            patcher = patch(f"kicad_tooling.hwrepo.surface.{attribute}", value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def report(self) -> ToolSurfaceReport:
        with patch("kicad_tooling.hwrepo.surface.find_spec", return_value=None):
            return inspect_tool_surfaces(reference_root())

    def messages(self, report: ToolSurfaceReport, code: str) -> str:
        return "\n".join(issue.message for issue in report.issues if issue.code == code)

    def replace_source(self, path: str, old: str, new: str) -> None:
        source = self.root / path
        text = source.read_text(encoding="utf-8")
        self.assertIn(old, text)
        source.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_real_checkout_and_full_registration_are_tracked(self) -> None:
        report = inspect_tool_surfaces(reference_root(), require_live_mcp=True)
        self.assertEqual(report.status, "PASS", report.model_dump_json(indent=2))
        self.assertEqual(report.mcp_verification, "LIVE")
        self.assertFalse(report.build_authorized)
        self.assertEqual(report.coverage_status, "PASS")
        self.assertEqual(report.parity_status, "PASS")
        self.assertEqual(report.behavior_verification, "NOT_RUN")
        self.assertEqual(
            {item.scope for item in report.capabilities}, {"core", "administration", "adapter"}
        )
        self.assertTrue(
            all(
                item.alignment == "aligned" and not item.gaps
                for item in report.capabilities
                if item.scope == "core"
            )
        )
        self.assertTrue(
            {"prepare_parts", "save_parts_preferences", "inspect_tool_surfaces"}
            <= {tool.name for tool in report.mcp}
        )
        self.assertEqual(parse_model_text(report.model_dump_json(), ToolSurfaceReport), report)

    def test_reference_fixture_keeps_surface_policy_in_the_tooling_package(self) -> None:
        root = reference_root()
        self.assertFalse((root / "kicad_tooling").exists())
        self.assertFalse((root / "catalog/tool-surfaces.json").exists())
        self.assertEqual(
            self.report().capabilities,
            read_model(SOURCE_ROOT / CATALOG, ToolSurfacesCatalog).capabilities,
        )

    def test_base_runtime_never_imports_optional_mcp(self) -> None:
        original = builtins.__import__

        def deny_mcp(name, *args, **kwargs):
            if name == "mcp" or name.startswith("mcp."):
                raise AssertionError("Static coverage must not import the optional SDK")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=deny_mcp):
            report = self.report()
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(report.mcp_verification, "STATIC_ONLY")
        with patch("kicad_tooling.hwrepo.surface.find_spec", return_value=None):
            required = inspect_tool_surfaces(reference_root(), require_live_mcp=True)
        self.assertEqual(required.status, "FAIL")
        self.assertEqual(required.mcp_verification, "UNAVAILABLE")
        self.assertIn("pinned dev or mcp extra", self.messages(required, "live_mcp_unavailable"))

    def test_new_cli_module_requires_snapshot_and_classification(self) -> None:
        (self.root / "kicad_tooling/future.py").write_text(
            "def main():\n    return 0\n",
            encoding="utf-8",
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("kicad_tooling.future", self.messages(report, "untracked_surface"))
        self.assertIn("kicad_tooling.future", self.messages(report, "unmapped_surface"))

    def test_new_subcommand_is_detected_on_an_existing_cli(self) -> None:
        self.replace_source(
            "kicad_tooling/hardware.py", '"verify-snapshot"))', '"verify-snapshot", "publish"))'
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("publish", self.messages(report, "cli_signature_drift"))
        self.assertIn("kicad_tooling.hardware publish", self.messages(report, "unmapped_surface"))

    def test_subparser_aliases_are_discovered(self) -> None:
        (self.root / "kicad_tooling/future.py").write_text(
            "import argparse\ndef main():\n"
            "    parser = argparse.ArgumentParser()\n"
            "    commands = parser.add_subparsers()\n"
            '    command = commands.add_parser("export", aliases=("save",))\n'
            '    command.add_argument("--strict")\n',
            encoding="utf-8",
        )
        report = self.report()
        future = next(item for item in report.cli if item.module == "kicad_tooling.future")
        self.assertEqual(future.commands, ("export", "save"))
        self.assertEqual(future.options, ("--strict",))
        self.assertIn("kicad_tooling.future save", self.messages(report, "unmapped_surface"))

    def test_changed_cli_option_records_added_and_removed_names(self) -> None:
        self.replace_source("kicad_tooling/verify.py", '"--detail"', '"--verbosity"')
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        message = self.messages(report, "cli_signature_drift")
        self.assertIn("added ['--verbosity']", message)
        self.assertIn("removed ['--detail']", message)

    def test_new_mcp_tool_requires_snapshot_and_classification(self) -> None:
        self.replace_source(
            "kicad_tooling/hwrepo/mcp_server.py",
            "    return server\n",
            "    def future_tool(project_id: str) -> str:\n"
            "        return project_id\n"
            "    server.tool()(future_tool)\n"
            "    return server\n",
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("future_tool", self.messages(report, "untracked_surface"))
        self.assertIn("future_tool", self.messages(report, "unmapped_surface"))

    def test_mcp_parameter_and_removal_drift_are_detected(self) -> None:
        self.replace_source(
            "kicad_tooling/hwrepo/mcp_server.py",
            "def list_projects()",
            "def list_projects(limit: int = 10)",
        )
        self.replace_source(
            "kicad_tooling/hwrepo/mcp_server.py",
            "    server.tool(annotations=READ_ONLY)(get_project)\n",
            "",
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("limit", self.messages(report, "mcp_signature_drift"))
        self.assertIn("get_project", self.messages(report, "stale_surface"))
        self.assertIn("get_project", self.messages(report, "stale_mapping"))

    def test_live_registration_disagreement_is_not_hidden_by_static_catalog(self) -> None:
        async def changed_registration(root: Path) -> tuple[ToolMcpSnapshot, ...]:
            return (*discover_mcp(self.root), ToolMcpSnapshot(name="runtime_only_tool"))

        with patch("kicad_tooling.hwrepo.surface._live_mcp", side_effect=changed_registration):
            report = inspect_tool_surfaces(reference_root(), require_live_mcp=True)
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.mcp_verification, "LIVE")
        self.assertIn("runtime_only_tool", self.messages(report, "mcp_registration_drift"))

    def test_unsupported_dynamic_declarations_fail_instead_of_disappearing(self) -> None:
        self.replace_source(
            "kicad_tooling/hardware.py",
            '("check", "generate", "snapshot", "verify-snapshot")',
            "commands_from_configuration",
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("literal strings", self.messages(report, "surface_discovery"))
        shutil.copy2(
            SOURCE_ROOT / "kicad_tooling/hardware.py", self.root / "kicad_tooling/hardware.py"
        )
        self.replace_source(
            "kicad_tooling/hwrepo/mcp_server.py",
            "server.tool(annotations=READ_ONLY)(get_project)",
            "server.tool(annotations=READ_ONLY)(tool_from_configuration())",
        )
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("unsupported MCP", self.messages(report, "surface_discovery"))

    def test_catalog_requires_complete_and_honest_classifications(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        mappings = tuple(
            item.model_copy(update={"alignment": "partial", "gaps": ("Missing order quantities",)})
            if item.id == "parts-preparation"
            else item
            for item in catalog.capabilities
            if item.id != "project-verification"
        )
        write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("parts-preparation", self.messages(report, "core_parity_gap"))
        self.assertIn("check_project", self.messages(report, "unmapped_surface"))

    def test_documenting_a_core_gap_does_not_make_parity_pass(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        mappings = tuple(
            item.model_copy(
                update={
                    "alignment": "partial",
                    "gaps": ("MCP lacks a workflow mode",),
                }
            )
            if item.id == "parts-preparation"
            else item
            for item in catalog.capabilities
        )
        write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
        report = self.report()
        self.assertEqual(report.coverage_status, "PASS")
        self.assertEqual(report.parity_status, "FAIL")
        self.assertEqual(report.status, "FAIL")
        self.assertIn("Core workflows", self.messages(report, "core_parity_gap"))

    def test_core_workflows_cannot_be_reclassified_as_exceptions(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        mappings = tuple(
            item.model_copy(
                update={
                    "scope": "administration",
                    "exception": "Ignore this missing behavior",
                }
            )
            if item.id == "model-population"
            else item
            for item in catalog.capabilities
        )
        write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertIn("model-population", self.messages(report, "core_scope"))

    def test_core_behavior_tests_are_required_and_resolved_without_imports(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        for references, code in (
            ((), "missing_parity_tests"),
            (("tests.test_missing.NotThere.test_behavior",), "missing_parity_test"),
        ):
            mappings = tuple(
                item.model_copy(update={"parity_tests": references})
                if item.id == "project-inventory"
                else item
                for item in catalog.capabilities
            )
            write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
            report = self.report()
            self.assertEqual(report.parity_status, "FAIL")
            self.assertIn(
                "Core parity" if not references else "does not exist", self.messages(report, code)
            )
        self.assertEqual(report.behavior_verification, "NOT_RUN")

    def test_adapter_constraints_do_not_mask_or_create_functional_gaps(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        mappings = tuple(
            item.model_copy(update={"constraints": ("MCP uses startup permissions",)})
            if item.id == "project-inventory"
            else item
            for item in catalog.capabilities
        )
        write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
        report = self.report()
        self.assertEqual(report.status, "PASS", report.issues)

    def test_installed_package_does_not_claim_test_reference_resolution(self) -> None:
        (self.root / "pyproject.toml").unlink()
        report = self.report()
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(report.behavior_verification, "NOT_RUN")
        self.assertTrue(any("NOT_AVAILABLE" in note for note in report.notes))
        self.assertTrue(any("test references were not resolved" in note for note in report.notes))

    def test_admin_exceptions_need_a_reason(self) -> None:
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        mappings = tuple(
            item.model_copy(update={"exception": None})
            if item.id == "repository-lifecycle"
            else item
            for item in catalog.capabilities
        )
        write_model(self.root / CATALOG, catalog.model_copy(update={"capabilities": mappings}))
        self.assertIn("explicit reason", self.messages(self.report(), "missing_exception"))

    def test_malformed_catalog_is_a_typed_failure(self) -> None:
        (self.root / CATALOG).write_text('{"schema_version":"future"}', encoding="utf-8")
        report = self.report()
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(self.messages(report, "surface_discovery"))
        self.assertEqual(report.capabilities, ())

    def test_serialized_catalog_and_report_reject_unknown_fields_and_wrong_types(self) -> None:
        report = self.report()
        with self.assertRaises(ValidationError):
            parse_model_text(
                report.model_dump_json().replace(
                    '"build_authorized":false', '"build_authorized":true'
                ),
                ToolSurfaceReport,
            )
        catalog = read_model(self.root / CATALOG, ToolSurfacesCatalog)
        with self.assertRaises(ValidationError):
            parse_model_text(
                catalog.model_dump_json().replace('"schema_version":"2"', '"schema_version":1'),
                ToolSurfacesCatalog,
            )
        with self.assertRaises(ValidationError):
            parse_model_text(
                catalog.model_dump_json()[:-1] + ',"unknown":true}', ToolSurfacesCatalog
            )

    def test_cli_uses_explicit_root_from_an_unrelated_directory(self) -> None:
        result = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.surface",
                "--root",
                str(reference_root()),
                "--format",
                "json",
                "--require-live-mcp",
            ),
            cwd=self.root,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = parse_model_text(result.stdout, ToolSurfaceReport)
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.mcp_verification, "LIVE")


if __name__ == "__main__":
    unittest.main()
