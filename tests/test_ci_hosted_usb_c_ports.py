"""Digest-pinned native USB-C port fixture regressions."""

from __future__ import annotations

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
    os.environ.get("KICAD_RUN_NATIVE_USB_C_PORT_FIXTURES") == "1",
    "native USB-C port fixtures run in the digest-pinned package acceptance lane",
)
class NativeUsbCPortFixtureTests(unittest.TestCase):
    def test_native_role_prompt_covers_unknown_source_and_sink_topologies(self) -> None:
        from kicad_tooling.ci_hosted import usb_c_port_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-usb-c-port-project-", dir=acceptance))
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
        expected_source_hashes = {
            "connector": "42935f2e21f3b86acc33a87916072b466d5c75b61cddd472a40fb6219d59ce9a",
            "source-rp-control": "b9913fa1e44adaaa3837257dc0756bcb39411b9bb79dcd1568c1a264248a1f8f",
            "sink-rd-control": "5ac40420e4adcc7f2005e1808f1ebdeb765fd4907113bfa5be657407d2d6d789",
            "vbus-capacitance-control": "d664fe8ece994d847c133187c14bcc279c2466eb917ddddddac4faa22c17c6ca",
            "vbus-capacitance-fault": "c126f173af020b3aa2eeebf74657064685e87eac684b4b197a15d82992970560",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-usb-c-port-{project}")
                usb_c_port_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("usb-c-port-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "usb-c-port-fixture/native-export",
                        "usb-c-port-fixture/unmapped",
                        "usb-c-port-fixture/mapped",
                        "usb-c-port-fixture/source-rp-control",
                        "usb-c-port-fixture/sink-rd-control",
                        "usb-c-port-fixture/vbus-capacitance-control",
                        "usb-c-port-fixture/vbus-capacitance-fault",
                    },
                )
                unmapped = results["usb-c-port-fixture/unmapped"]
                self.assertEqual(unmapped["status"], "PASS")
                self.assertEqual(unmapped["lint_status"], "REVIEW")
                self.assertEqual(unmapped["findings"], "J1: USB-C role-map coverage")
                self.assertEqual(unmapped["cc_pin_functions"], "J1.4=CC1;J1.5=CC2")
                mapped = results["usb-c-port-fixture/mapped"]
                self.assertEqual(mapped["status"], "PASS")
                self.assertEqual(mapped["lint_status"], "PASS")
                self.assertEqual(mapped["findings"], "none")
                for case in ("source-rp-control", "sink-rd-control"):
                    with self.subTest(fixture=case):
                        result = results[f"usb-c-port-fixture/{case}"]
                        self.assertEqual(result["status"], "PASS")
                        self.assertEqual(result["lint_status"], "REVIEW")
                        self.assertEqual(result["findings"], "J1: USB-C role-map coverage")
                        self.assertEqual(result["cc_pin_functions"], "J1.4=CC1;J1.5=CC2")
                        self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                        self.assertEqual(result["fixture_case"], case)
                capacitance_control = results["usb-c-port-fixture/vbus-capacitance-control"]
                self.assertEqual(capacitance_control["status"], "PASS")
                self.assertEqual(capacitance_control["check_status"], "PASS")
                self.assertEqual(capacitance_control["expected_check_status"], "PASS")
                self.assertEqual(float(capacitance_control["observed_nf"]), 4700.0)
                capacitance_fault = results["usb-c-port-fixture/vbus-capacitance-fault"]
                self.assertEqual(capacitance_fault["status"], "PASS")
                self.assertEqual(capacitance_fault["check_status"], "FAIL")
                self.assertEqual(capacitance_fault["expected_check_status"], "FAIL")
                self.assertEqual(float(capacitance_fault["observed_nf"]), 2200.0)
                for case, result in (
                    ("connector", unmapped),
                    ("connector", mapped),
                    ("source-rp-control", results["usb-c-port-fixture/source-rp-control"]),
                    ("sink-rd-control", results["usb-c-port-fixture/sink-rd-control"]),
                    ("vbus-capacitance-control", capacitance_control),
                    ("vbus-capacitance-fault", capacitance_fault),
                ):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["repeat_normalized_netlist_sha256"],
                        result["normalized_netlist_sha256"],
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
