"""Exact-version native exports for the mapped power-sequence heuristic."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, power_sequence_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence
from tests.support import reference_root
from tests.test_power_sequences import (
    power_sequence_netlist,
    power_sequence_output_cycle_netlist,
)


class PowerSequenceFixtureLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="power-sequence-lane-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = "fixture.invalid/kicad@sha256:" + "c" * 64
        self.config = SimpleNamespace(image=self.image, kicad_version="10.0.0")

    def test_native_export_requires_exact_pins_and_catches_open_enable(self) -> None:
        def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(timeout, 600)
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertIn("--read-only", argv)
            self.assertIn(self.image, argv)
            script = argv[-1]
            self.assertIn('test "$actual" = "10.0.0"', script)
            self.assertIn("kicad-cli sch export netlist", script)
            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            self.assertEqual(len(mounts), 2)
            fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
            output = Path(output_mount.removesuffix(":/output:rw"))
            self.assertEqual(
                {item.name for item in fixtures.iterdir() if item.suffix == ".kicad_sch"},
                {
                    "control.kicad_sch",
                    "open-enable.kicad_sch",
                    "output-enable-cycle.kicad_sch",
                },
            )
            for case in ("control", "open-enable", "output-enable-cycle"):
                for run in ("first", "repeat"):
                    (output / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} export {run}\n", encoding="utf-8"
                    )
            return CommandEvidence(
                argv=argv,
                started_utc="2026-09-30T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path):
            if path.name.startswith("output-enable-cycle"):
                return power_sequence_output_cycle_netlist(cycle=True)
            observed = (
                power_sequence_netlist(fault="open-enable")
                if path.name.startswith("open-enable")
                else power_sequence_netlist()
            )
            nets = dict(observed.nets)
            if path.name.startswith("open-enable"):
                nets["FLOATING_ENABLE"] = nets.pop("FLOATING")
            nets["GOOD_B"] = ("U2.3",)
            return observed.model_copy(update={"nets": nets})

        log = HostedLog(self.root, "power-sequence")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        ):
            power_sequence_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
                log=log,
            )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("power-sequence-fixture/")
        }
        control = results["power-sequence-fixture/control"]
        fault = results["power-sequence-fixture/open-enable"]
        native = results["power-sequence-fixture/native-export"]
        self.assertEqual(control["status"], "PASS")
        self.assertEqual(control["lint_status"], "PASS")
        self.assertEqual(control["power_sequence_findings"], "none")
        self.assertEqual(control["observed_enable_net"], "GOOD_A")
        self.assertEqual(fault["status"], "PASS")
        self.assertEqual(fault["lint_status"], "REVIEW")
        self.assertEqual(
            fault["power_sequence_findings"], "power.mapped_sequence_dependency_mismatch"
        )
        self.assertEqual(fault["observed_enable_net"], "FLOATING_ENABLE")
        cycle = results["power-sequence-fixture/output-enable-cycle"]
        self.assertEqual(cycle["status"], "PASS")
        self.assertEqual(cycle["lint_status"], "REVIEW")
        self.assertEqual(
            cycle["power_sequence_findings"],
            "power.mapped_sequence_dependency_mismatch",
        )
        self.assertEqual(cycle["observed_enable_cycle_stages"], "rail-a,rail-b")
        for case in (control, fault, cycle):
            self.assertEqual(case["repeatable"], "true")
            self.assertEqual(
                case["normalized_netlist_sha256"], case["repeat_normalized_netlist_sha256"]
            )
        self.assertEqual(native["status"], "PASS")
        self.assertEqual(native["kicad_version"], "10.0.0")
        self.assertEqual(native["repeatability_basis"], "canonical_native_netlist")
        command_receipt = self.root / native["command_receipt"]
        self.assertTrue(command_receipt.is_file())

    def test_unsupported_native_version_fails_before_export(self) -> None:
        config = SimpleNamespace(image=self.image, kicad_version="9.0.0")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command") as run_command,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 9.0.0"),
        ):
            power_sequence_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
                log=HostedLog(self.root, "unsupported-version"),
            )
        run_command.assert_not_called()


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES") == "1",
    "native power-sequence exports run in the digest-pinned package acceptance lane",
)
class NativePowerSequenceFixtureTests(unittest.TestCase):
    def test_control_open_enable_and_cycle_repeat_on_pinned_kicad_versions(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-power-sequence-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected = {
            "controller": (
                "10.0.0",
                (
                    "ghcr.io/kicad/kicad:10.0.0@sha256:"
                    "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
                ),
            ),
            "raspberry-pi-status-led": (
                "10.0.5",
                (
                    "ghcr.io/kicad/kicad:10.0.5@sha256:"
                    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
                ),
            ),
        }
        fixture_root = repository / "tests/fixtures/design_lint/power-sequence-native"
        expected_sources = {
            "control": "f1104387c9208d6be6a608872ddc9425158b05572d351e4afbd80d72a2f447c3",
            "open-enable": "b093d3b7b7b57f7a8aa3e1fa86b4c7c6b3440ebc6c3ee5d5c4a15ee4818f99fb",
            "output-enable-cycle": "da22daa43ad104bdce3e499d651c36b5a0ed6556cd75347a07eed5a21ea22c6d",
        }
        self.assertEqual(
            {
                case: hashlib.sha256((fixture_root / f"{case}.kicad_sch").read_bytes()).hexdigest()
                for case in expected_sources
            },
            expected_sources,
        )
        for project, (version, image) in expected.items():
            with self.subTest(project=project):
                from kicad_tooling.hwrepo.electrical import selected_config

                config = selected_config(root, project)
                self.assertEqual((config.kicad_version, config.image), (version, image))
                log = HostedLog(root, f"native-power-sequence-{project}")
                power_sequence_fixture_lane(root, project=project, image=image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("power-sequence-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "power-sequence-fixture/native-export",
                        "power-sequence-fixture/control",
                        "power-sequence-fixture/open-enable",
                        "power-sequence-fixture/output-enable-cycle",
                    },
                )
                native = results["power-sequence-fixture/native-export"]
                self.assertEqual(native["status"], "PASS")
                self.assertEqual(native["kicad_version"], version)
                self.assertEqual(native["image"], image)
                self.assertEqual(native["repeatable"], "true")
                self.assertEqual(native["repeatability_basis"], "canonical_native_netlist")
                self.assertEqual(
                    native["source_hashes"],
                    ",".join(f"{case}:{expected_sources[case]}" for case in expected_sources),
                )
                self.assertEqual(results["power-sequence-fixture/control"]["lint_status"], "PASS")
                self.assertEqual(
                    results["power-sequence-fixture/open-enable"]["lint_status"], "REVIEW"
                )
                cycle = results["power-sequence-fixture/output-enable-cycle"]
                self.assertEqual(cycle["lint_status"], "REVIEW")
                self.assertEqual(cycle["observed_enable_cycle_stages"], "rail-a,rail-b")
                for case in ("control", "open-enable", "output-enable-cycle"):
                    result = results[f"power-sequence-fixture/{case}"]
                    self.assertEqual(result["source_sha256"], expected_sources[case])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                receipt = root / native["command_receipt"]
                self.assertTrue(receipt.is_file())
                command = json.loads(receipt.read_text())
                mounts = tuple(
                    command["argv"][index + 1]
                    for index, item in enumerate(command["argv"][:-1])
                    if item == "-v"
                )
                self.assertEqual(len(mounts), 2)
                self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


if __name__ == "__main__":
    unittest.main()
