"""Exact-version native regression fixtures for return/signal net sharing."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, connector_return_signal_net_fixture_lane
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.return_pin_shares_protocol_signal_net"


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="pinned connector native fixtures run in package acceptance",
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_return_signal_shared_net_fault_and_control_are_repeatable(
    tmp_path: Path,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    project = f"connector-return-signal-{version.replace('.', '-')}"
    root, _ = synthetic_design_lint_project(
        tmp_path / project,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-connector-return-signal-{version}")
    connector_return_signal_net_fixture_lane(root, project=project, image=image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("connector-return-signal-fixture/")
    }
    assert set(results) == {
        "connector-return-signal-fixture/native-export",
        "connector-return-signal-fixture/fault",
        "connector-return-signal-fixture/control",
    }
    assert results["connector-return-signal-fixture/native-export"]["status"] == "PASS"
    for case, status, count in (("fault", "REVIEW", 1), ("control", "PASS", 0)):
        result = results[f"connector-return-signal-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["lint_status"] == status
        assert result["finding_count"] == count
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
