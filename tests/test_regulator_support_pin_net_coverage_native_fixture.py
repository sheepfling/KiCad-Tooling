"""Digest-pinned native fixtures for active support pin-map coverage."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_component_lint import component_lint_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)
from tests.test_regulator_support_pin_roles import support_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_support_pin_net_map_coverage_missing"
FIXTURES = MappingProxyType({"control": "regulator-support-pin-nets-native/control.kicad_sch"})
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {"control": "364bd28f1d87a7da147934d2ce5977c7566362f976455355a340cf0c51a65672"}
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": (
            "U2: active support pin-to-net map coverage is missing",
            "U3: active support pin-to-net map coverage is missing",
        )
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_REGULATOR_SUPPORT_PIN_NET_COVERAGE_FIXTURES") != "1",
    reason="native support pin-net coverage fixture runs in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_active_support_pin_net_coverage_is_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )
    policy = DesignLintPolicy(regulator_support_pin_role_map=support_map())
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-regulator-support-net-coverage-{version}")
    component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-support-pin-net-coverage-fixture",
        project_id_prefix="synthetic-regulator-support-net-coverage",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native = next(
        event
        for event in events
        if event["stage"] == "regulator-support-pin-net-coverage-fixture/native-export"
        and event["status"] == "PASS"
    )

    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == f"control:{EXPECTED_SOURCE_HASHES['control']}"
