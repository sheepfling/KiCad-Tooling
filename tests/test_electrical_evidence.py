"""Release electrical evidence rejects stale, incomplete and relabeled receipts."""

from __future__ import annotations

import json
import subprocess
import unittest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.electrical_evidence import required_projects, verify_electrical
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ReleaseClass,
    ReleaseEvidence,
    ReleaseManifest,
    ReleaseStatus,
)
from kicad_tooling.hwrepo.releasing import reference, retained_paths
from tests import test_contract_coach as coaching
from tests.support import initialize_git
from tests.test_electrical import ISLAND, NA, PROJECT, install_fixture


class ElectricalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = coaching.ContractCoachTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.native = reference(self.root, fixture.native / "summary.json")
        self.contract = install_fixture(self.root).model_copy(
            update={"grounding": NA, "high_frequency": NA}
        )
        write_model(self.root / ISLAND / "tests/electrical.json", self.contract)
        initialize_git(self.root)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic requirements",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        waveform = (
            "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
            "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
            "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
        )
        self.simulator = coaching.fake_executable(
            self.root.parent / "ngspice",
            (
                "from pathlib import Path\nimport sys\n"
                "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
                "else:\n"
                f"    Path('waveforms.raw').write_text({waveform!r})\n"
                "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
                "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
            ),
        )
        self.output = self.root / "build/electrical/release"
        result = analyze(self.root, PROJECT, self.output, ngspice=str(self.simulator))
        self.assertEqual(result.status, "PASS", result)
        self.path = self.output / "electrical.json"

    def verify(self) -> None:
        verify_electrical(
            self.root, reference(self.root, self.path), self.source, PROJECT, self.native
        )

    def test_exact_saved_requirements_logs_and_waveforms_pass_without_a_simulator(self) -> None:
        self.simulator.unlink()
        self.verify()
        result = json.loads(self.path.read_text())
        self.assertEqual(result["source"]["commit"], self.source.commit)
        candidate = ReleaseManifest(
            release_id="test",
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE,
            source_commit=self.source.commit or "",
            toolchain_id="kicad-10.0.0",
            projects=(PROJECT,),
            libraries=(),
            interfaces=(),
            artifacts=(),
            evidence=ReleaseEvidence(
                portable=self.native,
                native={},
                electrical={PROJECT: reference(self.root, self.path)},
            ),
        )
        retained = retained_paths(self.root, candidate)
        self.assertIn(self.path.relative_to(self.root).as_posix(), retained)
        self.assertIn(
            (self.output / "startup/waveforms.raw").relative_to(self.root).as_posix(), retained
        )

    def test_relabeling_and_rehashing_cannot_hide_missing_or_failed_measurements(self) -> None:
        original = self.path.read_bytes()
        for change in ("checks", "commands", "inventory", "source", "project", "inputs"):
            with self.subTest(change=change):
                value = json.loads(original)
                if change == "checks":
                    value["checks"] = []
                elif change == "commands":
                    value["commands"].pop("startup")
                elif change == "inventory":
                    value["artifacts_sha256"].pop("startup/waveforms.raw")
                elif change == "source":
                    value["source"] = None
                elif change == "project":
                    value["project_id"] = "another-board"
                else:
                    value["input_sha256"] = {}
                self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    self.verify()
        self.path.write_bytes(original)
        command = self.output / "startup/ngspice.command.json"
        value = json.loads(command.read_text())
        value["stdout"] = "check0 = 9000\n"
        command.write_text(json.dumps(value))
        report = json.loads(original)
        report["commands"]["startup"] = value
        report["artifacts_sha256"]["startup/ngspice.command.json"] = digest(command)
        self.path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "checks fail"):
            self.verify()

    def test_changed_model_waveform_or_case_deck_cannot_reuse_receipt(self) -> None:
        for name in ("startup/waveforms.raw", "startup/simulation.cir"):
            path = self.output / name
            original = path.read_bytes()
            path.write_bytes(original + b"\nchanged")
            with self.assertRaises(ValueError):
                self.verify()
            path.write_bytes(original)
        model = self.root / ISLAND / "tests/electrical/startup.cir"
        model.write_bytes(model.read_bytes() + b"\n* changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.verify()

    def test_declared_contracts_gate_review_and_build_releases_require_applicability(self) -> None:
        projects = tuple(p for p in load_registry(self.root).projects if p.id == PROJECT)
        self.assertEqual(
            required_projects(self.root, projects, ReleaseClass.ENGINEERING_REVIEW), (PROJECT,)
        )
        path = self.root / ISLAND / "tests/contract.json"
        value = json.loads(path.read_text())
        value.pop("electrical")
        path.write_text(json.dumps(value))
        self.assertEqual(
            required_projects(self.root, projects, ReleaseClass.ENGINEERING_REVIEW), ()
        )
        with self.assertRaisesRegex(ValueError, "build releases require"):
            required_projects(self.root, projects, ReleaseClass.PROTOTYPE)

    def test_all_not_applicable_still_requires_bound_evidence(self) -> None:
        path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(path, ElectricalAnalysisContract).model_copy(update={"power": NA})
        write_model(path, contract)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qam",
                "Synthetic applicability",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        self.output = self.root / "build/electrical/not-applicable"
        result = analyze(self.root, PROJECT, self.output, ngspice="missing-simulator")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.commands, {})
        self.path = self.output / "electrical.json"
        self.verify()


if __name__ == "__main__":
    unittest.main()
