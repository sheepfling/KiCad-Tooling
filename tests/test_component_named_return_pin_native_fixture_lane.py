"""Focused native acceptance for named component return-pin lint."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_named_return_pin import COMPONENT_NAMED_RETURN_PIN_CASES
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.component_power_pin_native_support import (
    assert_mocked_component_power_pin_lane,
    component_power_pin_lane_results,
)
from tests.design_lint_fixtures.named_component_power_pins import named_component_return_pin_cases
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
]


def test_component_named_return_pin_lane_exports_only_its_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_named_return_pin_lane import (
        component_named_return_pin_fixture_lane,
    )

    assert_mocked_component_power_pin_lane(
        tmp_path,
        monkeypatch,
        lane=component_named_return_pin_fixture_lane,
        cases=COMPONENT_NAMED_RETURN_PIN_CASES,
        observed_contracts=named_component_return_pin_cases(),
        stage_prefix="component-named-return-pin-fixture",
        fault_case="unconnected-named-component-return-fault",
        expected_rule_id="component.unconnected_return_pin",
        expected_subject="U1.2: GND",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.unconnected_return_pin")
@pytest.mark.design_lint_rule(rule_id="component.repeated_return_pin_function")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_NAMED_RETURN_PIN_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_named_component_return_pin_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_named_return_pin_lane import (
        component_named_return_pin_fixture_lane,
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

    log = HostedLog(root, f"native-component-named-return-pin-{project}")
    component_named_return_pin_fixture_lane(root, project=project, image=config.image, log=log)
    results = component_power_pin_lane_results(
        log, stage_prefix="component-named-return-pin-fixture"
    )
    native_export = results["component-named-return-pin-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == COMPONENT_NAMED_RETURN_PIN_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    for case, expected_status, expected_findings in (
        (
            "unconnected-named-component-return-fault",
            "REVIEW",
            "component.unconnected_return_pin",
        ),
        ("unconnected-named-component-power-control", "PASS", "none"),
        (
            "split-named-component-return-fault",
            "REVIEW",
            "component.repeated_return_pin_function",
        ),
        ("common-named-component-return-control", "PASS", "none"),
    ):
        result = results[f"component-named-return-pin-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == expected_status
        assert result["findings"] == expected_findings
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
