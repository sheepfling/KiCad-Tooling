"""Exact-version source regressions for MOSFET gate connectivity heuristics."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_mosfet_gate_fixture import MOSFET_GATE_FIXTURE_CASES
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.component_mosfet_gate_drive import RULE_ID as DIRECT_DRIVE_RULE_ID
from kicad_tooling.hwrepo.design_lint_component_mosfet_terminals import (
    GATE_SOURCE_RULE_ID as GATE_SOURCE_SAME_NET_RULE_ID,
)
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.mosfet_gate_connectivity import SOURCE_BIAS_RULE_ID
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
]

RULE_ID = "component.mosfet_gate_without_peer"
EXPECTED_SOURCE_HASHES = {
    "fault": "5cd4983eb3ac3abc6370f8d5626fae3fbe8b1e38ce26b32d31e0cb3c7d9a8c6c",
    "control": "e95ed1a5673723dc690e1fad27d534f3f834c371a489957c0c7050f642d18a75",
    "source-bias-control": "d7529a3ce8d7815669fa764cd1c0a868ea37dd94aae072fe66e05a3e34c48e78",
    "series-gate-control": "5f6a6b62155601ef51c1d9d3dad30dd2e5b8d02f22fa210f332fdf9566322323",
    "gate-source-fault": "75849c215452527d32739eb43d9a8d7ec72ee2a0a31fc50e49360bbb8e62986c",
    "gate-source-control": "d7529a3ce8d7815669fa764cd1c0a868ea37dd94aae072fe66e05a3e34c48e78",
}


def test_native_mosfet_gate_fixture_scope_matches_registered_cases() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    actual = {
        case: relative
        for case, relative in MOSFET_GATE_FIXTURE_CASES.items()
        if (fixture_root / relative).is_file()
    }

    assert actual == {
        "fault": "mosfet-gate-native/fault.kicad_sch",
        "control": "mosfet-gate-native/control.kicad_sch",
        "source-bias-control": "mosfet-gate-native/source-bias-control.kicad_sch",
        "series-gate-control": "mosfet-gate-native/series-gate-control.kicad_sch",
        "gate-source-fault": "mosfet-gate-native/gate-source-tie.kicad_sch",
        "gate-source-control": "mosfet-gate-native/source-bias-control.kicad_sch",
    }
    assert EXPECTED_SOURCE_HASHES.keys() == actual.keys()
    for case, relative in actual.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=SOURCE_BIAS_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=DIRECT_DRIVE_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=GATE_SOURCE_SAME_NET_RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES") != "1",
    reason="native component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_mosfet_gate_fault_and_control_are_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_mosfet_gate_fixture import mosfet_gate_fixture_lane

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-mosfet-gate-{project}")
    mosfet_gate_fixture_lane(root, project=project, image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if event.get("stage", "").startswith("mosfet-gate-fixture/")
    }
    assert set(results) == {
        "mosfet-gate-fixture/native-export",
        "mosfet-gate-fixture/fault",
        "mosfet-gate-fixture/control",
        "mosfet-gate-fixture/source-bias-control",
        "mosfet-gate-fixture/series-gate-control",
        "mosfet-gate-fixture/gate-source-fault",
        "mosfet-gate-fixture/gate-source-control",
    }
    native = results["mosfet-gate-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in MOSFET_GATE_FIXTURE_CASES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    fault = results["mosfet-gate-fixture/fault"]
    control = results["mosfet-gate-fixture/control"]
    source_bias_control = results["mosfet-gate-fixture/source-bias-control"]
    series_gate_control = results["mosfet-gate-fixture/series-gate-control"]
    gate_source_fault = results["mosfet-gate-fixture/gate-source-fault"]
    gate_source_control = results["mosfet-gate-fixture/gate-source-control"]
    assert fault["rule_findings"] == "Q1.2: MOSFET gate has no other fitted pin on its net"
    assert control["rule_findings"] == "none"
    assert fault["source_bias_rule_findings"] == "none"
    assert control["source_bias_rule_findings"] == (
        "Q1.2: MOSFET gate has no visible source-bias resistor"
    )
    assert source_bias_control["rule_findings"] == "none"
    assert source_bias_control["source_bias_rule_findings"] == "none"
    assert fault["direct_drive_rule_findings"] == "none"
    assert control["direct_drive_rule_findings"] == (
        "Q1.2: MOSFET gate directly shares a net with an output-capable pin"
    )
    assert source_bias_control["direct_drive_rule_findings"] == (
        "Q1.2: MOSFET gate directly shares a net with an output-capable pin"
    )
    assert series_gate_control["direct_drive_rule_findings"] == "none"
    assert gate_source_fault["gate_source_rule_findings"] == (
        "Q1: MOSFET gate and source share one schematic net"
    )
    assert gate_source_control["gate_source_rule_findings"] == "none"
    assert gate_source_fault["direct_drive_rule_findings"] == (
        "Q1.2: MOSFET gate directly shares a net with an output-capable pin"
    )
    for case, result in (
        ("fault", fault),
        ("control", control),
        ("source-bias-control", source_bias_control),
        ("series-gate-control", series_gate_control),
        ("gate-source-fault", gate_source_fault),
        ("gate-source-control", gate_source_control),
    ):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["repeatable"] == "true"
        assert result["erc_errors"] == "none"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
