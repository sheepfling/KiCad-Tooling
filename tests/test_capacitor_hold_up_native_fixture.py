"""Exact-version native exports for the mapped hold-up screen."""

from __future__ import annotations

import hashlib
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
from tests.test_capacitor_hold_up import RULE_ID, hold_up_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

FIXTURES = MappingProxyType(
    {
        "control": "capacitor-hold-up-native/control.kicad_sch",
        "below-minimum": "capacitor-hold-up-native/below-minimum.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "1b845d0d869a300c8bb5ba2ebd703b1df767d6355b70c66fb928b2d5bfbac1db",
        "below-minimum": "7dacdde5769904e4f0e0912f734ed55983c9afafdb3e51b5d1bcb582ac1da283",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "below-minimum": "backup-rail: C1 hold-up review",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_capacitor_hold_up_fixture_sources_are_pinned() -> None:
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
    os.environ.get("KICAD_RUN_NATIVE_CAPACITOR_HOLD_UP_FIXTURES") != "1",
    reason="native hold-up fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_capacitor_hold_up_faults_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )
    policy = DesignLintPolicy(capacitor_hold_up_map=hold_up_map(minimum_ms=2000.0))
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="storage",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-capacitor-hold-up-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="storage",
        image=image,
        log=log,
        fixture_prefix="capacitor-hold-up-fixture",
        project_id_prefix="synthetic-capacitor-hold-up",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    assert tuple(item.rule_id for item in reports["below-minimum"].findings) == (RULE_ID,)
