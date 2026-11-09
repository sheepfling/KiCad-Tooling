"""Exact-version native exports for active regulator-support role maps."""

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
from tests.test_regulator_support_pin_roles import RULE_ID, support_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

FIXTURES = MappingProxyType(
    {
        "control": "regulator-support-pin-roles-native/control.kicad_sch",
        "wrong-function": "regulator-support-pin-roles-native/wrong-optocoupler-function.kicad_sch",
        "wrong-type": "regulator-support-pin-roles-native/wrong-reference-type.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "5f42a353ccbb057567ac02d6027a0d37315d8a289ed9895bb040c9cdd9017146",
        "wrong-function": "78313d4d31c25d47771fd75e8cb17b54c811dd7aa810222b6d384d8f8acdfad9",
        "wrong-type": "addf7b75c257a6c7f90e08a9ecbae09a0c7ef8a5a96f16089488b8b18e3231e1",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "wrong-function": "U2: mapped feedback isolator pin roles differ",
        "wrong-type": "U3: mapped secondary reference pin roles differ",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_active_support_pin_role_fixture_sources_are_pinned() -> None:
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
    os.environ.get("KICAD_RUN_NATIVE_REGULATOR_SUPPORT_PIN_ROLE_FIXTURES") != "1",
    reason="native regulator-support role fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_active_support_pin_role_faults_and_control_are_source_bound(
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
    log = HostedLog(root, f"native-regulator-support-role-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-support-role-fixture",
        project_id_prefix="synthetic-regulator-support-role",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native = next(
        event
        for event in events
        if event["stage"] == "regulator-support-role-fixture/native-export"
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
        assert finding.subject == EXPECTED_SUBJECTS[case]
