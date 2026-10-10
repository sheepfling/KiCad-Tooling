"""Digest-pinned native connector inventory acceptance."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from tests.support import reference_root

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") == "1",
    "native connector fixtures run in the digest-pinned package acceptance lane",
)
class NativeConnectorInventoryFixtureTests(unittest.TestCase):
    def test_native_netlist_connector_inventory_candidates_and_test_point_control(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, connector_inventory_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-connector-inventory-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-connector-inventory-{project}")
                connector_inventory_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("connector-inventory-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "connector-inventory-fixture/native-export",
                        "connector-inventory-fixture/fault",
                        "connector-inventory-fixture/control",
                    },
                )
                fault = results["connector-inventory-fixture/fault"]
                control = results["connector-inventory-fixture/control"]
                self.assertEqual(fault["coverage_status"], "UNDECLARED")
                self.assertEqual(fault["candidate_references"], "U7")
                self.assertEqual(control["coverage_status"], "COMPLETE")
                self.assertEqual(control["candidate_references"], "none")
                for result in (fault, control):
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["coverage_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
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
