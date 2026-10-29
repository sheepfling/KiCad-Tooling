"""Exact-version native export tests for regulator required-passive maps."""

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
from tests.test_regulator_required_passives import RULE_ID, topology_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

FIXTURES = MappingProxyType(
    {
        "control": "regulator-required-passive-native/control.kicad_sch",
        "missing-passive": "regulator-required-passive-native/missing-passive.kicad_sch",
        "wrong-net": "regulator-required-passive-native/wrong-net.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "10ac24d66c489a3258d3827d571cb2ab826ee76ef5a97070a1e9a87274854c7f",
        "missing-passive": "920b189071c13b2fcbf0dc31137d908c9bf38caadef495efea1ef2b0fd6e9a5b",
        "wrong-net": "0468d7a5b636346e0f56e656ece602cce87200f5a07daa7b3b5ebe93445466ea",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "missing-passive": "U1: required passive topology differs",
        "wrong-net": "U1: required passive topology differs",
    }
)
NATIVE_FIXTURE_ENV = "KICAD_RUN_NATIVE_REGULATOR_REQUIRED_PASSIVE_FIXTURES"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_regulator_passive_fixture_sources_are_pinned() -> None:
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
    os.environ.get(NATIVE_FIXTURE_ENV) != "1",
    reason="native regulator passive fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_regulator_passive_topology_faults_and_control_are_source_bound(
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
    log = HostedLog(root, f"native-regulator-passive-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-required-passive-fixture",
        project_id_prefix="synthetic-regulator-required-passive",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native = next(
        event
        for event in events
        if event["stage"] == "regulator-required-passive-fixture/native-export"
        and event["status"] == "PASS"
    )
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])
    assert not any(item.rule_id == RULE_ID for item in reports["control"].findings)
    for case in ("missing-passive", "wrong-net"):
        finding = next(item for item in reports[case].findings if item.rule_id == RULE_ID)
        assert finding.mode == "review"
        assert reports[case].netlist_sha256
