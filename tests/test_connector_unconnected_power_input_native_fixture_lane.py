"""Focused exact-version native regressions for generic connector power inputs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, connector_unconnected_power_input_fixture_lane
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.unconnected_power_input"


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="pinned connector native fixtures run in package acceptance",
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_power_input_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    project = f"connector-power-input-{version.replace('.', '-')}"
    root, _ = synthetic_design_lint_project(
        tmp_path / project,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-connector-power-input-{version}")

    connector_unconnected_power_input_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
    )

    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("connector-power-input-fixture/")
    }
    assert set(results) == {
        "connector-power-input-fixture/native-export",
        "connector-power-input-fixture/unconnected-generic-power-input-fault",
        "connector-power-input-fixture/unconnected-generic-power-input-control",
    }
    native_export = results["connector-power-input-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert native_export["image"] == image

    fault = results["connector-power-input-fixture/unconnected-generic-power-input-fault"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"].split(",") == [RULE_ID, RULE_ID]
    assert set(fault["subjects"].split(";")) == {
        "J1.1: generic native power-input pin is unassigned",
        "J2.1: generic native power-input pin is unassigned",
    }
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]

    control = results["connector-power-input-fixture/unconnected-generic-power-input-control"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
