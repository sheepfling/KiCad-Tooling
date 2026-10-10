"""Digest-pinned native acceptance for LED rail and output-path heuristics."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_LED_RAIL_FIXTURES") != "1",
    reason="native LED rail fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_direct_rail_and_output_driven_led_faults_with_series_controls(
    hosted_reference_root: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, led_rail_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    root = hosted_reference_root
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    expected_source_hashes = {
        "direct-rails": "998164b255a1ec4c71a1faf1681366ea0bf3e253cc1a9833d3a6c85b838816b8",
        "series-control": "00d7ab8dc51351f400f5599526304ab4576ced2d9cd9f583f093cb37705456c3",
        "parallel-resistor": "b5fef4b342eccddf9b582ad725ee69aa910b595c92f44042e999c6810459cffd",
        "direct-output": "a71215195b1273c29ebbe318d52d32ba7db568a8cb49476ed34bea0252fbdfb2",
        "series-return-control": "d64eac25b88d7d355e81f8f05001976f15ea989d9b518086499e30e7ef48ba2c",
        "parallel-output-resistor": "1c37d1e6c7a70f460f4525f25c1d0ebe89dd8db0cbe8e17b415a15827a9422a0",
        "custom-direct-output": "2e2d6909d49c5815c5254aea14125ac6243fba0d45307d875c2563d657bc4f7b",
        "custom-series-return-control": "c5a254ead0887da399cd2ace46db4fde8231711abdb602304eac7e1be68ff047",
    }
    expected_findings: dict[str, set[str]] = {
        "direct-rails": {"D1: LED directly spans supply and return"},
        "series-control": set(),
        "parallel-resistor": {"D1: LED directly spans supply and return"},
        "direct-output": set(),
        "series-return-control": set(),
        "parallel-output-resistor": set(),
        "custom-direct-output": set(),
        "custom-series-return-control": set(),
    }
    expected_output_findings: dict[str, set[str]] = {
        "direct-rails": set(),
        "series-control": set(),
        "parallel-resistor": set(),
        "direct-output": {"D1: LED directly shares an output net and a rail"},
        "series-return-control": set(),
        "parallel-output-resistor": {"D1: LED directly shares an output net and a rail"},
        "custom-direct-output": {"D1: LED directly shares an output net and a rail"},
        "custom-series-return-control": set(),
    }
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-led-rail-{project}")
    led_rail_fixture_lane(
        root,
        project=project,
        image=config.image,
        log=log,
    )
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("led-rail-fixture/")
    }
    assert set(results) == {
        "led-rail-fixture/native-export",
        "led-rail-fixture/direct-rails",
        "led-rail-fixture/series-control",
        "led-rail-fixture/parallel-resistor",
        "led-rail-fixture/direct-output",
        "led-rail-fixture/series-return-control",
        "led-rail-fixture/parallel-output-resistor",
        "led-rail-fixture/custom-direct-output",
        "led-rail-fixture/custom-series-return-control",
    }
    assert results["led-rail-fixture/native-export"]["status"] == "PASS"
    for case, expected in expected_findings.items():
        result = results[f"led-rail-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert (
            set(result["led_rule_findings"].split(";"))
            if result["led_rule_findings"] != "none"
            else set()
        ) == expected
        assert (
            set(result["led_output_rule_findings"].split(";"))
            if result["led_output_rule_findings"] != "none"
            else set()
        ) == expected_output_findings[case]
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == expected_source_hashes[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        receipt = root / result["command_receipt"]
        assert receipt.is_file()
        command = json.loads(receipt.read_text())
        mounts = tuple(
            command["argv"][index + 1]
            for index, item in enumerate(command["argv"][:-1])
            if item == "-v"
        )
        assert len(mounts) == 2
        assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
        assert sum(item.endswith(":/output:rw") for item in mounts) == 1
