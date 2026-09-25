"""Actual CLI/MCP conversion parity with an explicitly synthetic external native CLI."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ForeignFormat, ForeignPcbReport
from tests import test_artifact_parity
from tests.support import SOURCE_ROOT, initialize_git, reference_root
from tests.test_contract_coach import fake_executable


class McpConversionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-conversion-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"))
        initialize_git(self.root)
        self.source = self.root / "build/imports/vendor.brd"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("Synthetic foreign PCB, no verified geometry\n")
        binary = self.base / "native-bin"
        binary.mkdir()
        self.executable = fake_executable(binary / "kicad-cli", '''import json
import sys
from pathlib import Path
args = sys.argv[1:]
if args == ["version"]:
    print("10.0.5")
    raise SystemExit(0)
if args[:2] != ["pcb", "import"]:
    raise SystemExit("Unexpected synthetic command: " + repr(args))
source = Path(args[-1])
text = source.read_text()
if "command-failure" in text:
    print("Synthetic conversion failure", file=sys.stderr)
    raise SystemExit(17)
Path(args[args.index("--output") + 1]).write_text("(kicad_pcb (version 20260206))\\n")
selected = args[args.index("--format") + 1]
Path(args[args.index("--report-file") + 1]).write_text(json.dumps({
    "source_format": "eagle" if selected == "auto" else selected,
    "layer_mapping": {"top": "F.Cu"},
    "errors": ["Synthetic layer mapping error"] if "report-error" in text else [],
    "warnings": ["Synthetic geometry needs engineering review"],
}))
if "source-drift" in text:
    source.write_text(text + "changed during conversion\\n")
''')
        self.environment = patch.dict(os.environ, {
            "PATH": str(binary) + os.pathsep + os.environ.get("PATH", ""),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    async def cli(self, source: Path, project: str, input_format: str = "auto",
                  toolchain: str = "kicad-10.0.5") -> tuple[int, ForeignPcbReport]:
        result = await asyncio.to_thread(subprocess.run, (
            sys.executable, "-B", "-m", "kicad_tooling.template", "convert-pcb", "--root", str(self.root),
            "--source", str(source), "--project-id", project, "--toolchain", toolchain,
            "--input-format", input_format, "--runner", "local", "--format", "json",
        ), cwd=SOURCE_ROOT, text=True, capture_output=True, check=False, timeout=60)
        self.assertIn(result.returncode, (0, 1), result.stderr + result.stdout)
        return result.returncode, ForeignPcbReport.model_validate_json(result.stdout)

    async def call(self, client, source: Path, project: str, input_format: str = "auto",
                   toolchain: str = "kicad-10.0.5") -> ForeignPcbReport:
        result = await client.call_tool("convert_pcb", {
            "source": str(source), "project_id": project, "toolchain_id": toolchain,
            "input_format": input_format, "runner": "local",
        })
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return ForeignPcbReport.model_validate_json(json.dumps(result.structured_content))

    def authored_snapshot(self) -> dict[str, str]:
        return {path.relative_to(self.root).as_posix(): digest(path)
                for path in self.root.rglob("*") if path.is_file()
                and path.relative_to(self.root).parts[0] not in {"build", ".git"}}

    def assert_equivalent(self, cli: ForeignPcbReport, mcp: ForeignPcbReport) -> None:
        self.assertEqual(test_artifact_parity.ArtifactParityTests.semantic(cli, Path(cli.run_directory)),
                         test_artifact_parity.ArtifactParityTests.semantic(mcp, Path(mcp.run_directory)))
        for report in (cli, mcp):
            directory = Path(report.run_directory)
            self.assertTrue(directory.is_relative_to(self.root / "build/diagnostics"))
            self.assertEqual(read_model(directory / "conversion.json", ForeignPcbReport), report)
            self.assertTrue(report.review_required)
            self.assertFalse(report.build_authorized)
            self.assertFalse((self.root / "projects" / report.project_id).exists())

    async def test_all_formats_cli_and_mcp_match_without_registering_source(self) -> None:
        before = self.authored_snapshot()
        source_hash = digest(self.source)
        async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                          mode="legacy") as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertFalse(tools["convert_pcb"].annotations.read_only_hint)
            for input_format in ForeignFormat.__args__:
                with self.subTest(input_format=input_format):
                    project = f"foreign-{input_format}"
                    code, cli = await self.cli(self.source, project, input_format)
                    mcp = await self.call(client, self.source, project, input_format)
                    self.assertEqual(code, 0, cli.error)
                    self.assert_equivalent(cli, mcp)
                    self.assertEqual(mcp.status, "PASS", mcp.error)
                    self.assertEqual(mcp.source_sha256, source_hash)
                    self.assertTrue(mcp.import_preview.dry_run)
                    self.assertEqual(mcp.import_preview.status, "PASS")
                    self.assertTrue(mcp.native_summary.warnings)
                    self.assertEqual(digest(self.source), source_hash)
                    self.assertNotEqual(cli.run_directory, mcp.run_directory)
        self.assertEqual(self.authored_snapshot(), before)

    async def test_conversion_failure_receipts_match_cli(self) -> None:
        async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                          mode="legacy") as client:
            for mode in ("command-failure", "report-error", "source-drift"):
                with self.subTest(mode=mode):
                    self.source.write_text(mode)
                    code, cli = await self.cli(self.source, "failed-conversion")
                    self.source.write_text(mode)
                    mcp = await self.call(client, self.source, "failed-conversion")
                    self.assertEqual(code, 1)
                    self.assert_equivalent(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL")
                    self.assertIsNone(mcp.next_command)
            for source, project, toolchain in (
                (self.source.with_suffix(".missing"), "missing-source", "kicad-10.0.5"),
                (self.source, "bad/id", "kicad-10.0.5"),
                (self.source, "unknown-toolchain", "missing"),
            ):
                with self.subTest(project=project):
                    code, cli = await self.cli(source, project, toolchain=toolchain)
                    mcp = await self.call(client, source, project, toolchain=toolchain)
                    self.assertEqual(code, 1)
                    self.assert_equivalent(cli, mcp)

    async def test_conversion_requires_checks_and_exports_and_explicit_import_roots(self) -> None:
        request = {"source": str(self.source), "project_id": "disabled", "toolchain_id": "kicad-10.0.5"}
        for options in ({}, {"allow_checks": True}, {"allow_exports": True}, {"allow_writes": True}):
            with self.subTest(options=options):
                async with Client(create_server(self.root, **options), mode="legacy") as client:
                    self.assertNotIn("convert_pcb", {item.name for item in (await client.list_tools()).tools})
                    self.assertTrue((await client.call_tool("convert_pcb", request)).is_error)
        self.assertFalse((self.root / "build/diagnostics").exists())
        external = self.base / "external"
        external.mkdir()
        source = external / "vendor.brd"
        source.write_bytes(self.source.read_bytes())
        async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                          mode="legacy") as client:
            self.assertTrue((await client.call_tool("convert_pcb", request | {"source": str(source)})).is_error)
        async with Client(create_server(self.root, allow_checks=True, allow_exports=True,
                                        import_roots=(external,)), mode="legacy") as client:
            report = await self.call(client, source, "external-board")
            self.assertEqual(report.status, "PASS", report.error)
            tool = next(item for item in (await client.list_tools()).tools if item.name == "convert_pcb")
            self.assertNotIn("cli", tool.input_schema["properties"])
            self.assertNotIn("output", tool.input_schema["properties"])
            # The SDK ignores undeclared top-level arguments. They cannot replace
            # the fixed executable or route writes to caller-supplied output paths.
            for extra in ({"cli": "/untrusted/program"}, {"output": str(external / "output")}):
                result = await client.call_tool("convert_pcb", request | {"runner": "local"} | extra)
                self.assertFalse(result.is_error, result.content)
                bounded = ForeignPcbReport.model_validate_json(json.dumps(result.structured_content))
                self.assertEqual(bounded.commands["convert"].argv[0], str(self.executable.resolve()))
                self.assertTrue(Path(bounded.run_directory).is_relative_to(self.root / "build/diagnostics"))
                self.assertFalse((external / "output").exists())
        self.assertEqual(source.read_bytes(), self.source.read_bytes())

    async def test_conversion_path_links_and_special_files_fail_before_native_calls(self) -> None:
        outside = self.base / "private.brd"
        outside.write_text("Private source outside authorized roots")
        link = self.root / "build/imports/link.brd"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(str(exc))
        linked_directory = self.root / "build/linked-imports"
        linked_directory.symlink_to(self.source.parent, target_is_directory=True)
        candidates = [str(link), str(linked_directory / self.source.name), "../private.brd",
                      str(outside), str(self.source.parent)]
        if hasattr(os, "mkfifo"):
            fifo = self.source.parent / "pipe.brd"
            os.mkfifo(fifo)
            candidates.append(str(fifo))
        with patch("kicad_tooling.hwrepo.mcp_conversion.foreign_pcb.convert_pcb") as execute:
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                for source in candidates:
                    with self.subTest(source=source):
                        result = await client.call_tool("convert_pcb", {
                            "source": source, "project_id": "unsafe", "toolchain_id": "kicad-10.0.5",
                        })
                        self.assertTrue(result.is_error)
                execute.assert_not_called()
        self.assertFalse((self.root / "build/diagnostics").exists())
        receipt_root = self.base / "outside-receipts"
        receipt_root.mkdir()
        (self.root / "build/diagnostics").symlink_to(receipt_root, target_is_directory=True)
        with patch("kicad_tooling.hwrepo.mcp_conversion.foreign_pcb.convert_pcb") as execute:
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                result = await client.call_tool("convert_pcb", {
                    "source": str(self.source), "project_id": "linked-receipt", "toolchain_id": "kicad-10.0.5",
                })
                self.assertTrue(result.is_error)
                execute.assert_not_called()
        self.assertEqual(list(receipt_root.iterdir()), [])
