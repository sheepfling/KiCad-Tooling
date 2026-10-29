"""Exact KiCad-version native exports for the unanchored connector power-input hint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_same_voltage_power_input_unanchored"
FAULT_CASE = "footprint-alias-same-voltage-power-input-fault"
CONTROL_CASE = "footprint-alias-same-voltage-power-input-control"
FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = {
    FAULT_CASE: "b1f0fbf69b4bf417ac004147b5eef2649446d8c563bac5716e3aab5a8ea3e78e",
    CONTROL_CASE: "93b2988e463477a23a5041d1d38f4cf07178245dfc757c086f653ae93bab4f56",
}


def test_same_voltage_native_fixture_sources_match_reviewed_hashes() -> None:
    root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-same-voltage-power-input-native"
    )
    assert {
        case: hashlib.sha256((root / f"{name}.kicad_sch").read_bytes()).hexdigest()
        for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control"))
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_same_voltage_connector_power_inputs_fault_and_control_repeatably(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-same-voltage-power-input-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="same-voltage-power-input-fixture",
        rule_overrides_by_case={FAULT_CASE: (RULE_ID,), CONTROL_CASE: (RULE_ID,)},
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "same-voltage-power-input-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    fault = context.reports[FAULT_CASE, "first"]
    fault_observed = context.observed_contracts[FAULT_CASE, "first"]
    assert fault.status == "REVIEW"
    finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
    assert finding.evidence["assignments"] == ("J1.1=+3V3", "J2.1=3.3V")
    assert finding.evidence["nominal_voltage_v"] == ("3.3",)
    assert fault_observed.nets["PORT_A"] == ("J1.2",)
    assert fault_observed.nets["PORT_B"] == ("J2.2",)

    control = context.reports[CONTROL_CASE, "first"]
    assert control.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in control.findings)
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
