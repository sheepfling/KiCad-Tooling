"""Digest-pinned native control-input fixture regressions."""

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
    os.environ.get("KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES") == "1",
    "native control-input demos run in the digest-pinned package acceptance lane",
)
class NativeControlInputDemoTests(unittest.TestCase):
    def test_native_public_demos_record_connected_bias_and_unconnected_controls(self) -> None:
        from kicad_tooling.ci_hosted import native_control_input_demo_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-control-input-demo-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        project = "raspberry-pi-status-led"
        config = selected_config(root, project)
        self.assertEqual(config.kicad_version, "10.0.5")
        log = HostedLog(root, "native-control-input-demos")
        native_control_input_demo_lane(root, project=project, image=config.image, log=log)

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("control-input-demo/")
        }
        expected_candidates = {
            "cm5-minima": "none",
            "jetson-agx-thor": "J14.23|SDIO_~{RESET}|reset|input",
            "coldfire-xilinx": "VR201.4|SHDN|enable|input",
            "vme-wren": (
                "IC19.3|~{RESET}|reset|input;IC21.3|~{RESET}|reset|input;"
                "IC30.33|BOOT_B|boot/strap|input;IC30.38|BOOT_A|boot/strap|input"
            ),
            "por-alias-fixture": "U1.1|POR_B|reset|input",
        }
        expected_connected_bias = {
            "cm5-minima": (
                4,
                "7c96b511e8fa95eef6dc8fff36c45e92c34e1cfbcc54db7400a2e3149fdd9709",
            ),
            "jetson-agx-thor": (
                24,
                "04bd60403bf87f8a4edf249d582a5b7620974dd333b53e5e80c6db9af8dc9f71",
            ),
            "coldfire-xilinx": (
                2,
                "371dfc8d9313aabf215947750e2ad170d9c5b69f6f03a171ae90e81a73bfb929",
            ),
            "vme-wren": (
                12,
                "2ee541b32622143b5293f6add4da0d0c6b32137ec15521fd2bafb6fe9e3df050",
            ),
            "por-alias-fixture": (
                0,
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
            ),
        }
        self.assertEqual(
            set(results),
            {"control-input-demo/native-export"}
            | {f"control-input-demo/{sample}" for sample in expected_candidates},
        )
        native = results["control-input-demo/native-export"]
        self.assertEqual(native["status"], "PASS")
        receipt = root / native["command_receipt"]
        self.assertTrue(receipt.is_file())
        command = json.loads(receipt.read_text())
        argv = command["argv"]
        self.assertIn("none", argv)
        self.assertIn("--read-only", argv)
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        self.assertEqual(len(mounts), 2)
        self.assertEqual(sum(item.endswith(":/synthetic:ro") for item in mounts), 1)
        self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)

        for sample, expected in expected_candidates.items():
            with self.subTest(sample=sample):
                result = results[f"control-input-demo/{sample}"]
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["kicad_version"], "10.0.5")
                self.assertEqual(result["image"], config.image)
                self.assertEqual(result["review_candidates"], expected)
                expected_count, expected_sha256 = expected_connected_bias[sample]
                bias_candidates = json.loads(result["connected_bias_candidates"])
                self.assertEqual(len(bias_candidates), expected_count)
                self.assertEqual(result["connected_bias_candidate_count"], str(expected_count))
                canonical_bias_candidates = json.dumps(
                    bias_candidates,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                self.assertEqual(
                    hashlib.sha256(canonical_bias_candidates).hexdigest(), expected_sha256
                )
                self.assertEqual(result["connected_bias_candidates_sha256"], expected_sha256)
                self.assertEqual(result["repeatable"], "true")
                self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(result["source_manifest_sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(int(result["source_manifest_entries"]), 0)
                self.assertRegex(result["raw_netlist_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(result["repeat_raw_netlist_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    result["normalized_netlist_sha256"],
                    result["repeat_normalized_netlist_sha256"],
                )
