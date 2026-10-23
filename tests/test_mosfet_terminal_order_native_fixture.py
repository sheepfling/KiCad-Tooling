"""Digest-pinned native exports for MOSFET drain/source-order review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_mosfet_gate_fixture import MOSFET_TERMINAL_ORDER_FIXTURE_CASES
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_terminal_order_on_named_rails"
EXPECTED_SOURCE_HASHES: dict[str, str] = {
    "fault_nmos": "b79b2a7bfde5855e43bf7abbed61f1d9954a576e88ffcc9c07a3d2f42953a81f",
    "control_nmos": "5b876b74b39d730820ae3d4cbb7d462874e0affa4a91add709db90c118154103",
    "fault_pmos": "be3131997dc36fab36ab838dbafe52cb789838abab8a6a1e17aebe14de529a41",
    "control_pmos": "d5b4873bfcc1132c3940ebe112a5546ebc0a2820ad85c43655bf488fdac56e6a",
}


def test_native_mosfet_terminal_order_fixture_inventory_is_source_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    actual = {
        case: relative
        for case, relative in MOSFET_TERMINAL_ORDER_FIXTURE_CASES.items()
        if (fixture_root / relative).is_file()
    }

    assert actual == {
        "fault_nmos": "mosfet-terminal-order-native/fault_nmos.kicad_sch",
        "control_nmos": "mosfet-terminal-order-native/control_nmos.kicad_sch",
        "fault_pmos": "mosfet-terminal-order-native/fault_pmos.kicad_sch",
        "control_pmos": "mosfet-terminal-order-native/control_pmos.kicad_sch",
    }
    assert EXPECTED_SOURCE_HASHES.keys() == actual.keys()
    for case, relative in actual.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
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
def test_native_mosfet_terminal_order_faults_and_controls_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_mosfet_gate_fixture import mosfet_terminal_order_fixture_lane

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-mosfet-terminal-order-{project}")
    mosfet_terminal_order_fixture_lane(root, project=project, image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if event.get("stage", "").startswith("mosfet-terminal-order-fixture/")
    }
    assert set(results) == {
        "mosfet-terminal-order-fixture/native-export",
        *(f"mosfet-terminal-order-fixture/{case}" for case in MOSFET_TERMINAL_ORDER_FIXTURE_CASES),
    }
    native = results["mosfet-terminal-order-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in MOSFET_TERMINAL_ORDER_FIXTURE_CASES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, channel in (
        ("fault_nmos", "NMOS"),
        ("fault_pmos", "PMOS"),
        ("control_nmos", "NMOS"),
        ("control_pmos", "PMOS"),
    ):
        result = results[f"mosfet-terminal-order-fixture/{case}"]
        expected = (
            f"Q1: MOSFET {channel} drain/source order merits review"
            if case.startswith("fault_")
            else "none"
        )
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["rule_findings"] == expected
        assert result["lint_status"] == ("REVIEW" if case.startswith("fault_") else "PASS")
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
