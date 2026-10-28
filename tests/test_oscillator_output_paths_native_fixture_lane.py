"""Exact-version native exports for the authored oscillator path rule."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures.oscillator_output_path_native import CASES, render_case
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)
from tests.test_oscillator_output_paths import oscillator_output_path_map

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "oscillator.output_load_path_mismatch"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "design_lint" / "oscillator-output-native"
SOURCE_SHA256 = MappingProxyType(
    {
        "series-boundary-control.kicad_sch": "4fadcabb12a2bbedc396e707abf0bf1247df3a921674b5236cc993c9d54445b9",
        "wrong-value-fault.kicad_sch": "9225ef72ca1e7922003672085bc69531a33f67b0acc1acbde2b9554d350239d8",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_fixture_sources_match_their_generator() -> None:
    assert set(CASES) == {"series-boundary-control", "wrong-value-fault"}
    assert {path.name for path in FIXTURE_ROOT.glob("*.kicad_sch")} == set(SOURCE_SHA256)
    for filename, expected_sha256 in SOURCE_SHA256.items():
        source = FIXTURE_ROOT / filename
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_sha256
        case_name = source.stem
        expected_value = CASES[case_name]
        assert content.decode("utf-8") == render_case(case_name, expected_value)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_OSCILLATOR_OUTPUT_PATH_FIXTURES") != "1",
    reason="oscillator path exports run in the digest-pinned native acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_oscillator_output_path_fault_and_control_are_version_pinned_and_repeatable(
    tmp_path: Path, version: str
) -> None:
    from kicad_tooling.ci_hosted_oscillator_output_path_fixtures import (
        oscillator_output_path_fixture_lane,
    )

    project = "oscillator-output-native"
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _summary = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(oscillator_output_path_map=oscillator_output_path_map()),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-oscillator-output-path-{version}")
    oscillator_output_path_fixture_lane(root, project=project, image=config.image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("oscillator-output-path-fixture/")
    }
    assert set(results) == {
        "oscillator-output-path-fixture/native-export",
        "oscillator-output-path-fixture/series-boundary-control",
        "oscillator-output-path-fixture/wrong-value-fault",
    }
    export = results["oscillator-output-path-fixture/native-export"]
    assert export["status"] == "PASS"
    assert export["kicad_version"] == version
    assert export["repeatable"] == "true"
    assert_native_fixture_mounts(root, export["command_receipt"])

    control = results["oscillator-output-path-fixture/series-boundary-control"]
    assert control["lint_status"] == "PASS"
    assert control["issues"] == "none"
    fault = results["oscillator-output-path-fixture/wrong-value-fault"]
    assert fault["lint_status"] == "REVIEW"
    assert "nominal resistance is 1000 ohms" in fault["issues"]
