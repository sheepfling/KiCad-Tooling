"""Exact-version native regressions for mapped regulator pin roles."""

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
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)
from tests.test_regulator_passive_pin_roles import RULE_ID
from tests.test_regulator_required_passives import RULE_ID as TOPOLOGY_RULE_ID
from tests.test_regulator_required_passives import topology_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

FIXTURES = MappingProxyType(
    {
        "control": "regulator-required-passive-native/control.kicad_sch",
        "wrong-function": "regulator-required-passive-native/wrong-pin-function.kicad_sch",
        "wrong-type": "regulator-required-passive-native/wrong-pin-type.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "10ac24d66c489a3258d3827d571cb2ab826ee76ef5a97070a1e9a87274854c7f",
        "wrong-function": "caeb900e8af806cb9cf32564fb7752e64e5428b4bdc72c5d7d78438e5cc9d2fc",
        "wrong-type": "47d45af1094e3f8d2c20cdd71f65c918d325eb280e00660e05c336d4ea46f516",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "wrong-function": "U1: mapped pin roles differ",
        "wrong-type": "U1: mapped pin roles differ",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_regulator_pin_role_fixture_sources_are_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_REGULATOR_REQUIRED_PASSIVE_FIXTURES") != "1",
    reason="native regulator topology fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_regulator_pin_role_faults_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )
    policy = DesignLintPolicy(regulator_passive_topology_map=topology_map())
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-regulator-pin-roles-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-pin-role-fixture",
        project_id_prefix="synthetic-regulator-pin-role",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    native = next(
        event
        for event in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if event["stage"] == "regulator-pin-role-fixture/native-export"
        and event["status"] == "PASS"
    )
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])
    assert not any(item.rule_id == RULE_ID for item in reports["control"].findings)
    for case in ("wrong-function", "wrong-type"):
        finding = next(item for item in reports[case].findings if item.rule_id == RULE_ID)
        assert finding.mode == "review"
        assert not any(item.rule_id == TOPOLOGY_RULE_ID for item in reports[case].findings)
