"""Exact-version native evidence for mapped regulator-feedback lint."""

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
from tests.test_regulator_feedback import regulator_feedback_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_feedback_mismatch"
FIXTURES = MappingProxyType(
    {
        "control": "regulator-feedback-native/control.kicad_sch",
        "value-fault": "regulator-feedback-native/value-fault.kicad_sch",
        "split-feedback-fault": "regulator-feedback-native/split-feedback-fault.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "7b0f89c28b607ed9b22bb3757976eb3ddd882c6a543ce093c4557232ffb68e63",
        "value-fault": "4f032ee18da29f42232ba3bf7ba2b033f6e1e66fced8629599047ae6d114f7f9",
        "split-feedback-fault": "2f9c3e020f095891745edd137fed1691432fefcd7d43168585e3507a62b30f36",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "value-fault": "U1: mapped feedback divider",
        "split-feedback-fault": "U1: mapped feedback divider",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_regulator_feedback_fixture_sources_are_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    assert set(FIXTURES) == set(EXPECTED_SOURCE_HASHES)
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_REGULATOR_FEEDBACK_FIXTURES") != "1",
    reason="native regulator-feedback fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_regulator_feedback_faults_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )

    policy = DesignLintPolicy(regulator_feedback_map=regulator_feedback_map())
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-regulator-feedback-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="regulator-feedback-fixture",
        project_id_prefix="synthetic-regulator-feedback",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "regulator-feedback-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "regulator-feedback-fixture/native-export",
        "regulator-feedback-fixture/control",
        "regulator-feedback-fixture/value-fault",
        "regulator-feedback-fixture/split-feedback-fault",
    }
    native = results["regulator-feedback-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    control_coverage = reports["control"].regulator_feedback_coverage
    assert control_coverage.status == "COMPLETE"
    assert control_coverage.netlist_sha256 == reports["control"].netlist_sha256
    control_entry = control_coverage.entries[0]
    assert control_entry.status == "COMPLETE"
    assert control_entry.pin_nets == {
        "U1.1": ("REG_OUT",),
        "U1.2": ("FB",),
        "R1.1": ("REG_OUT",),
        "R1.2": ("FB",),
        "R2.1": ("FB",),
        "R2.2": ("GND",),
    }
    assert control_entry.nominal_resistance_ohms == {"R1": 180000.0, "R2": 33000.0}

    value_coverage = reports["value-fault"].regulator_feedback_coverage
    assert value_coverage.status == "COMPLETE"
    value_entry = value_coverage.entries[0]
    assert value_entry.status == "OUT_OF_RANGE"
    assert value_entry.nominal_resistance_ohms == {"R1": 220000.0, "R2": 33000.0}
    assert (value_entry.calculated_output_minimum_v or 0) > value_entry.target_output_maximum_v

    split_coverage = reports["split-feedback-fault"].regulator_feedback_coverage
    assert split_coverage.status == "INCOMPLETE"
    split_entry = split_coverage.entries[0]
    assert split_entry.status == "INCOMPLETE"
    assert split_entry.pin_nets["R2.1"] == ("FB2",)

    for case in FIXTURES:
        result = results[f"regulator-feedback-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
