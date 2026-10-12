"""Exact-version native acceptance for generic component peer assignments."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

RULE_ID = "component.generic_peer_pin_assignment_outlier"
FIXTURE_CASES = (
    "component-peer-assignment-outlier-fault",
    "component-peer-assignment-outlier-control",
)
EXPECTED_SOURCE_HASHES = {
    FIXTURE_CASES[0]: "ebf8109ce0270fbee3ed525d3e20aaf2b9c06dab845abc8fd29c828948428dce",
    FIXTURE_CASES[1]: "b8a2b2d9969f779a12dd0ec5e4608895a49205b74f51e407db627bc99004f18a",
}

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="digest-pinned native peer-pin fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_generic_peer_assignment_outlier_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

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

    log = HostedLog(root, f"native-component-peer-outlier-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="component-peer-assignment-outlier-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native = next(
        item
        for item in events
        if item["stage"] == "component-peer-assignment-outlier-fixture/native-export"
    )
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native["command_receipt"])

    fault_case, control_case = FIXTURE_CASES
    fault = context.reports[fault_case, "first"]
    control = context.reports[control_case, "first"]
    fault_findings = [item for item in fault.findings if item.rule_id == RULE_ID]
    assert len(fault_findings) == 1
    assert fault_findings[0].mode == "review"
    assert fault_findings[0].evidence["majority_net"] == ("+5V",)
    assert fault_findings[0].evidence["outlier_pins"] == ("U3.1",)
    assert fault_findings[0].evidence["shared_anchor_contacts"] == ("U1.2 / U2.2 / U3.2 -> GND",)
    assert not any(item.rule_id == RULE_ID for item in control.findings)

    for case in FIXTURE_CASES:
        observed = context.observed_contracts[case, "first"]
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == (context.normalized_netlist_hashes[case, "repeat"])
        )
        assert observed.component_symbols == {
            "U1": "Lint:GenericComponentPeer",
            "U2": "Lint:GenericComponentPeer",
            "U3": "Lint:GenericComponentPeer",
        }
        assert observed.component_pin_numbers == {
            "U1": ("1", "2"),
            "U2": ("1", "2"),
            "U3": ("1", "2"),
        }
        assert all(observed.pin_electrical_types[f"U{index}.1"] == "passive" for index in (1, 2, 3))
