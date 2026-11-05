"""Pinned native evidence for the mapped signal-divider check."""

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
from tests.design_lint_fixtures.signal_divider import signal_divider_map
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "interface.signal_divider_input_range_mismatch"
FIXTURES = MappingProxyType(
    {
        "control": "signal-divider-native/control.kicad_sch",
        "value-fault": "signal-divider-native/value-fault.kicad_sch",
        "split-tap-fault": "signal-divider-native/split-tap-fault.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "control": "d3d6187c851d42f8df539f2d31e285a6e134bb1207b1adf87d69e4efe7000202",
        "value-fault": "927bd13fd05e173f6e2d2e11550a1abe0eec25ec551cbc21669079c9b209e1ff",
        "split-tap-fault": "ef0e1dab588b49abaf79eaa4ca6614869c01ba2079c231e93fd0c7ea7e3d7f61",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "control": None,
        "value-fault": "U1: mapped signal-input divider",
        "split-tap-fault": "U1: mapped signal-input divider",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SIGNAL_DIVIDER_FIXTURES") != "1",
    reason="native signal-divider fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_signal_divider_faults_and_control_are_source_bound(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest() == (
            EXPECTED_SOURCE_HASHES[case]
        )

    policy = DesignLintPolicy(signal_divider_map=signal_divider_map())
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-signal-divider-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="signal-divider-fixture",
        project_id_prefix="synthetic-signal-divider",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "signal-divider-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "signal-divider-fixture/native-export",
        "signal-divider-fixture/control",
        "signal-divider-fixture/value-fault",
        "signal-divider-fixture/split-tap-fault",
    }
    native = results["signal-divider-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    control = reports["control"].signal_divider_coverage
    assert control.status == "COMPLETE"
    assert control.netlist_sha256 == reports["control"].netlist_sha256
    assert control.entries[0].pin_nets == {
        "U1.2": ("ADC_IN",),
        "R1.1": ("SENSOR_OUT",),
        "R1.2": ("ADC_IN",),
        "R2.1": ("ADC_IN",),
        "R2.2": ("GND",),
    }
    assert control.entries[0].nominal_resistance_ohms == {"R1": 220000.0, "R2": 33000.0}

    value_fault = reports["value-fault"].signal_divider_coverage.entries[0]
    assert value_fault.status == "OUT_OF_RANGE"
    assert value_fault.nominal_resistance_ohms == {"R1": 180000.0, "R2": 33000.0}
    assert (value_fault.calculated_input_maximum_v or 0) > value_fault.target_input_maximum_v

    split_fault = reports["split-tap-fault"].signal_divider_coverage.entries[0]
    assert split_fault.status == "INCOMPLETE"
    assert split_fault.pin_nets["R2.1"] == ("ADC_OTHER",)

    for case in FIXTURES:
        result = results[f"signal-divider-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result[
            "repeat_normalized_netlist_sha256"
        ]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
