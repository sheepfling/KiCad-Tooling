"""Release CLI/MCP parity and archive replay using explicit synthetic applicability."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from kicad_tooling import release as cli
from kicad_tooling.hwrepo import mcp_workflow as workflow
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_setup import initialize
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    CheckEvidence,
    ElectricalAnalysisContract,
    ReleaseManifest,
    ValidationSummary,
)
from tests import test_mcp_workflow, test_release_evidence


class ReleaseElectricalTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = test_release_evidence.ReleaseEvidenceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        setup = initialize(self.root, fixture.project_id, "47")
        na = AnalysisNotApplicable(mode="not_applicable", reason="Synthetic archive test only")
        write_model(self.root / setup.contract, ElectricalAnalysisContract(
            project_id=fixture.project_id, ngspice_version="47", grounding=na, power=na,
            high_frequency=na,
        ))
        contract_path = self.root / f"examples/projects/{fixture.project_id}/tests/contract.json"
        contract = json.loads(contract_path.read_text())
        contract["validation"]["components"] = {"R1": {"value": "synthetic", "footprint": ""}}
        contract_path.write_text(json.dumps(contract))
        fixture.git("add", "--all")
        fixture.git("-c", "user.name=Test fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "Synthetic electrical applicability")
        self.source = source_state(self.root)
        native = read_model(fixture.native_path, ValidationSummary)
        hashes = {name: self.source.files_sha256[name] for name in fixture.config.required_inputs}
        checks = dict(native.checks)
        checks.update(grounding=CheckEvidence(status="PASS"), netlist=CheckEvidence(status="PASS"))
        for name in ("source_scope", "source_unchanged"):
            checks[name] = checks[name].model_copy(update={"source_hashes": hashes})
        netlist = fixture.native_path.parent / "netlist.xml"
        netlist.write_text('<export><components><comp ref="R1"><value>synthetic</value>'
                           '</comp></components><nets/></export>')
        shutil.copy2(fixture.native_path.parent / "version.command.json",
                     fixture.native_path.parent / "netlist.command.json")
        artifacts = dict(native.artifacts_sha256)
        artifacts.update({name: digest(fixture.native_path.parent / name)
                          for name in ("netlist.xml", "netlist.command.json")})
        write_model(fixture.native_path, native.model_copy(update={
            "source": self.source, "checked_commit": self.source.commit, "checks": checks,
            "artifacts_sha256": artifacts,
        }))

    def copy_native(self, _root, _project, output, _cli, _dependencies, export_only=False):
        self.assertFalse(export_only)
        shutil.copytree(self.fixture.native_path.parent, output)

    def command(self, *args: str) -> tuple[int, dict]:
        output = StringIO()
        with patch.object(sys, "argv", ["release", "--root", str(self.root), *args]), redirect_stdout(output):
            code = cli.main()
        return code, json.loads(output.getvalue())

    def test_release_electrical_cli_mcp_roundtrip_and_missing_evidence(self) -> None:
        with (patch("kicad_tooling.hwrepo.releasing.run_native", side_effect=self.copy_native),
              patch("kicad_tooling.hwrepo.mcp_workflow.doctor", return_value=test_mcp_workflow.runner_report()),
              patch("kicad_tooling.hwrepo.mcp_workflow.cli_executable", return_value="kicad-cli")):
            code, prepared = self.command("prepare", "--project", self.fixture.project_id,
                                          "--release-id", "cli-review", "--cli", "kicad-cli", "--json")
            self.assertEqual(code, 0)
            mcp = workflow.prepare_review(self.root, self.fixture.project_id, "mcp-review", "local")
        self.assertEqual(set(prepared["evidence"]["electrical"]), {self.fixture.project_id})
        self.assertEqual(set(mcp.evidence.electrical), {self.fixture.project_id})
        self.assertIsNone(mcp.approval)
        for release_id in ("cli-review", "mcp-review"):
            name = f"build/releases/{release_id}/manifest.json"
            code, checked = self.command("check", "--manifest", name)
            self.assertEqual(code, 0, checked)
            self.assertEqual(checked, workflow.check_release(self.root, name).model_dump(mode="json"))
            packaged = workflow.package_release(self.root, name, release_id)
            self.assertEqual(packaged.status, "PASS")
            archive = f"build/packages/{release_id}.zip"
            self.assertEqual(self.command("verify", "--archive", str(self.root / archive))[0], 0)
            restored = workflow.restore_package(self.root, archive, release_id)
            self.assertEqual(restored.status, "PASS")
            self.assertEqual(source_state(self.root / "build/restores" / release_id), self.source)
            review = (self.root / f"build/releases/{release_id}/review.md").read_text()
            self.assertIn("PASS", review)
            manifest = read_model(self.root / name, ReleaseManifest)
            bad = manifest.model_copy(update={"evidence": manifest.evidence.model_copy(update={"electrical": {}})})
            write_model(self.root / name, bad)
            code, failed = self.command("check", "--manifest", name)
            self.assertEqual(code, 1)
            self.assertEqual(failed, workflow.check_release(self.root, name).model_dump(mode="json"))
            self.assertIn("RELEASE_EVIDENCE", {row["code"] for row in failed["issues"]})
            with self.assertRaises(ValueError):
                workflow.package_release(self.root, name, release_id + "-missing")
