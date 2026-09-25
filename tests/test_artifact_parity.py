"""Actual CLI/MCP artifact parity with explicitly synthetic native payloads.

The external fake KiCad executable exercises command adapters and file handling;
its tiny payloads establish no physical, geometry or manufacturing validity.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from pydantic import BaseModel

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PartsCatalog,
    ReleaseExportReport,
    ReleasePackageReport,
    ReleaseReadinessReport,
    ThreeDReport,
)
from tests import test_release_evidence, test_visualize
from tests.support import SOURCE_ROOT
from tests.test_contract_coach import fake_executable


class ArtifactParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        fixture = test_release_evidence.ReleaseEvidenceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.base = fixture.parent

    async def cli_process(self, module, *arguments):
        return await asyncio.to_thread(
            subprocess.run,
            (sys.executable, "-B", "-m", module, "--root", str(self.root),
             *arguments, "--format", "json"),
            cwd=self.base, env={**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
            text=True, capture_output=True, check=False, timeout=60,
        )

    async def cli(self, module, model, *arguments, expected_exit=0):
        result = await self.cli_process(module, *arguments)
        self.assertEqual(result.returncode, expected_exit, result.stderr + result.stdout)
        return parse_model_text(result.stdout, model)

    async def call(self, client, name, model, arguments):
        result = await client.call_tool(name, arguments)
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return model.model_validate_json(json.dumps(result.structured_content))

    @staticmethod
    def semantic(report: BaseModel, output: Path):
        """Normalize only one known output directory and command start timestamps."""
        def normalize(value, field=None):
            if isinstance(value, dict):
                return {key: normalize(item, key) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, str):
                return "<command-start>" if field == "started_utc" else value.replace(str(output), "<output>")
            return value
        return normalize(report.model_dump(mode="json"))

    @staticmethod
    def archive_members(archive: Path):
        with zipfile.ZipFile(archive) as opened:
            return {name: opened.read(name) for name in opened.namelist()}

    @staticmethod
    def archive_metadata(archive: Path):
        # Date/time is the sole permitted ZIP metadata difference. The archive
        # comment and every content/encoding/permission field stay comparable.
        with zipfile.ZipFile(archive) as opened:
            return opened.comment, {
                item.filename: (
                    item.compress_type, item.compress_size, item.file_size, item.CRC,
                    item.create_system, item.create_version, item.extract_version,
                    item.flag_bits, item.internal_attr, item.external_attr, item.extra, item.comment,
                ) for item in opened.infolist()
            }

    def native_executable(self) -> Path:
        """Create a subprocess fixture outside the committed source checkout."""
        binary = self.base / "native-bin"
        binary.mkdir()
        part = read_model(self.root / "catalog/parts.json", PartsCatalog).parts[0].id
        script = f'''import os
import sys
from pathlib import Path
args = sys.argv[1:]
if args == ["version"]:
    print("10.0.5")
    raise SystemExit(0)
if "-o" in args:
    destination = Path(args[args.index("-o") + 1])
    payloads = {{".png": {test_visualize.PNG!r}, ".step": {test_visualize.STEP!r},
                ".glb": {test_visualize.GLB!r}}}
    payload = payloads[destination.suffix]
    if os.environ.get("PARITY_INVALID_IMAGE") == "1" and destination.name == "top.png":
        payload = b"synthetic-invalid-image"
    destination.write_bytes(payload)
    raise SystemExit(0)
output = Path(args[args.index("--output") + 1])
kind = args[2]
if kind == "gerbers" and os.environ.get("PARITY_MUTATE_SOURCE") == "1":
    board = Path(args[-1])
    board.write_bytes(board.read_bytes() + b"\\n")
if kind == "gerbers" and os.environ.get("PARITY_FAILED_EXPORT") == "1":
    print("Synthetic Gerber command failure", file=sys.stderr)
    raise SystemExit(17)
if kind == "gerbers":
    (output / "board.gbr").write_text("Synthetic parity Gerber\\n")
elif kind == "drill":
    (output / "board.drl").write_text("Synthetic parity drill\\n")
elif kind == "pos":
    output.write_text("Ref,PosX,PosY\\nR1,0,0\\n")
elif kind == "pdf":
    output.write_bytes(b"%PDF-1.5\\nSynthetic parity review packet\\n")
elif kind == "stats":
    output.write_text("{{}}\\n")
elif kind in {{"odb", "ipc2581"}}:
    import zipfile
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(zipfile.ZipInfo("synthetic.txt"), "Synthetic supplier output")
elif kind == "ipcd356":
    output.write_text("Synthetic IPC-D-356\\n")
elif kind == "bom":
    output.write_text("Reference,Value,Footprint,PartID,DNP\\n"
                      "R1,1k,Resistor_SMD:R_0805_2012Metric,{part},\\n")
else:
    raise SystemExit("Unexpected synthetic KiCad command: " + repr(args))
'''
        return fake_executable(binary / "kicad-cli", script)

    async def test_release_readiness_and_archive_lifecycle_parity(self) -> None:
        fixture = self.fixture
        cli_ready = await self.cli("kicad_tooling.release", ReleaseReadinessReport, "check",
                                   "--manifest", fixture.manifest_name)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp_ready = await self.call(client, "check_release", ReleaseReadinessReport,
                                        {"manifest": fixture.manifest_name})
            self.assertEqual(cli_ready, mcp_ready)
            self.assertEqual(mcp_ready.status, "PASS")
            self.assertFalse(mcp_ready.build_authorized)
            cli_archive = self.root / "build/packages/cli-review.zip"
            mcp_archive = self.root / "build/packages/mcp-review.zip"
            cli_package = await self.cli("kicad_tooling.release", ReleasePackageReport, "package",
                                         "--manifest", fixture.manifest_name, "--output", str(cli_archive))
            mcp_package = await self.call(client, "package_release", ReleasePackageReport, {
                "manifest": fixture.manifest_name, "package_id": "mcp-review",
            })
            self.assertEqual(cli_package.package_sha256, digest(cli_archive))
            self.assertEqual(mcp_package.package_sha256, digest(mcp_archive))
            # ZIP container timestamps can differ. Every decompressed member,
            # including Git bundle, source binding and payload digests, must match.
            self.assertEqual(self.archive_members(cli_archive), self.archive_members(mcp_archive))
            self.assertEqual(self.archive_metadata(cli_archive), self.archive_metadata(mcp_archive))
            self.assertEqual(cli_package.model_copy(update={"package": "<archive>",
                                                            "package_sha256": "<zip-container>"}),
                             mcp_package.model_copy(update={"package": "<archive>",
                                                            "package_sha256": "<zip-container>"}))
            for archive in (cli_archive, mcp_archive):
                with self.subTest(archive=archive.name):
                    cli_verified = await self.cli("kicad_tooling.release", ReleasePackageReport, "verify",
                                                  "--archive", str(archive))
                    mcp_verified = await self.call(client, "verify_package", ReleasePackageReport, {
                        "archive": archive.relative_to(self.root).as_posix(),
                    })
                    self.assertEqual(cli_verified, mcp_verified)
                    self.assertEqual(mcp_verified.status, "PASS")
                    self.assertFalse(mcp_verified.build_authorized)
            cli_destination = self.root / "build/restores/cli-review"
            cli_destination.parent.mkdir(parents=True)
            cli_restored = await self.cli("kicad_tooling.release", ReleasePackageReport, "restore",
                                          "--archive", str(mcp_archive), "--destination", str(cli_destination))
            mcp_restored = await self.call(client, "restore_package", ReleasePackageReport, {
                "archive": mcp_archive.relative_to(self.root).as_posix(), "restore_id": "mcp-review",
            })
            self.assertEqual(cli_restored, mcp_restored)
            mcp_destination = self.root / "build/restores/mcp-review"
            self.assertEqual(source_state(cli_destination), fixture.source)
            self.assertEqual(source_state(mcp_destination), fixture.source)
            for name, content in self.archive_members(mcp_archive).items():
                if name.startswith("payload/"):
                    relative = name.removeprefix("payload/")
                    self.assertEqual((cli_destination / relative).read_bytes(), content)
                    self.assertEqual((mcp_destination / relative).read_bytes(), content)

            changed = self.root / fixture.config.required_inputs[0]
            changed.write_bytes(changed.read_bytes() + b"\n")
            cli_stale = await self.cli("kicad_tooling.release", ReleaseReadinessReport, "check",
                                       "--manifest", fixture.manifest_name, expected_exit=1)
            mcp_stale = await self.call(client, "check_release", ReleaseReadinessReport,
                                        {"manifest": fixture.manifest_name})
            self.assertEqual(cli_stale, mcp_stale)
            self.assertEqual(mcp_stale.status, "FAIL")
            self.assertTrue(mcp_stale.issues)
            cli_denied = await self.cli_process("kicad_tooling.release", "package", "--manifest",
                                                fixture.manifest_name, "--output",
                                                str(self.root / "build/packages/cli-stale.zip"))
            mcp_denied = await client.call_tool("package_release", {
                "manifest": fixture.manifest_name, "package_id": "mcp-stale",
            })
            self.assertEqual(cli_denied.returncode, 2)
            self.assertTrue(mcp_denied.is_error)
            self.assertIn("Release is not ready", cli_denied.stderr)
            self.assertIn("Release is not ready", str(mcp_denied.content))
            self.assertFalse((self.root / "build/packages/cli-stale.zip").exists())
            self.assertFalse((self.root / "build/packages/mcp-stale.zip").exists())

    async def test_3d_export_parity(self) -> None:
        executable = self.native_executable()
        before = source_state(self.root)
        with patch.dict(os.environ, {"PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}):
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                for invalid in (False, True):
                    with self.subTest(invalid_image=invalid), patch.dict(
                        os.environ, {"PARITY_INVALID_IMAGE": "1" if invalid else "0"},
                    ):
                        cli_directory = self.root / ("build/3d/cli-invalid" if invalid else "build/3d/cli-good")
                        cli = await self.cli("kicad_tooling.visualize", ThreeDReport, "--project",
                                             test_visualize.PROJECT, "--runner", "local", "--output",
                                             str(cli_directory), expected_exit=int(invalid))
                        mcp = await self.call(client, "export_3d", ThreeDReport, {
                            "project_id": test_visualize.PROJECT, "runner": "local",
                            "view_id": "mcp-invalid" if invalid else "mcp-good",
                        })
                        mcp_directory = Path(mcp.run_directory)
                        self.assertEqual(self.semantic(cli, cli_directory), self.semantic(mcp, mcp_directory))
                        self.assertEqual(mcp.status, "FAIL" if invalid else "PASS")
                        self.assertEqual(mcp.runner, "local")
                        self.assertEqual(mcp.models.status, "REVIEW")
                        self.assertFalse(mcp.build_authorized)
                        self.assertEqual(cli.artifacts_sha256, mcp.artifacts_sha256)
                        for name, expected in mcp.artifacts_sha256.items():
                            self.assertEqual(digest(cli_directory / name), expected)
                            self.assertEqual(digest(mcp_directory / name), expected)
                            self.assertEqual((cli_directory / name).read_bytes(),
                                             (mcp_directory / name).read_bytes())
                        if invalid:
                            self.assertFalse(mcp.artifacts_sha256)
                            self.assertEqual(set(mcp.commands), {"version", "top"})
                        else:
                            self.assertEqual(set(mcp.artifacts_sha256),
                                             {"top.png", "angled.png", "board.step", "board.glb"})
                        self.assertEqual(source_state(self.root), before)

    def configure_variants(self) -> None:
        project = self.root / test_visualize.BOARD.replace(".kicad_pcb", ".kicad_pro")
        data = json.loads(project.read_text())
        data.setdefault("schematic", {})["variants"] = [{"name": "Pilot A"}, {"name": "Pilot B"}]
        project.write_text(json.dumps(data), encoding="utf-8")
        manifest = project.parent.parent / "project.json"
        data = json.loads(manifest.read_text())
        data["release_exports"]["assembly_variant"] = "Pilot A"
        data["release_exports"]["supplier_formats"] = ["odb", "ipc2581", "ipcd356"]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.fixture.git("-c", "user.name=Test fixture", "-c", "user.email=fixture@example.invalid",
                         "commit", "-qam", "Synthetic variant configuration")

    async def test_assembly_variant_export_and_3d_parity(self) -> None:
        self.configure_variants()
        executable = self.native_executable()
        before = source_state(self.root)
        with patch.dict(os.environ, {"PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}):
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                for suffix, variant in (("default", None), ("explicit", "Pilot B")):
                    with self.subTest(variant=variant):
                        selected = variant or "Pilot A"
                        args = () if variant is None else ("--assembly-variant", variant)
                        cli_directory = self.root / f"build/exports/cli-{suffix}"
                        cli = await self.cli("kicad_tooling.release", ReleaseExportReport, "export", "--project",
                                             test_visualize.PROJECT, "--cli", str(executable), "--output",
                                             str(cli_directory), *args)
                        mcp = await self.call(client, "export_project", ReleaseExportReport, {
                            "project_id": test_visualize.PROJECT, "export_id": f"mcp-{suffix}",
                            "runner": "local", "assembly_variant": variant,
                        })
                        mcp_directory = self.root / f"build/exports/mcp-{suffix}/files"
                        self.assertEqual(self.export_semantic(cli, cli_directory),
                                         self.export_semantic(mcp, mcp_directory))
                        self.assertEqual(mcp.assembly_variant, selected)
                        self.assertEqual(mcp.status, "PASS")
                        for name in ("gerbers", "position", "bom", "schematic_pdf", "pcb_pdf", "odb", "ipc2581"):
                            argv = mcp.commands[name].argv
                            self.assertEqual(argv[argv.index("--variant") + 1], selected)
                        for name in ("drill", "board_stats", "ipcd356"):
                            self.assertNotIn("--variant", mcp.commands[name].argv)
                        self.assertEqual(source_state(self.root), before)
                cli_directory = self.root / "build/3d/cli-variant"
                cli_3d = await self.cli("kicad_tooling.visualize", ThreeDReport, "--project", test_visualize.PROJECT,
                                         "--runner", "local", "--output", str(cli_directory),
                                         "--assembly-variant", "Pilot B")
                mcp_3d = await self.call(client, "export_3d", ThreeDReport, {
                    "project_id": test_visualize.PROJECT, "view_id": "mcp-variant",
                    "runner": "local", "assembly_variant": "Pilot B",
                })
                self.assertEqual(self.semantic(cli_3d, cli_directory),
                                 self.semantic(mcp_3d, Path(mcp_3d.run_directory)))
                self.assertEqual(mcp_3d.assembly_variant, "Pilot B")
                self.assertEqual(mcp_3d.models.status, "REVIEW")
                for name in ("top", "angled", "step", "glb"):
                    argv = mcp_3d.commands[name].argv
                    self.assertEqual(argv[argv.index("--variant") + 1], "Pilot B")
                self.assertEqual(source_state(self.root), before)

    async def test_unknown_assembly_variant_is_rejected_before_native_export(self) -> None:
        self.configure_variants()
        async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                          mode="legacy") as client:
            for index, variant in enumerate(("Missing population", " ")):
                with self.subTest(variant=variant), patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli") as select:
                    result = await client.call_tool("export_project", {
                        "project_id": test_visualize.PROJECT, "export_id": f"invalid-{index}",
                        "runner": "local", "assembly_variant": variant,
                    })
                    self.assertTrue(result.is_error)
                    select.assert_not_called()
                    self.assertFalse((self.root / f"build/exports/invalid-{index}").exists())
                    command = await self.cli_process("kicad_tooling.release", "export", "--project",
                                                     test_visualize.PROJECT, "--cli", "kicad-cli", "--output",
                                                     str(self.root / f"build/exports/cli-invalid-{index}"),
                                                     "--assembly-variant", variant)
                    self.assertEqual(command.returncode, 2, command.stdout + command.stderr)
            cli_3d = await self.cli("kicad_tooling.visualize", ThreeDReport, "--project", test_visualize.PROJECT,
                                     "--assembly-variant", "Missing population", expected_exit=1)
            with patch("kicad_tooling.hwrepo.three_d._run_kicad") as execute:
                mcp_3d = await self.call(client, "export_3d", ThreeDReport, {
                    "project_id": test_visualize.PROJECT, "view_id": "unknown-3d",
                    "assembly_variant": "Missing population",
                })
                execute.assert_not_called()
            self.assertEqual(self.semantic(cli_3d, Path(cli_3d.run_directory)),
                             self.semantic(mcp_3d, Path(mcp_3d.run_directory)))
            self.assertEqual(mcp_3d.status, "FAIL")
            self.assertFalse(mcp_3d.artifacts_sha256)

    def export_semantic(self, report: ReleaseExportReport, directory: Path):
        artifact_hashes = {}
        for name, expected in report.artifacts_sha256.items():
            path = directory / name
            self.assertEqual(digest(path), expected)
            if name.endswith(".command.json"):
                # Retained log hashes include output paths/start times. Compare
                # canonical content while validating each real file hash above.
                command = read_model(path, CommandEvidence)
                content = json.dumps(self.semantic(command, directory), sort_keys=True).encode()
                artifact_hashes[name] = hashlib.sha256(content).hexdigest()
            else:
                artifact_hashes[name] = expected
        data = self.semantic(report, directory)
        data["artifacts_sha256"] = artifact_hashes
        return data

    async def test_native_fabrication_export_parity(self) -> None:
        executable = self.native_executable()
        before = source_state(self.root)
        board = self.root / test_visualize.BOARD
        original_board = board.read_bytes()
        with patch.dict(os.environ, {"PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}):
            async with Client(create_server(self.root, allow_checks=True, allow_exports=True),
                              mode="legacy") as client:
                for suffix, failing, mutating in (("good", False, False),
                                                   ("failed", True, False),
                                                   ("mutated", False, True)):
                    with self.subTest(scenario=suffix), patch.dict(
                        os.environ, {"PARITY_FAILED_EXPORT": "1" if failing else "0",
                                     "PARITY_MUTATE_SOURCE": "1" if mutating else "0"},
                    ):
                        cli_directory = self.root / f"build/exports/cli-{suffix}"
                        mcp_directory = self.root / f"build/exports/mcp-{suffix}/files"
                        cli = await self.cli("kicad_tooling.release", ReleaseExportReport, "export", "--project",
                                             test_visualize.PROJECT, "--cli", str(executable), "--output",
                                             str(cli_directory), expected_exit=int(failing or mutating))
                        if mutating:
                            self.assertNotEqual(board.read_bytes(), original_board)
                            board.write_bytes(original_board)
                        mcp = await self.call(client, "export_project", ReleaseExportReport, {
                            "project_id": test_visualize.PROJECT,
                            "export_id": f"mcp-{suffix}", "runner": "local",
                        })
                        self.assertEqual(mcp.status, "FAIL" if failing or mutating else "PASS")
                        self.assertEqual(cli.source, mcp.source)
                        self.assertEqual(mcp.source, before)
                        self.assertEqual(set(cli.artifacts_sha256), set(mcp.artifacts_sha256))
                        self.assertEqual(self.export_semantic(cli, cli_directory),
                                         self.export_semantic(mcp, mcp_directory))
                        for name in ("fabrication/board.drl", "assembly/positions.csv",
                                     "assembly/bom.csv", "assembly/purchasing-bom.csv"):
                            self.assertEqual((cli_directory / name).read_bytes(),
                                             (mcp_directory / name).read_bytes())
                        if failing:
                            self.assertEqual(mcp.commands["gerbers"].returncode, 17)
                            self.assertIn("Synthetic Gerber command failure", mcp.commands["gerbers"].stderr)
                            self.assertFalse((mcp_directory / "fabrication/board.gbr").exists())
                        else:
                            self.assertEqual((cli_directory / "fabrication/board.gbr").read_bytes(),
                                             (mcp_directory / "fabrication/board.gbr").read_bytes())
                        if mutating:
                            self.assertNotEqual(board.read_bytes(), original_board)
                            self.assertTrue(all(command.returncode == 0 for command in mcp.commands.values()))
                            board.write_bytes(original_board)
                        self.assertEqual(source_state(self.root), before)


if __name__ == "__main__":
    unittest.main()
