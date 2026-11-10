"""Synthetic orchestration checks for the source-bound I2C array lane."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted_i2c_pullup_fixtures as i2c_pullup_service
from kicad_tooling.ci_hosted import HostedLog, i2c_pullup_native_fixture_lane
from kicad_tooling.hwrepo.models import CommandEvidence
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import i2c_netlist_with_parallel_sda
from tests.design_lint_fixtures.i2c_arrays import array_netlist_with_capacitor
from tests.design_lint_fixtures.i2c_resistor_symbols import i2c_netlist_with_device_r_symbol

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _low_resistance_observation(value: str) -> NetlistContract:
    source = i2c_netlist_with_parallel_sda(value)
    return source.model_copy(
        update={
            "components": {"R1": source.components["R1"], "R2": source.components["R3"]},
            "nets": {
                "I2C_SDA": ("R1.2", "R2.2", "U1.1"),
                "I2C_SCL": ("U1.2",),
                "+3V3": ("R1.1", "R2.1"),
            },
            "component_symbols": {
                "U1": "Synthetic:I2cTarget",
                "R1": "Device:R",
                "R2": "Device:R",
            },
            "component_pin_numbers": {"R1": ("1", "2"), "R2": ("1", "2")},
        }
    )


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_native_array_lane_checks_contract_resolution_against_typed_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    image = (
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
    )
    config = SimpleNamespace(kicad_version="10.0.0", image=image)
    control = array_netlist_with_capacitor(reference="X1", value="0,01nF, 10%").model_copy(
        update={
            "nets": {
                "I2C_SDA": ("RN1.1", "U1.1", "X1.1"),
                "I2C_SCL": ("RN1.3", "U1.2"),
                "+3V3": ("RN1.2", "RN1.4"),
                "GND": ("X1.2",),
            }
        }
    )
    fault = array_netlist_with_capacitor(
        reference="X1",
        extra_capacitor=True,
        extra_reference="X2",
        value="0,01nF, 10%",
    )
    fault_nets = dict(fault.nets)
    fault_nets["I2C_SDA"] = ("U1.1", "X1.1", "X2.1")
    fault_nets["SDA_WRONG"] = ("RN1.1",)
    fault = fault.model_copy(update={"nets": fault_nets})
    symbol_resistor = i2c_netlist_with_device_r_symbol()
    low_resistance_observations = {
        "low_resistance_control": _low_resistance_observation("2,0k"),
        "low_resistance_fault": _low_resistance_observation("1,5k"),
    }
    observations = {
        "control": control,
        "fault": fault,
        **low_resistance_observations,
        "symbol_resistor": symbol_resistor.model_copy(
            update={
                "nets": {
                    "I2C_SDA": ("X1.1",),
                    "+3V3": ("X1.2",),
                }
            }
        ),
    }

    def fake_run_command(
        command_root: Path,
        argv: tuple[str, ...],
        timeout: int,
    ) -> CommandEvidence:
        assert command_root == root
        assert timeout == 600
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {path.name for path in source_directory.iterdir()} == {
            "control.kicad_sch",
            "fault.kicad_sch",
            "low_resistance_control.kicad_sch",
            "low_resistance_fault.kicad_sch",
            "symbol_resistor.kicad_sch",
        }
        for case in observations:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} netlist {run}\n",
                    encoding="utf-8",
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path):
        case = path.name.split(".", 1)[0]
        return observations[case]

    def fake_selected_config(*_args: object) -> SimpleNamespace:
        return config

    monkeypatch.setattr(i2c_pullup_service, "selected_config", fake_selected_config)
    monkeypatch.setattr(i2c_pullup_service, "run_command", fake_run_command)
    monkeypatch.setattr(i2c_pullup_service, "read_netlist", fake_read_netlist)

    log = HostedLog(root, "i2c-pullup-native-lane-synthetic")
    i2c_pullup_native_fixture_lane(root, project="synthetic", image=image, log=log)

    results = {
        item["stage"]: item
        for item in map(json.loads, log.events.read_text(encoding="utf-8").splitlines())
        if item.get("stage", "").startswith("i2c-pullup-fixture/")
    }
    control_result = results["i2c-pullup-fixture/control"]
    fault_result = results["i2c-pullup-fixture/fault"]
    symbol_resistor_result = results["i2c-pullup-fixture/symbol-resistor"]
    assert control_result["baseline_missing_pullup"] == "OPEN"
    assert control_result["heuristic_coverage"] == "COMPLETE"
    assert control_result["heuristic_findings"] == "none"
    assert control_result["sda_tolerance_scope"] == "PASS"
    assert control_result["scl_tolerance_scope"] == "PASS"
    assert control_result["sda_capacitance_scope"] == "PASS"
    assert control_result["sda_capacitance_contributors"] == "X1"
    assert control_result["scl_capacitance_scope"] == "PASS"
    assert fault_result["baseline_missing_pullup"] == "OPEN"
    assert fault_result["heuristic_coverage"] == "OPEN"
    assert fault_result["heuristic_findings"] == "bus.i2c_missing_pullup"
    assert fault_result["sda_tolerance_scope"] == "PASS"
    assert fault_result["scl_tolerance_scope"] == "PASS"
    assert fault_result["sda_capacitance_scope"] == "FAIL"
    assert fault_result["sda_capacitance_contributors"] == "X1"
    assert fault_result["sda_capacitance_unmapped"] == "X2"
    assert fault_result["scl_capacitance_scope"] == "PASS"
    assert control_result["contract_path"] == "projects/synthetic-i2c-array/electrical.json"
    assert control_result["contract_sha256"] == fault_result["contract_sha256"]
    assert symbol_resistor_result["component_reference"] == "X1"
    assert symbol_resistor_result["component_symbol"] == "Device:R"
    assert symbol_resistor_result["component_pins"] == "1,2"
    assert symbol_resistor_result["pullup_path"] == "X1=4700Ω to +3V3"
    assert symbol_resistor_result["repeatable"] == "true"
    low_resistance_control = results["i2c-pullup-fixture/low_resistance_control"]
    low_resistance_fault = results["i2c-pullup-fixture/low_resistance_fault"]
    assert low_resistance_control["equivalent_ohms"] == "1000Ω"
    assert low_resistance_control["rule_findings"] == "none"
    assert low_resistance_fault["equivalent_ohms"] == "SDA=750Ω"
    assert low_resistance_fault["rule_findings"] == "bus.i2c_low_equivalent_resistance"
