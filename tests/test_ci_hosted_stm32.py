"""Digest-pinned native STM32 pin-map fixture regressions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
)
from tests.support import reference_root

pytestmark = pytest.mark.template_checkout


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_STM32_PIN_MAP_FIXTURES") == "1",
    "native STM32 pin-map fixtures run in the digest-pinned package acceptance lane",
)
class NativeStm32PinMapFixtureTests(unittest.TestCase):
    def test_cube_mx_and_schematic_pin_map_faults_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import stm32_pin_map_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-stm32-pin-map-project-", dir=acceptance))
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
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture_root = repository / "tests/fixtures/design_lint/stm32-pin-map-native"
        expected_source_hashes = {
            "valid.kicad_sch": "5656bf52778eb58d224d7b211999cb816c26bbf7220fc6430887b74ee3b42716",
            "net-drift.kicad_sch": "399e94cf7213b926e435c1053a43da4ad6a2e82a419d8763ebd3df10b4b50738",
            "valid.ioc": "f36873f874ab1ac1252ec8012b491042eca3ed24129dbd51d5f6053d50821c42",
            "signal-drift.ioc": "5bcd5d407060c7c7978e773f1929e6713c275b23c6cc7563faecce2e6a61867a",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected_source_hashes
            },
            expected_source_hashes,
        )
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-stm32-pin-map-{project}")
                stm32_pin_map_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("stm32-pin-map-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "stm32-pin-map-fixture/native-export",
                        "stm32-pin-map-fixture/control",
                        "stm32-pin-map-fixture/net-drift",
                        "stm32-pin-map-fixture/signal-drift",
                    },
                )
                self.assertEqual(results["stm32-pin-map-fixture/control"]["lint_status"], "PASS")
                self.assertEqual(results["stm32-pin-map-fixture/control"]["mismatch_pins"], "none")
                for case in ("net-drift", "signal-drift"):
                    result = results[f"stm32-pin-map-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["lint_status"], "REVIEW")
                    self.assertEqual(result["mismatch_pins"], "PA0")
                for case in ("control", "net-drift", "signal-drift"):
                    result = results[f"stm32-pin-map-fixture/{case}"]
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertIn(result["source_sha256"], expected_source_hashes.values())
                    self.assertIn(result["ioc_sha256"], expected_source_hashes.values())
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
