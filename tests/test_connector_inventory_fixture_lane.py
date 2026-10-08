"""Synthetic orchestration checks for pinned connector-inventory netlist exports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, connector_inventory_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract


class ConnectorInventoryFixtureLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="connector-inventory-lane-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = "fixture.invalid/kicad@sha256:" + "b" * 64
        self.config = SimpleNamespace(image=self.image, kicad_version="10.0.0")
        self.observed = {
            "fault": NetlistContract(
                components={},
                nets={},
                component_symbols={
                    "U7": "Connector_Generic:Conn_01x02",
                    "U8": "Connector:TestPoint_Alt",
                },
            ),
            "control": NetlistContract(
                components={},
                nets={},
                component_symbols={"U8": "Connector:TestPoint_Alt"},
            ),
        }

    def test_pinned_export_detects_nonstandard_reference_and_keeps_test_point_control(self) -> None:
        def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(timeout, 600)
            self.assertIn("--network", argv)
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertIn("--read-only", argv)
            self.assertEqual(argv[argv.index("--entrypoint") + 1], "/bin/sh")
            self.assertEqual(argv[argv.index("--platform") + 1], "linux/amd64")
            self.assertIn(self.image, argv)
            script = argv[-1]
            self.assertIn('test "$actual" = "10.0.0"', script)
            self.assertIn("kicad-cli sch export netlist", script)

            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            self.assertEqual(len(mounts), 2)
            source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
            output_directory = Path(output_mount.removesuffix(":/output:rw"))
            self.assertEqual(
                {item.name for item in source_directory.iterdir()},
                {"fault.kicad_sch", "control.kicad_sch"},
            )
            for case in ("fault", "control"):
                for run in ("first", "repeat"):
                    (output_directory / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} netlist export {run}\n",
                        encoding="utf-8",
                    )
            return CommandEvidence(
                argv=argv,
                started_utc="2026-09-30T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path) -> NetlistContract:
            case = path.name.split(".", 1)[0]
            return self.observed[case]

        log = HostedLog(self.root, "connector-inventory")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
        ):
            connector_inventory_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
                log=log,
            )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("connector-inventory-fixture/")
        }
        fault = results["connector-inventory-fixture/fault"]
        control = results["connector-inventory-fixture/control"]
        self.assertEqual(fault["status"], "PASS")
        self.assertEqual(fault["coverage_status"], "UNDECLARED")
        self.assertEqual(fault["candidate_references"], "U7")
        self.assertEqual(control["status"], "PASS")
        self.assertEqual(control["coverage_status"], "COMPLETE")
        self.assertEqual(control["candidate_references"], "none")
        self.assertEqual(
            fault["normalized_netlist_sha256"], fault["repeat_normalized_netlist_sha256"]
        )
        self.assertEqual(
            control["normalized_netlist_sha256"], control["repeat_normalized_netlist_sha256"]
        )
        self.assertTrue((self.root / fault["command_receipt"]).is_file())
        export = results["connector-inventory-fixture/native-export"]
        self.assertEqual(export["status"], "PASS")
        self.assertEqual(export["kicad_version"], "10.0.0")


if __name__ == "__main__":
    unittest.main()
