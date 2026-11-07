"""Exact-version native exports for generic connector SWD pair review."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config

RULE_ID = "bus.swd_generic_connector_pair_review"
PROJECT_TOOLCHAINS = (
    pytest.param(
        "controller",
        "10.0.0",
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        id="controller-kicad-10.0.0",
    ),
    pytest.param(
        "raspberry-pi-status-led",
        "10.0.5",
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        id="raspberry-pi-status-led-kicad-10.0.5",
    ),
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SWD_GENERIC_CONNECTOR_FIXTURES") != "1",
    reason="native SWD generic-connector fixtures run in the digest-pinned interface lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_generic_swd_connector_fault_and_control_repeat(
    hosted_reference_root: Path,
    project: str,
    version: str,
    image: str,
) -> None:
    from kicad_tooling.ci_hosted_swd_generic_connector import swd_generic_connector_fixture_lane

    root = hosted_reference_root
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-swd-generic-connector-{project}")
    swd_generic_connector_fixture_lane(root, project=project, image=config.image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("generic-connector/swd/")
    }

    assert set(results) == {"generic-connector/swd/fault", "generic-connector/swd/control"}
    assert results["generic-connector/swd/fault"]["finding_count"] == 1
    assert results["generic-connector/swd/control"]["finding_count"] == 0
    for result in results.values():
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
