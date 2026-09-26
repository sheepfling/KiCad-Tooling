"""Actual CLI and MCP generation outputs share selection and review-only semantics."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from tests.support import reference_root


def files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class GenerationParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="generation-parity-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.hardware",
                "generate",
                "--root",
                str(self.root),
                *arguments,
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )

    async def test_cli_and_mcp_generate_identical_scoped_files(self) -> None:
        selections = (
            (),
            (("--project", "project_ids", "arduino-uno-status-led"),),
            (("--product", "product_ids", "status-indicator-system"),),
            (("--tag", "tags", "status-led"),),
            (
                ("--project", "project_ids", "controller"),
                ("--tag", "tags", "reference"),
                ("--exclude-tag", "exclude_tags", "status-led"),
            ),
            (
                ("--project", "project_ids", "controller"),
                ("--project", "project_ids", "arduino-uno-status-led"),
            ),
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for index, selection in enumerate(selections):
                with self.subTest(selection=selection):
                    output = self.root / "build/cli" / str(index)
                    arguments = ["--output", str(output)]
                    mcp_arguments = {"view_id": f"scope-{index}"}
                    for flag, name, value in selection:
                        arguments.extend((flag, value))
                        mcp_arguments.setdefault(name, []).append(value)
                    cli = self.cli(*arguments)
                    self.assertEqual(cli.returncode, 0, cli.stderr + cli.stdout)
                    cli_report = json.loads(cli.stdout)
                    mcp = await client.call_tool("generate_views", mcp_arguments)
                    self.assertFalse(mcp.is_error, mcp.content)
                    mcp_report = mcp.structured_content
                    self.assertFalse(cli_report["build_authorized"])
                    self.assertFalse(mcp_report["build_authorized"])
                    mcp_output = self.root / mcp_report["directory"]
                    self.assertEqual(files(output), files(mcp_output))
                    self.assertEqual(set(cli_report["generated"]), set(files(output)))
                    if selection:
                        self.assertFalse(any(name.startswith("schemas/") for name in files(output)))
                    else:
                        self.assertIn("schemas/product-v1.schema.json", files(output))
                    if index in {1, 2, 3, 5}:
                        self.assertTrue(any(name.endswith(".bom.csv") for name in files(output)))
                    if index == 4:
                        self.assertEqual(files(output), {})

    def test_default_generation_preserves_existing_locations_and_regeneration(self) -> None:
        first = self.cli()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        report = json.loads(first.stdout)
        self.assertNotIn("output", report)
        self.assertIn("schemas/product-v1.schema.json", report["generated"])
        bom = next(name for name in report["generated"] if name.endswith(".bom.csv"))
        self.assertTrue(bom.startswith("examples/products/status-indicator-system/build/"))
        original = {name: (self.root / name).read_bytes() for name in report["generated"]}
        (self.root / bom).write_bytes(b"stale generated output")
        repeated = self.cli()
        self.assertEqual(repeated.returncode, 0, repeated.stderr + repeated.stdout)
        self.assertEqual(
            {name: (self.root / name).read_bytes() for name in report["generated"]}, original
        )

    def test_invalid_selection_fails_before_fresh_output_creation(self) -> None:
        for index, arguments in enumerate(
            (
                ("--project", "missing"),
                ("--product", "missing"),
                ("--tag", "missing"),
                ("--project", "controller", "--project", "controller"),
                ("--project", "controller", "--exclude-tag", "training"),
            )
        ):
            with self.subTest(arguments=arguments):
                output = self.root / f"build/invalid-{index}"
                result = self.cli("--output", str(output), *arguments)
                self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
                self.assertEqual(json.loads(result.stdout)["status"], "FAIL")
                self.assertFalse(output.exists())

    def test_optional_output_is_fresh_and_separate_from_authored_source(self) -> None:
        output = self.base / "external-view"
        result = self.cli("--output", str(output), "--tag", "status-led")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        original = files(output)
        repeated = self.cli("--output", str(output), "--tag", "status-led")
        self.assertEqual(repeated.returncode, 1)
        self.assertEqual(files(output), original)
        for unsafe in (self.root, self.root / "catalog/new-output", self.root / "build"):
            with self.subTest(unsafe=unsafe):
                result = self.cli("--output", str(unsafe))
                self.assertEqual(result.returncode, 1)
                self.assertIn("below build/", json.loads(result.stdout)["error"])
        self.assertFalse((self.root / "catalog/new-output").exists())

    def test_selectors_on_other_hardware_commands_are_explicit_errors(self) -> None:
        result = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.hardware",
                "check",
                "--root",
                str(self.root),
                "--project",
                "controller",
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("only valid with generate", result.stderr)


if __name__ == "__main__":
    unittest.main()
