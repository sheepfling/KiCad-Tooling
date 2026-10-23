"""Exact-version native regression for mapped I2C pull-up arrays."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, i2c_pullup_native_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES") != "1",
    reason="native I2C pull-up fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_native_array_channel_fault_and_control_on_supported_images(tmp_path: Path) -> None:
    root = tmp_path / "project"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_toolchains = {
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
    normalized_hashes_by_version: dict[str, dict[str, str]] = {}
    for project, (version, image) in expected_toolchains.items():
        config = selected_config(root, project)
        assert (config.kicad_version, config.image) == (version, image)
        log = HostedLog(root, f"native-i2c-pullup-{project}")
        i2c_pullup_native_fixture_lane(root, project=project, image=config.image, log=log)
        events = tuple(
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("i2c-pullup-fixture/")
        }
        assert set(results) == {
            "i2c-pullup-fixture/native-export",
            "i2c-pullup-fixture/control",
            "i2c-pullup-fixture/fault",
            "i2c-pullup-fixture/symbol-resistor",
        }
        assert results["i2c-pullup-fixture/native-export"]["status"] == "PASS"
        control = results["i2c-pullup-fixture/control"]
        fault = results["i2c-pullup-fixture/fault"]
        symbol_resistor = results["i2c-pullup-fixture/symbol-resistor"]
        normalized_hashes_by_version[version] = {
            "control": control["normalized_netlist_sha256"],
            "fault": fault["normalized_netlist_sha256"],
            "symbol_resistor": symbol_resistor["normalized_netlist_sha256"],
        }
        assert (control["sda"], control["scl"]) == ("PASS", "PASS")
        assert (fault["sda"], fault["scl"]) == ("FAIL", "PASS")
        assert control["baseline_missing_pullup"] == "OPEN"
        assert control["heuristic_coverage"] == "COMPLETE"
        assert control["heuristic_findings"] == "none"
        assert control["input_limit_coverage"] == "SDA:OPEN,SCL:OPEN"
        assert control["input_limit_findings"] == "bus.i2c_pullup_input_limit_coverage"
        assert (control["sda_tolerance_scope"], control["scl_tolerance_scope"]) == (
            "PASS",
            "PASS",
        )
        assert (
            control["sda_capacitance_scope"],
            control["scl_capacitance_scope"],
        ) == ("PASS", "PASS")
        assert control["sda_capacitance_contributors"] == "X1"
        assert fault["baseline_missing_pullup"] == "OPEN"
        assert fault["heuristic_coverage"] == "OPEN"
        assert fault["heuristic_findings"] == "bus.i2c_missing_pullup"
        assert fault["input_limit_coverage"] == "SCL:OPEN"
        assert fault["input_limit_findings"] == "bus.i2c_pullup_input_limit_coverage"
        assert (fault["sda_tolerance_scope"], fault["scl_tolerance_scope"]) == (
            "PASS",
            "PASS",
        )
        assert (fault["sda_capacitance_scope"], fault["scl_capacitance_scope"]) == (
            "FAIL",
            "PASS",
        )
        assert fault["sda_capacitance_contributors"] == "X1"
        assert fault["sda_capacitance_unmapped"] == "X2"
        assert symbol_resistor["status"] == "PASS"
        assert symbol_resistor["component_reference"] == "X1"
        assert symbol_resistor["component_symbol"] == "Device:R"
        assert symbol_resistor["component_pins"] == "1,2"
        assert symbol_resistor["pullup_path"] == "X1=4700Ω to +3V3"
        assert symbol_resistor["repeatable"] == "true"
        assert (
            symbol_resistor["normalized_netlist_sha256"]
            == symbol_resistor["repeat_normalized_netlist_sha256"]
        )
        assert control["contract_path"] == "projects/synthetic-i2c-array/electrical.json"
        assert control["contract_sha256"] == fault["contract_sha256"]
        for result in (control, fault):
            assert result["status"] == "PASS"
            assert result["kicad_version"] == version
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert result["heuristic_coverage"] in {"COMPLETE", "OPEN"}
            assert len(result["contract_sha256"]) == 64
            digests = (result["source_sha256"], result["normalized_netlist_sha256"])
            assert all(len(digest) == 64 for digest in digests)
            assert all(
                character in "0123456789abcdef" for digest in digests for character in digest
            )
            assert_native_fixture_mounts(root, result["command_receipt"])
    assert normalized_hashes_by_version["10.0.0"] == normalized_hashes_by_version["10.0.5"]
