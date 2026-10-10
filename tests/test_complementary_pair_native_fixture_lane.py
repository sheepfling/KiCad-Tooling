"""Digest-pinned native acceptance for USB SuperSpeed pair checks."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES") != "1",
    reason="native complementary-pair fixtures run in the digest-pinned package acceptance lane",
)
def test_usb_superspeed_fault_and_control_export_repeatably(
    hosted_reference_root: Path,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, complementary_pair_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    root = hosted_reference_root
    expected_versions = (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    normalized_hashes: dict[str, dict[str, str]] = {}
    for project, version in expected_versions:
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == expected_images[project]
        log = HostedLog(root, f"native-complementary-pair-{project}")
        complementary_pair_fixture_lane(
            root,
            project=project,
            image=config.image,
            log=log,
        )
        results = {
            item["stage"]: item
            for item in (json.loads(line) for line in log.events.read_text().splitlines())
            if item.get("stage", "").startswith("complementary-pair-fixture/")
        }
        assert set(results) == {
            "complementary-pair-fixture/native-export",
            "complementary-pair-fixture/fault",
            "complementary-pair-fixture/control",
        }
        fault = results["complementary-pair-fixture/fault"]
        control = results["complementary-pair-fixture/control"]
        assert fault["lint_status"] == "REVIEW"
        assert fault["pair_findings"] == "J1: USB SuperSpeed RX pair"
        assert "J1.4=StdA_SSRX-" in fault["pin_functions"]
        assert control["lint_status"] == "PASS"
        assert control["pair_findings"] == "none"
        for result in (fault, control):
            assert result["kicad_version"] == version
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert re.fullmatch("^[0-9a-f]{64}$", result["source_sha256"])
            assert re.fullmatch("^[0-9a-f]{64}$", result["normalized_netlist_sha256"])
        normalized_hashes[version] = {
            case: results[f"complementary-pair-fixture/{case}"]["normalized_netlist_sha256"]
            for case in ("fault", "control")
        }
    assert set(normalized_hashes) == {"10.0.0", "10.0.5"}
    assert normalized_hashes["10.0.0"] == normalized_hashes["10.0.5"]
