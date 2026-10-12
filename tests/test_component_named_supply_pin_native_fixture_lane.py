"""Focused native acceptance for named component supply-pin lint."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_named_supply_pin import COMPONENT_NAMED_SUPPLY_PIN_CASES
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.component_power_pin_native_support import (
    assert_mocked_component_power_pin_lane,
    component_power_pin_lane_results,
)
from tests.design_lint_fixtures.named_component_power_pins import named_component_supply_pin_cases
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_component_named_supply_pin_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_named_supply_pin_lane import (
        component_named_supply_pin_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=component_named_supply_pin_fixture_lane,
        cases=COMPONENT_NAMED_SUPPLY_PIN_CASES,
        observed_contracts=named_component_supply_pin_cases(),
        stage_prefix="component-named-supply-pin-fixture",
        fault_case="unconnected-named-component-supply-fault",
        expected_rule_id="component.unconnected_supply_pin",
        expected_subject="U1.1: VDD",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_NAMED_SUPPLY_PIN_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_named_component_supply_pin_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_named_supply_pin_lane import (
        component_named_supply_pin_fixture_lane,
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

    log = HostedLog(root, f"native-component-named-supply-pin-{project}")
    component_named_supply_pin_fixture_lane(root, project=project, image=config.image, log=log)
    results = component_power_pin_lane_results(
        log, stage_prefix="component-named-supply-pin-fixture"
    )
    native_export = results["component-named-supply-pin-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == COMPONENT_NAMED_SUPPLY_PIN_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    for case, expected_status, expected_findings in (
        (
            "unconnected-named-component-supply-fault",
            "REVIEW",
            "component.unconnected_supply_pin",
        ),
        ("unconnected-named-component-power-control", "PASS", "none"),
    ):
        result = results[f"component-named-supply-pin-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == expected_status
        assert result["findings"] == expected_findings
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
