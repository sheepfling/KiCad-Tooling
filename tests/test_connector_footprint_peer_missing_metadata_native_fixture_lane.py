"""Exact-version native acceptance for incomplete connector peer metadata."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_connector_return_peer_missing_metadata import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_peer_missing_metadata_divergence,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_footprint_peer_support import (
    lint_report,
    native_peer_missing_metadata_netlist,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = {
    FAULT_CASE: "7265e062e47c5b1d06a30f40c94cfd23d14cc5f07ff51799ef0afefb21ab2c21",
    CONTROL_CASE: "407e25454fabe943a4f2b9ad5fd58c8d8af48b836cef20258b32d216902db923",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-peer-missing-metadata-native"
    )
    assert {
        case: hashlib.sha256((fixture_root / f"{name}.kicad_sch").read_bytes()).hexdigest()
        for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control"))
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    for case, filename in zip(FIXTURE_CASES, ("fault.kicad_sch", "control.kicad_sch"), strict=True):
        assert sources[case] == (
            fixture_root / "connector-footprint-peer-missing-metadata-native" / filename
        )
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_evidence_validator_checks_split_fault_and_common_control() -> None:
    fault_observed = native_peer_missing_metadata_netlist()
    control_observed = native_peer_missing_metadata_netlist(common_target=True)
    context = SimpleNamespace(
        reports={
            (FAULT_CASE, "first"): lint_report(fault_observed),
            (CONTROL_CASE, "first"): lint_report(control_observed),
        },
        observed_contracts={
            (FAULT_CASE, "first"): fault_observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={(case, "first"): "a" * 64 for case in FIXTURE_CASES},
    )

    receipts = verify_footprint_alias_peer_missing_metadata_divergence(context)

    assert tuple(receipts) == (FAULT_CASE,)
    assert json.loads(receipts[FAULT_CASE])["rule_id"] == RULE_ID


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
def test_native_missing_metadata_fault_and_control_are_repeatable(
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

    log = HostedLog(root, f"native-peer-missing-metadata-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="peer-missing-metadata-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "peer-missing-metadata-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_peer_missing_metadata_divergence(context)

    fault = context.reports[FAULT_CASE, "first"]
    control = context.reports[CONTROL_CASE, "first"]
    assert any(item.rule_id == RULE_ID for item in fault.findings)
    assert not any(item.rule_id == RULE_ID for item in control.findings)
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
