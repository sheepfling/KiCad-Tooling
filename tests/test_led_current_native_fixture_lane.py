"""Pinned native source-to-netlist fixtures for mapped LED current windows."""

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
from tests.design_lint_fixtures.led_current import led_current_map
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "component.mapped_led_current_range_mismatch"
FIXTURES = MappingProxyType(
    {
        "control": "led-current-range/control.kicad_sch",
        "value-fault": "led-current-range/value-fault.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "a6be3691cf356ac8020d10341116d56a7cd9e36a6cb09b1c885c574d899ee17c",
        "value-fault": "ef95f66b22f00b3a23ab8db26a3a53c0f36d11dba1add141dc440449d0d1485f",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "value-fault": "D1: mapped LED current range",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_LED_CURRENT_RANGE_FIXTURES") != "1",
    reason="native LED current fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_led_current_envelope_fault_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        actual = hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
        assert actual == EXPECTED_SOURCE_HASHES[case]

    policy = DesignLintPolicy(
        led_current_map=led_current_map(
            resistor_outer_pin="R1.2",
            resistor_led_side_pin="R1.1",
        )
    )
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-led-current-range-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="led-current-range-fixture",
        project_id_prefix="synthetic-led-current-range",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "led-current-range-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "led-current-range-fixture/native-export",
        "led-current-range-fixture/control",
        "led-current-range-fixture/value-fault",
    }
    native = results["led-current-range-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    control = reports["control"]
    assert control.status == "PASS"
    control_run = next(item for item in control.mapped_check_runs if item.rule_id == RULE_ID)
    assert control_run.status == "EVALUATED"
    assert control_run.netlist_sha256 == control.netlist_sha256
    assert control_run.requirement_count == 1
    assert control_run.finding_count == 0

    fault = reports["value-fault"]
    assert fault.status == "REVIEW"
    finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
    assert finding.evidence["resistor_nominal_ohms"] == ("100",)
    assert finding.evidence["calculated_current_ma"] == ("10.4762–15.7895",)
    assert finding.evidence["netlist_sha256"] == (fault.netlist_sha256,)
    fault_run = next(item for item in fault.mapped_check_runs if item.rule_id == RULE_ID)
    assert fault_run.status == "EVALUATED"
    assert fault_run.finding_count == 1

    for case in FIXTURES:
        result = results[f"led-current-range-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
