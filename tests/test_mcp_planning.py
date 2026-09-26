"""CLI/MCP behavior parity for impact, model-map drafts and sourcing snapshots."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from mcp.types import CallToolResult, TextContent

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ModelMap, SourcingSnapshot, SupplierOffer
from tests.support import SOURCE_ROOT, initialize_git, reference_root


class McpPlanningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-planning-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )

    async def cli(self, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
            subprocess.run,
            (sys.executable, "-B", "-m", module, "--root", str(self.root), *arguments),
            cwd=SOURCE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def text(result: CallToolResult) -> str:
        return "\n".join(item.text for item in result.content if isinstance(item, TextContent))

    def structured(self, result: CallToolResult):
        self.assertFalse(result.is_error, self.text(result))
        self.assertIsNotNone(result.structured_content)
        return result.structured_content

    def source_snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.root).as_posix(): digest(path)
            for path in self.root.rglob("*")
            if path.is_file() and path.relative_to(self.root).parts[0] not in {"build", ".git"}
        }

    def sourcing_snapshot(self) -> SourcingSnapshot:
        return SourcingSnapshot(
            snapshot_id="training-offer-observation",
            source_commit="a" * 40,
            observed_at=datetime(2026, 9, 7, tzinfo=UTC),
            offers=(
                SupplierOffer(
                    id="offer-1",
                    part_id="training-generic-led-red-5mm",
                    supplier="Example supplier observation",
                    supplier_sku="EXAMPLE-LED-5MM",
                    source_url="https://example.invalid/offer",
                    region="test-only",
                    currency="USD",
                    quantity_break=1,
                    unit_price_minor=0,
                    availability="not a purchasing instruction",
                ),
            ),
        )

    async def test_impact_cli_and_mcp_match_paths_full_and_manual_modes(self) -> None:
        cases = (
            (("--path", "README.md"), {"paths": ["README.md"]}),
            (
                ("--path", "examples/projects/controller/kicad/controller.kicad_pcb"),
                {"paths": ["examples/projects/controller/kicad/controller.kicad_pcb"]},
            ),
            (
                ("--path", "unowned.txt", "--path", "README.md"),
                {"paths": ["unowned.txt", "README.md"]},
            ),
            (("--path", "../unsafe"), {"paths": ["../unsafe"]}),
            (("--full",), {"full": True}),
            (("--select-project", "controller"), {"select_project": "controller"}),
            (("--select-tag", "training"), {"select_tag": "training"}),
            (
                ("--select-product", "status-indicator-system"),
                {"select_product": "status-indicator-system"},
            ),
            (
                ("--select-tag", "training", "--exclude-tag", "legacy"),
                {"select_tag": "training", "exclude_tag": "legacy"},
            ),
            (
                ("--select-tag", "training", "--shard", "1/2"),
                {"select_tag": "training", "shard": "1/2"},
            ),
        )
        before = self.source_snapshot()
        async with Client(create_server(self.root), mode="legacy") as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertTrue(tools["plan_impact"].annotations.read_only_hint)
            for arguments, request in cases:
                with self.subTest(arguments=arguments):
                    command = await self.cli("kicad_tooling.impact", *arguments)
                    self.assertEqual(command.returncode, 0, command.stderr)
                    actual = self.structured(await client.call_tool("plan_impact", request))
                    self.assertEqual(actual, json.loads(command.stdout))
        self.assertFalse((self.root / "build").exists())
        self.assertEqual(self.source_snapshot(), before)

    async def test_impact_cli_and_mcp_match_git_refs_and_block_option_injection(self) -> None:
        await asyncio.to_thread(initialize_git, self.root)

        def git(*args: str) -> str:
            return subprocess.run(
                ("git", "-C", str(self.root), *args), capture_output=True, text=True, check=True
            ).stdout.strip()

        await asyncio.to_thread(
            git,
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Initial synthetic source",
        )
        base = await asyncio.to_thread(git, "rev-parse", "HEAD")
        source = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        source.write_bytes(source.read_bytes() + b"\n")
        await asyncio.to_thread(
            git,
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qam",
            "Changed selected synthetic board",
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            for reference in (base, "HEAD~1"):
                command = await self.cli(
                    "kicad_tooling.impact", "--base", reference, "--head", "HEAD"
                )
                self.assertEqual(command.returncode, 0, command.stderr)
                actual = self.structured(await client.call_tool("plan_impact", {"base": reference}))
                self.assertEqual(actual, json.loads(command.stdout))
                self.assertEqual(actual["projects"], ["controller"])
            destination = self.base / "should-not-exist"
            for reference in (f"--output={destination}", "--no-index", "missing-branch"):
                command = await self.cli("kicad_tooling.impact", f"--base={reference}")
                self.assertEqual(command.returncode, 2)
                result = await client.call_tool("plan_impact", {"base": reference})
                self.assertTrue(result.is_error)
            result = await client.call_tool(
                "plan_impact", {"base": base, "head": f"--output={destination}"}
            )
            self.assertTrue(result.is_error)
            self.assertFalse(destination.exists())
        self.assertFalse((self.root / "build").exists())

    async def test_impact_invalid_modes_and_selectors_fail_in_both_interfaces(self) -> None:
        cases = (
            ((), {}),
            (
                ("--full", "--select-project", "controller"),
                {"full": True, "select_project": "controller"},
            ),
            (("--select-project", "unknown"), {"select_project": "unknown"}),
            (("--select-tag", "missing-tag"), {"select_tag": "missing-tag"}),
            (("--full", "--exclude-tag", "training"), {"full": True, "exclude_tag": "training"}),
            (("--select-project", ""), {"select_project": ""}),
            (
                ("--select-project", "controller", "--shard", "2/2"),
                {"select_project": "controller", "shard": "2/2"},
            ),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            for arguments, request in cases:
                with self.subTest(request=request):
                    command = await self.cli("kicad_tooling.impact", *arguments)
                    self.assertEqual(command.returncode, 2)
                    self.assertTrue((await client.call_tool("plan_impact", request)).is_error)
        self.assertFalse((self.root / "build").exists())

    async def test_model_map_cli_and_mcp_match_draft_content_and_authority(self) -> None:
        project = "arduino-uno-status-led"
        before = self.source_snapshot()
        command = await self.cli(
            "kicad_tooling.visualize",
            "--project",
            project,
            "--init-model-map",
            "build/cli-map/model-map.json",
            "--output",
            "build/cli-map",
            "--format",
            "json",
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        expected = json.loads(command.stdout)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            actual = self.structured(
                await client.call_tool(
                    "init_model_map",
                    {
                        "project_id": project,
                        "view_id": "draft-one",
                    },
                )
            )
            excluded = {"draft_map", "run_directory", "next_commands"}
            self.assertEqual(
                {key: value for key, value in actual.items() if key not in excluded},
                {key: value for key, value in expected.items() if key not in excluded},
            )
            self.assertEqual(actual["status"], "DRAFT")
            self.assertFalse(actual["build_authorized"])
            self.assertTrue(actual["checks_required"])
            self.assertEqual(
                read_model(Path(actual["draft_map"]), ModelMap),
                read_model(Path(expected["draft_map"]), ModelMap),
            )
            draft = self.structured(
                await client.call_tool(
                    "read_artifact",
                    {
                        "path": "build/model-maps/draft-one/model-map.json",
                    },
                )
            )
            self.assertTrue(
                all(item["model"] == "" for item in json.loads(draft["text"])["assignments"])
            )
        self.assertEqual(self.source_snapshot(), before)

    async def test_model_map_failure_receipts_match_cli_and_gates_refuse_overwrite(self) -> None:
        project = "arduino-uno-status-led"
        board = self.root / f"examples/projects/{project}/kicad/{project}.kicad_pcb"
        board.write_text("(kicad_pcb)\n")
        command = await self.cli(
            "kicad_tooling.visualize",
            "--project",
            project,
            "--init-model-map",
            "build/cli-empty/model-map.json",
            "--output",
            "build/cli-empty",
            "--format",
            "json",
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        expected = json.loads(command.stdout)
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (
                    await client.call_tool(
                        "init_model_map",
                        {
                            "project_id": project,
                            "view_id": "disabled",
                        },
                    )
                ).is_error
            )
        self.assertFalse((self.root / "build/model-maps/disabled").exists())
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            actual = self.structured(
                await client.call_tool(
                    "init_model_map",
                    {
                        "project_id": project,
                        "view_id": "empty",
                    },
                )
            )
            self.assertEqual(actual["status"], expected["status"])
            self.assertEqual(actual["error"], expected["error"])
            self.assertTrue(Path(actual["run_directory"], "model-population.json").is_file())
            for view in ("empty", "../escape", "/tmp/escape"):
                self.assertTrue(
                    (
                        await client.call_tool(
                            "init_model_map",
                            {
                                "project_id": project,
                                "view_id": view,
                            },
                        )
                    ).is_error
                )
        self.assertFalse((self.root / "build/escape").exists())

    async def test_sourcing_cli_and_mcp_match_artifact_and_semantic_failures(self) -> None:
        snapshot = self.sourcing_snapshot()
        path = self.root / "build/sourcing/snapshot.json"
        path.parent.mkdir(parents=True)
        cases = (
            snapshot,
            snapshot.model_copy(update={"offers": snapshot.offers * 2}),
            snapshot.model_copy(
                update={
                    "offers": (snapshot.offers[0].model_copy(update={"part_id": "unknown-part"}),)
                }
            ),
        )
        before = self.source_snapshot()
        async with Client(create_server(self.root), mode="legacy") as client:
            for current in cases:
                with self.subTest(offers=current.offers):
                    write_model(path, current)
                    command = await self.cli(
                        "kicad_tooling.sourcing", "--snapshot", "build/sourcing/snapshot.json"
                    )
                    expected = json.loads(command.stdout)
                    self.assertEqual(command.returncode, 0 if expected["status"] == "PASS" else 1)
                    actual = self.structured(
                        await client.call_tool(
                            "inspect_sourcing_snapshot",
                            {
                                "path": "build/sourcing/snapshot.json",
                            },
                        )
                    )
                    self.assertEqual(actual, expected)
                    self.assertFalse(actual["build_authorized"])
        self.assertEqual(self.source_snapshot(), before)

    async def test_sourcing_load_failures_match_cli_and_paths_are_bounded(self) -> None:
        path = self.root / "build/broken.json"
        path.parent.mkdir()
        path.write_text('{"snapshot_id": "incomplete"}')
        async with Client(create_server(self.root), mode="legacy") as client:
            for name in ("build/broken.json", "build/missing.json"):
                command = await self.cli("kicad_tooling.sourcing", "--snapshot", name)
                self.assertEqual(command.returncode, 1)
                actual = self.structured(
                    await client.call_tool("inspect_sourcing_snapshot", {"path": name})
                )
                self.assertEqual(actual, json.loads(command.stdout))
                self.assertEqual(actual["issues"][0]["code"], "SOURCING_LOAD")
            external = self.base / "outside.json"
            write_model(external, self.sourcing_snapshot())
            (self.root / "build/linked.json").symlink_to(external)
            for request in (
                {},
                {"path": "../outside.json"},
                {"path": str(path)},
                {"path": "catalog/parts.json"},
                {"path": "build/linked.json"},
                {"snapshot": self.sourcing_snapshot().model_dump(mode="json")},
            ):
                self.assertTrue(
                    (await client.call_tool("inspect_sourcing_snapshot", request)).is_error
                )
        self.assertEqual(
            {entry.name for entry in (self.root / "build").iterdir()},
            {"broken.json", "linked.json"},
        )

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Requires POSIX special files")
    async def test_sourcing_special_file_is_rejected_before_reader_can_block(self) -> None:
        path = self.root / "build/fifo.json"
        path.parent.mkdir()
        os.mkfifo(path)
        async with Client(create_server(self.root), mode="legacy") as client:
            with patch("kicad_tooling.hwrepo.mcp_planning.read_model") as reader:
                report = self.structured(
                    await client.call_tool(
                        "inspect_sourcing_snapshot",
                        {
                            "path": "build/fifo.json",
                        },
                    )
                )
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["issues"][0]["code"], "SOURCING_LOAD")
                self.assertIn("regular", report["issues"][0]["message"])
                reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
