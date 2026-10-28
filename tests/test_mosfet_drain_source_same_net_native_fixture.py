"""Exact-version native exports for MOSFET drain/source same-net lint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_component_mosfet_terminals import (
    FIXTURE_CASES,
    RULE_ID,
    mosfet_drain_source_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "332cc8bef1c6af31e2e585f75824efa6a38049419f88e27071febebc2f07d3a4",
        "control": "e95ed1a5673723dc690e1fad27d534f3f834c371a489957c0c7050f642d18a75",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_mosfet_same_net_fixture_inventory_is_source_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"

    assert set(FIXTURE_CASES) == set(EXPECTED_SOURCE_HASHES)
    for case, relative in FIXTURE_CASES.items():
        source = fixture_root / relative
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SOURCE_HASHES[case]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES") != "1",
    reason="native MOSFET fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_mosfet_same_net_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-mosfet-same-net-{project}")
    mosfet_drain_source_fixture_lane(root, project=project, image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if event.get("stage", "").startswith("mosfet-drain-source-fixture/")
    }

    assert set(results) == {
        "mosfet-drain-source-fixture/native-export",
        "mosfet-drain-source-fixture/fault",
        "mosfet-drain-source-fixture/control",
    }
    native = results["mosfet-drain-source-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURE_CASES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    fault = results["mosfet-drain-source-fixture/fault"]
    control = results["mosfet-drain-source-fixture/control"]
    assert fault["source_sha256"] == EXPECTED_SOURCE_HASHES["fault"]
    assert control["source_sha256"] == EXPECTED_SOURCE_HASHES["control"]
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
    assert fault["rule_findings"] == "Q1: MOSFET drain and source share one schematic net"
    assert fault["lint_status"] == "REVIEW"
    assert control["rule_findings"] == "none"
    assert control["lint_status"] == "PASS"
