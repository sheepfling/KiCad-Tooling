"""Native evidence for all-open named component power-input peers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_peer_power_input import (
    NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.component_peer_power_input_support import named_peer_power_input_netlist
from tests.component_power_pin_native_support import (
    assert_mocked_component_power_pin_lane,
    component_power_pin_lane_results,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_named_peer_power_input_all_open_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/named-peer-power-input-all-open"
    )
    expected = {
        "fault.kicad_sch": "07868167a3fcbe4a8e06a8f7fda29dbc73138808ada53e805db6cab4aa8909fc",
        "control.kicad_sch": "437224399056a521542a4ff556900b696250f3ad6d8fd6f7d66f24227c20d136",
    }

    assert {
        filename: hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def test_named_component_peer_power_input_all_open_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        named_component_peer_power_input_all_open_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=named_component_peer_power_input_all_open_fixture_lane,
        cases=NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES,
        observed_contracts={
            NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES[0]: named_peer_power_input_netlist(
                assignments=(None, None)
            ),
            NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES[1]: named_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
        },
        stage_prefix="named-component-peer-power-input-all-open-fixture",
        fault_case=NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES[0],
        expected_rule_id="component.peer_power_input_named_all_open",
        expected_subject=(
            "Lint:NamedPeerPowerInput pin 1 (BIAS_IN): "
            "named power-input peer pin is open on every fitted peer"
        ),
        expected_control_status="REVIEW",
        expected_control_findings="power.ic_rail_without_fitted_capacitor",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_named_peer_power_input_all_open_fault_and_control_are_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        named_component_peer_power_input_all_open_fixture_lane,
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

    log = HostedLog(root, f"native-named-peer-power-input-all-open-{project}")
    named_component_peer_power_input_all_open_fixture_lane(
        root, project=project, image=config.image, log=log
    )
    results = component_power_pin_lane_results(
        log, stage_prefix="named-component-peer-power-input-all-open-fixture"
    )
    native_export = results["named-component-peer-power-input-all-open-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[
        "named-component-peer-power-input-all-open-fixture/"
        f"{NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES[0]}"
    ]
    control = results[
        "named-component-peer-power-input-all-open-fixture/"
        f"{NAMED_COMPONENT_PEER_POWER_INPUT_ALL_OPEN_CASES[1]}"
    ]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "component.peer_power_input_named_all_open" in fault["findings"].split(",")
    assert control["lint_status"] == "REVIEW"
    assert "component.peer_power_input_named_all_open" not in control["findings"].split(",")
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
