"""Exact-version exports for mapped active regulator-support pin assignments."""

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
from tests.regulator_support_pin_net_support import support_pin_net_map
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_support_pin_net_mismatch"
FIXTURES = MappingProxyType(
    {
        "control": "regulator-support-pin-nets-native/control.kicad_sch",
        "wrong-net": "regulator-support-pin-nets-native/wrong-net.kicad_sch",
        "unconnected": "regulator-support-pin-nets-native/unconnected.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "364bd28f1d87a7da147934d2ce5977c7566362f976455355a340cf0c51a65672",
        "wrong-net": "329aea4ade3409a68cd6276eebaa17f0dd371eb9ae4012750eff3b4c751aa1f4",
        "unconnected": "db2be2b41afa070e2245aef43764f629aeb8a1b5fd41899a1d8915112a0eb8f4",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "wrong-net": "U2: mapped feedback isolator pin-to-net assignments differ",
        "unconnected": "U3: mapped secondary reference pin-to-net assignments differ",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_active_support_pin_net_fixture_sources_are_pinned() -> None:
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
    os.environ.get("KICAD_RUN_NATIVE_REGULATOR_SUPPORT_PIN_NET_FIXTURES") != "1",
    reason="native regulator-support pin-net fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_active_support_pin_net_faults_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )
    policy = DesignLintPolicy(regulator_support_pin_net_map=support_pin_net_map())
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-regulator-support-net-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-support-pin-net-fixture",
        project_id_prefix="synthetic-regulator-support-net",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native = next(
        event
        for event in events
        if event["stage"] == "regulator-support-pin-net-fixture/native-export"
        and event["status"] == "PASS"
    )
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])
    assert not any(item.rule_id == RULE_ID for item in reports["control"].findings)
    for case in ("wrong-net", "unconnected"):
        finding = next(item for item in reports[case].findings if item.rule_id == RULE_ID)
        assert finding.mode == "review"
        assert finding.subject == EXPECTED_SUBJECTS[case]
