"""Exact-version source export coverage for same-voltage IC supply inputs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from kicad_tooling.ci_hosted_component_same_voltage_power_inputs import (
    RULE_ID,
    SAME_VOLTAGE_POWER_INPUT_CASES,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.component_power_pin_native_support import (
    assert_mocked_component_power_pin_lane,
    component_power_pin_lane_results,
)
from tests.design_lint_fixtures.same_voltage_power_inputs import (
    same_voltage_power_input_netlist,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def _observed_cases() -> dict[str, NetlistContract]:
    return {
        SAME_VOLTAGE_POWER_INPUT_CASES[0]: same_voltage_power_input_netlist(),
        SAME_VOLTAGE_POWER_INPUT_CASES[1]: same_voltage_power_input_netlist(
            nets={"+3V3": ("U1.1", "U1.2")}
        ),
    }


def test_same_voltage_power_input_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_same_voltage_power_inputs_lane import (
        same_voltage_power_input_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=same_voltage_power_input_fixture_lane,
        cases=SAME_VOLTAGE_POWER_INPUT_CASES,
        observed_contracts=_observed_cases(),
        stage_prefix="same-voltage-power-input-fixture",
        fault_case=SAME_VOLTAGE_POWER_INPUT_CASES[0],
        expected_rule_id=RULE_ID,
        expected_subject=(
            "U1 (Lint:MultiSupplyIC): distinct supply inputs on separate 3.3 V-labeled nets"
        ),
        expected_control_status="REVIEW",
        expected_control_findings="power.ic_rail_without_fitted_capacitor",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_SAME_VOLTAGE_POWER_INPUT_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    "project,version", (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_same_voltage_power_input_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_same_voltage_power_inputs_lane import (
        same_voltage_power_input_fixture_lane,
    )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-same-voltage-power-input-{project}")
    same_voltage_power_input_fixture_lane(root, project=project, image=config.image, log=log)
    results = component_power_pin_lane_results(log, stage_prefix="same-voltage-power-input-fixture")
    native_export = results["same-voltage-power-input-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    source_hashes = cast(str, native_export["source_hashes"])
    assert tuple(source_hash.split(":", 1)[0] for source_hash in source_hashes.split(",")) == (
        SAME_VOLTAGE_POWER_INPUT_CASES
    )
    assert_native_fixture_mounts(root, cast(str, native_export["command_receipt"]))

    fault = results[f"same-voltage-power-input-fixture/{SAME_VOLTAGE_POWER_INPUT_CASES[0]}"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert RULE_ID in cast(str, fault["findings"]).split(",")
    assert fault["kicad_version"] == version
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]

    control = results[f"same-voltage-power-input-fixture/{SAME_VOLTAGE_POWER_INPUT_CASES[1]}"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "REVIEW"
    assert RULE_ID not in cast(str, control["findings"]).split(",")
    assert control["kicad_version"] == version
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
