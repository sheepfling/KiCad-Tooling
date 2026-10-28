"""Exact-version native schematic evidence for polarized-capacitor polarity lint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_polarized_capacitor import (
    POLARIZED_CAPACITOR_FIXTURE_CASES,
    polarized_capacitor_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.component_polarized_capacitor_orientation import RULE_ID
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures.polarized_capacitor import NATIVE_FIXTURE_SHA256
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES") != "1",
    reason="native component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_polarized_capacitor_fault_and_control_are_deterministic(
    tmp_path: Path,
    version: str,
) -> None:

    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    actual_paths = {
        case: relative
        for case, relative in POLARIZED_CAPACITOR_FIXTURE_CASES.items()
        if (fixture_root / relative).is_file()
    }
    assert actual_paths == {
        "fault": "polarized-capacitor-native/fault.kicad_sch",
        "control": "polarized-capacitor-native/control.kicad_sch",
    }
    assert NATIVE_FIXTURE_SHA256.keys() == actual_paths.keys()
    for case, relative in actual_paths.items():
        source = fixture_root / relative
        assert hashlib.sha256(source.read_bytes()).hexdigest() == NATIVE_FIXTURE_SHA256[case]

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, "controller")
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-polarized-capacitor-{version}")
    polarized_capacitor_fixture_lane(root, project="controller", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "polarized-capacitor-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "polarized-capacitor-fixture/native-export",
        "polarized-capacitor-fixture/fault",
        "polarized-capacitor-fixture/control",
    }
    native = results["polarized-capacitor-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{NATIVE_FIXTURE_SHA256[case]}" for case in POLARIZED_CAPACITOR_FIXTURE_CASES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    fault = results["polarized-capacitor-fixture/fault"]
    control = results["polarized-capacitor-fixture/control"]
    assert fault["rule_findings"] == "C1: polarized capacitor pin 1 is below pin 2"
    assert control["rule_findings"] == "none"
    for case, result in (("fault", fault), ("control", control)):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == NATIVE_FIXTURE_SHA256[case]
        assert result["repeatable"] == "true"
        assert result["erc_errors"] == "none"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
