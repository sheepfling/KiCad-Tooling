"""Exact-version native exports for two-contact RS-485 return review."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config

RULE_ID = "connector.rs485_pair_without_return_review"
PROJECTS = ("controller", "raspberry-pi-status-led")

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_RS485_CONNECTOR_RETURN_FIXTURES") != "1",
    reason="native RS-485 connector return fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("project", PROJECTS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_two_pin_rs485_return_fault_and_named_control(
    hosted_reference_root: Path, project: str
) -> None:
    from kicad_tooling.ci_hosted_rs485_connector_return_lane import (
        rs485_connector_return_fixture_lane,
    )

    root = hosted_reference_root
    config = selected_config(root, project)
    assert config.kicad_version in {"10.0.0", "10.0.5"}
    log = HostedLog(root, f"native-rs485-connector-return-{project}")
    rs485_connector_return_fixture_lane(
        root,
        project=project,
        image=config.image,
        log=log,
    )
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("generic-connector/rs485-return/")
    }

    assert set(results) == {
        "generic-connector/rs485-return/fault",
        "generic-connector/rs485-return/control",
    }
    assert results["generic-connector/rs485-return/fault"]["finding_count"] == 1
    assert results["generic-connector/rs485-return/control"]["finding_count"] == 0
    for result in results.values():
        assert result["status"] == "PASS"
        assert result["kicad_version"] == config.kicad_version
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
