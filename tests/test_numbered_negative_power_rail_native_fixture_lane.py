"""Exact-version native coverage for numbered negative supply labels."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_context import (
    prepare_connector_return_fixture_context,
)
from kicad_tooling.ci_hosted_connector_return_receipts import emit_connector_return_receipts
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

RULE_ID = "net.numbered_power_rails"
_CASES = ("negative-numbered-power-fault", "negative-numbered-power-control")

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned package acceptance lane",
    ),
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_numbered_negative_power_rail_fault_and_control_are_source_bound_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-numbered-negative-power-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=_CASES,
    )
    emit_connector_return_receipts(context, {})

    fault = context.reports[_CASES[0], "first"]
    fault_findings = [item for item in fault.findings if item.rule_id == RULE_ID]
    assert len(fault_findings) == 1
    assert fault_findings[0].subject == "-5V"
    assert dict(fault_findings[0].evidence) == {
        "-5.0V-2": ("J2.3",),
        "-5V_1": ("J1.3",),
    }

    control = context.reports[_CASES[1], "first"]
    assert RULE_ID not in {item.rule_id for item in control.findings}
    assert context.observed_contracts[_CASES[1], "first"].nets["-5V_1"] == (
        "J1.3",
        "J2.3",
    )
    for case in _CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_export = next(
        item
        for item in events
        if item.get("stage") == "connector-return-fixture/native-export"
        and item.get("status") == "PASS"
    )
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert native_export["source_hashes"] == (
        "negative-numbered-power-fault:efd12982e8dfb4ee93cbb6888dae821ba0a26a9a3bfa3411a3f8c1b5c93bf16e,"
        "negative-numbered-power-control:73b371ae8c83e505c7e58ae946a4cf2b448e20c4d022b1c4927ec734c481d103"
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])
