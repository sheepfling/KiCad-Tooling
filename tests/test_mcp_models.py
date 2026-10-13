"""MCP 3D model inspection, export, and population workflows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DEFAULT_THREE_D_VIEWS
from tests import test_visualize
from tests.mcp_test_support import McpTestCase, snapshot

pytestmark = [pytest.mark.slow, pytest.mark.template_checkout]


class McpTests(McpTestCase):
    async def test_3d_inventory_is_read_only_and_preserves_model_review(self) -> None:
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(
                await client.call_tool(
                    "inspect_3d_models",
                    {
                        "project_id": "arduino-uno-status-led",
                    },
                )
            )
            self.assertEqual(data["status"], "REVIEW")
            self.assertFalse(data["build_authorized"])
            self.assertTrue(data["footprints"])
            for project in ("../outside", "passive-signal-reference", "missing-project"):
                rejected = await client.call_tool("inspect_3d_models", {"project_id": project})
                self.assertTrue(rejected.is_error, rejected.content)
        self.assertEqual(snapshot(self.root), before)

    async def test_3d_export_handoff_keeps_review_and_rejects_unsafe_or_used_output(self) -> None:
        payloads = {f"{name}.png": test_visualize.PNG for name in DEFAULT_THREE_D_VIEWS}
        payloads.update({"board.step": test_visualize.STEP, "board.glb": test_visualize.GLB})

        def native(_root, output, _config, selected, cli, args, timeout=300):
            self.assertEqual(selected, "local")
            self.assertEqual(cli, "kicad-cli")
            if args == ("version",):
                return test_visualize.evidence(args, stdout="10.0.5\n")
            filename = Path(args[args.index("-o") + 1]).name
            (output / filename).write_bytes(payloads[filename])
            return test_visualize.evidence(args)

        options = {
            "project_id": "arduino-uno-status-led",
            "view_id": "review-one",
            "runner": "local",
        }
        async with Client(
            create_server(
                self.root,
                allow_checks=True,
                allow_exports=True,
            ),
            mode="legacy",
        ) as client:
            tool = next(
                item for item in (await client.list_tools()).tools if item.name == "export_3d"
            )
            self.assertFalse(tool.annotations.read_only_hint)
            self.assertEqual(
                set(tool.input_schema["properties"]),
                {"project_id", "view_id", "runner", "assembly_variant", "views"},
            )
            view_schema = tool.input_schema["properties"]["views"]
            array_schema = next(
                item for item in view_schema["anyOf"] if item.get("type") == "array"
            )
            self.assertEqual(set(array_schema["items"]["enum"]), set(DEFAULT_THREE_D_VIEWS))
            with (
                patch(
                    "kicad_tooling.hwrepo.three_d.doctor",
                    return_value=test_visualize.passing_doctor(),
                ),
                patch("kicad_tooling.hwrepo.three_d._run_kicad", side_effect=native),
            ):
                report = self.structured(await client.call_tool("export_3d", options))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["models"]["status"], "REVIEW")
            self.assertFalse(report["build_authorized"])
            self.assertEqual(report["run_directory"], str(self.root / "build/3d/review-one"))
            self.assertEqual(set(report["artifacts_sha256"]), set(payloads))
            saved = self.structured(
                await client.call_tool(
                    "read_artifact",
                    {
                        "path": "build/3d/review-one/visualization.json",
                    },
                )
            )
            self.assertEqual(json.loads(saved["text"])["models"]["status"], "REVIEW")
            with patch("kicad_tooling.hwrepo.three_d.generate") as generate:
                for update in (
                    {},
                    {"view_id": "../escape"},
                    {"view_id": "/tmp/escape"},
                    {"view_id": "duplicate-views", "views": ["top", "top"]},
                    {"view_id": "invalid-runner", "runner": "arbitrary-command"},
                ):
                    rejected = await client.call_tool("export_3d", options | update)
                    self.assertTrue(rejected.is_error, rejected.content)
                generate.assert_not_called()

    def population_arguments(self):
        project_id = "arduino-uno-status-led"
        island = self.root / f"examples/projects/{project_id}"
        board = island / f"kicad/{project_id}.kicad_pcb"
        model = island / "kicad/models/Header_1x02.step"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_bytes(test_visualize.STEP)
        return {
            "project_id": project_id,
            "board_sha256": hashlib.sha256(board.read_bytes()).hexdigest(),
            "assignments": [{"reference": "J1", "model": model.relative_to(self.root).as_posix()}],
        }

    async def test_model_population_preview_and_reviewed_apply_preserve_source_scope(self) -> None:
        arguments = self.population_arguments()
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            plan = self.structured(await client.call_tool("preview_model_population", arguments))
            self.assertEqual(plan["status"], "PLAN", plan["error"])
            self.assertFalse(plan["build_authorized"])
            self.assertTrue(plan["checks_required"])
            self.assertIn("${KIPRJMOD}/models/Header_1x02.step", plan["board_diff"])
            self.assertIn("kicad/models/Header_1x02.step", plan["manifest_diff"])
            self.assertEqual(
                {
                    key: value
                    for key, value in snapshot(self.root).items()
                    if Path(key).parts[0] != "build"
                },
                before,
            )
            receipt = Path(plan["run_directory"]).relative_to(self.root)
            saved = self.structured(
                await client.call_tool(
                    "read_artifact",
                    {
                        "path": (receipt / "locked-model-map.json").as_posix(),
                    },
                )
            )
            saved_map = json.loads(saved["text"])
            self.assertEqual(saved_map["manifest_sha256"], plan["manifest_sha256"])
            self.assertEqual(saved_map["assignments"][0]["reference"], "J1")
            self.assertEqual(
                saved_map["assignments"][0]["model"], arguments["assignments"][0]["model"]
            )
            apply_arguments = {
                "project_id": arguments["project_id"],
                "plan": (receipt / "model-population.json").as_posix(),
            }
            self.assertTrue(
                (await client.call_tool("apply_model_population", apply_arguments)).is_error
            )
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            applied = self.structured(
                await client.call_tool("apply_model_population", apply_arguments)
            )
            self.assertEqual(applied["status"], "APPLIED", applied["error"])
            self.assertFalse(applied["build_authorized"])
            self.assertTrue(applied["checks_required"])
            self.assertEqual(applied["board_diff"], plan["board_diff"])
            self.assertNotEqual(applied["run_directory"], plan["run_directory"])
            board = self.structured(
                await client.call_tool(
                    "read_project_file",
                    {
                        "project_id": arguments["project_id"],
                        "path": f"kicad/{arguments['project_id']}.kicad_pcb",
                    },
                )
            )
            self.assertIn("${KIPRJMOD}/models/Header_1x02.step", board["text"])
            repeated = self.structured(
                await client.call_tool("apply_model_population", apply_arguments)
            )
            self.assertEqual(repeated["status"], "FAIL")
        after = {
            key: value
            for key, value in snapshot(self.root).items()
            if Path(key).parts[0] != "build"
        }
        changed = {key for key in before | after if before.get(key) != after.get(key)}
        self.assertEqual(changed, {plan["board"], plan["manifest"]})

    async def test_model_population_apply_rejects_stale_source_assets_and_map(self) -> None:
        arguments = self.population_arguments()
        board = (
            self.root
            / f"examples/projects/{arguments['project_id']}/kicad/{arguments['project_id']}.kicad_pcb"
        )
        manifest = board.parent.parent / "project.json"
        model = self.root / arguments["assignments"][0]["model"]
        originals = {path: path.read_bytes() for path in (board, manifest, model)}
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            for changed in ("board", "manifest", "model", "map"):
                with self.subTest(changed=changed):
                    for path, contents in originals.items():
                        path.write_bytes(contents)
                    plan = self.structured(
                        await client.call_tool("preview_model_population", arguments)
                    )
                    self.assertEqual(plan["status"], "PLAN", plan["error"])
                    receipt = Path(plan["run_directory"])
                    path = {
                        "board": board,
                        "manifest": manifest,
                        "model": model,
                        "map": receipt / "locked-model-map.json",
                    }[changed]
                    if changed == "map":
                        data = json.loads(path.read_text())
                        data["assignments"][0]["reference"] = "J2"
                        path.write_text(json.dumps(data))
                    else:
                        path.write_bytes(path.read_bytes() + b"\n")
                    before = (board.read_bytes(), manifest.read_bytes())
                    rejected = self.structured(
                        await client.call_tool(
                            "apply_model_population",
                            {
                                "project_id": arguments["project_id"],
                                "plan": (receipt / "model-population.json")
                                .relative_to(self.root)
                                .as_posix(),
                            },
                        )
                    )
                    self.assertEqual(rejected["status"], "FAIL", rejected["error"])
                    self.assertEqual((board.read_bytes(), manifest.read_bytes()), before)

    async def test_model_population_rejects_unsafe_plan_and_map_before_source_edit(self) -> None:
        arguments = self.population_arguments()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            plan = self.structured(await client.call_tool("preview_model_population", arguments))
            receipt = Path(plan["run_directory"])
            name = (receipt / "model-population.json").relative_to(self.root).as_posix()
            before = snapshot(self.root)
            for path in (
                "../outside.json",
                str(receipt / "model-population.json"),
                "examples/projects/controller/project.json",
            ):
                with self.subTest(path=path):
                    result = await client.call_tool(
                        "apply_model_population",
                        {
                            "project_id": arguments["project_id"],
                            "plan": path,
                        },
                    )
                    self.assertTrue(result.is_error, result.content)
            mismatch = await client.call_tool(
                "apply_model_population",
                {
                    "project_id": "controller",
                    "plan": name,
                },
            )
            self.assertTrue(mismatch.is_error, mismatch.content)
            self.assertEqual(snapshot(self.root), before)
            spec = receipt / "locked-model-map.json"
            outside = self.base / "model-map.json"
            spec.replace(outside)
            spec.symlink_to(outside)
            with patch(
                "kicad_tooling.hwrepo.mcp_workflow.model_population.populate_models"
            ) as populate:
                result = await client.call_tool(
                    "apply_model_population",
                    {
                        "project_id": arguments["project_id"],
                        "plan": name,
                    },
                )
                self.assertTrue(result.is_error, result.content)
                populate.assert_not_called()
