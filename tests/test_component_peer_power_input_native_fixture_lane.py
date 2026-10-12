"""Focused native acceptance for generic peer power-input assignment lint."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_peer_power_input import (
    COMPONENT_PEER_POWER_INPUT_CASES,
    NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.component_peer_power_input_support import (
    generic_peer_power_input_netlist,
    named_peer_power_input_netlist,
)
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


def test_generic_peer_power_input_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/generic-peer-power-input-assignment"
    )
    expected = {
        "fault.kicad_sch": "594736519e5c2e3bde88af27d9f059749060014a71f6447aeeceeb8767e7bdae",
        "control.kicad_sch": "9242ac4bf9c466ea0e5a4b41a616c6de881283fdac697ef3e55618040ea6746d",
    }

    assert {
        filename: hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def test_named_peer_power_input_open_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/named-peer-power-input-open"
    )
    expected = {
        "fault.kicad_sch": "bbf389425f8f86e1375c6265768a38d1a52c54efd4b80b4c849fd5593cdc0d13",
        "control.kicad_sch": "ce5553c0a40d57bcc5719089d607ddec91398e20155cbe3cb2edae2d2ee49ed3",
    }

    assert {
        filename: hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def test_component_peer_power_input_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        component_peer_power_input_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=component_peer_power_input_fixture_lane,
        cases=COMPONENT_PEER_POWER_INPUT_CASES,
        observed_contracts={
            "peer-generic-power-input-fault": generic_peer_power_input_netlist(),
            "peer-generic-power-input-control": generic_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
        },
        stage_prefix="component-peer-power-input-fixture",
        fault_case="peer-generic-power-input-fault",
        expected_rule_id="component.peer_power_input_assignment_divergence",
        expected_subject=(
            "Lint:GenericPowerInputPeer pin 1: generic peer power-input assignments differ"
        ),
        expected_control_status="REVIEW",
        expected_control_findings="power.ic_rail_without_fitted_capacitor",
    )


def test_named_component_peer_power_input_open_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        named_component_peer_power_input_open_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=named_component_peer_power_input_open_fixture_lane,
        cases=NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES,
        observed_contracts={
            "peer-named-power-input-open-fault": named_peer_power_input_netlist(),
            "peer-named-power-input-open-control": named_peer_power_input_netlist(
                assignments=("+3V3", "+3V3")
            ),
        },
        stage_prefix="named-component-peer-power-input-open-fixture",
        fault_case="peer-named-power-input-open-fault",
        expected_rule_id="component.peer_power_input_open_assignment",
        expected_subject=(
            "Lint:NamedPeerPowerInput pin 1 (BIAS_IN): power-input peer assignment is open"
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
def test_native_generic_peer_power_input_fault_and_control_are_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        component_peer_power_input_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

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

    log = HostedLog(root, f"native-component-peer-power-input-{project}")
    component_peer_power_input_fixture_lane(root, project=project, image=config.image, log=log)
    results = component_power_pin_lane_results(
        log, stage_prefix="component-peer-power-input-fixture"
    )
    native_export = results["component-peer-power-input-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == COMPONENT_PEER_POWER_INPUT_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[f"component-peer-power-input-fixture/{COMPONENT_PEER_POWER_INPUT_CASES[0]}"]
    control = results[f"component-peer-power-input-fixture/{COMPONENT_PEER_POWER_INPUT_CASES[1]}"]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "component.peer_power_input_assignment_divergence" in fault["findings"].split(",")
    assert control["lint_status"] == "REVIEW"
    assert "component.peer_power_input_assignment_divergence" not in control["findings"].split(",")
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


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
def test_native_named_peer_power_input_open_fault_and_control_are_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_peer_power_input_lane import (
        named_component_peer_power_input_open_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

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

    log = HostedLog(root, f"native-named-peer-power-input-open-{project}")
    named_component_peer_power_input_open_fixture_lane(
        root, project=project, image=config.image, log=log
    )
    results = component_power_pin_lane_results(
        log, stage_prefix="named-component-peer-power-input-open-fixture"
    )
    native_export = results["named-component-peer-power-input-open-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[
        f"named-component-peer-power-input-open-fixture/{NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES[0]}"
    ]
    control = results[
        f"named-component-peer-power-input-open-fixture/{NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES[1]}"
    ]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "component.peer_power_input_open_assignment" in fault["findings"].split(",")
    assert control["lint_status"] == "REVIEW"
    assert "component.peer_power_input_open_assignment" not in control["findings"].split(",")
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
