"""Exact-version native connector named power-input alias regressions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_named_power_input import (
    ALL_OPEN_RULE_ID,
    CASES,
    RULE_ID,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]


def test_named_connector_power_input_alias_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-named-power-input-peer-native"
    )
    expected = {
        "fault.kicad_sch": "48eae0285f76c61668dbe58e33ee00bf9480a3064f5a45c2e122b12d2f91ec7c",
        "control.kicad_sch": "401fda583c25519540d427b1e24e320e5843c3aab5e99407378497e7dc475717",
        "all-open-fault.kicad_sch": "b17443d0e3db891ca9946f032561dabe57d29e17bd9396668b0398a70ac2fdeb",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    } == expected


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_connector_named_power_input_alias_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_input_lane import (
        connector_named_power_input_fixture_lane,
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

    log = HostedLog(root, f"native-connector-named-power-input-{project}")
    connector_named_power_input_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-named-power-input-alias-fixture/"
    results = {
        item["stage"].removeprefix(prefix): item
        for item in events
        if item.get("stage", "").startswith(prefix)
    }
    assert set(results) == {"native-export", *CASES}
    native_export = results["native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[CASES[0]]
    control = results[CASES[1]]
    all_open = results[CASES[2]]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert RULE_ID in fault["findings"].split(",")
    assert control["lint_status"] in {"PASS", "REVIEW"}
    assert RULE_ID not in control["findings"].split(",")
    assert ALL_OPEN_RULE_ID not in control["findings"].split(",")
    assert all_open["status"] == "PASS"
    assert all_open["lint_status"] == "REVIEW"
    assert ALL_OPEN_RULE_ID in all_open["findings"].split(",")
    assert RULE_ID not in all_open["findings"].split(",")
    for result in (fault, control, all_open):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
