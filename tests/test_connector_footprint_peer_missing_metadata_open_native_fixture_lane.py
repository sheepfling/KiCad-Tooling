"""Exact-version native acceptance for open peers with missing pin metadata."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.ci_hosted_connector_return_context import (
    ConnectorReturnFixtureContext,
    prepare_connector_return_fixture_context,
)
from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_connector_return_peer_missing_metadata_open import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_peer_missing_metadata_open_outlier,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_footprint_peer_support import lint_report
from tests.design_lint_fixtures.connector_peer_missing_metadata_open import (
    missing_metadata_open_peer_netlist,
)
from tests.hosted_connector_return_expected_stages import EXPECTED_CONNECTOR_RETURN_STAGES
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
FIXTURE_PATHS = MappingProxyType(
    {
        FAULT_CASE: (
            "connector-footprint-peer-missing-metadata-open-native",
            "fault.kicad_sch",
        ),
        CONTROL_CASE: (
            "connector-footprint-peer-missing-metadata-open-native",
            "control.kicad_sch",
        ),
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        FAULT_CASE: "ac23a42151b013689a6c90c66ba36da980f9798c670a553ab90983efb413e73e",
        CONTROL_CASE: "ea9380576e3dd2aaa3710935c28c7b38b14399a5954ecc939d1538dd1722d0f0",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    assert {
        case: hashlib.sha256((fixture_root / folder / filename).read_bytes()).hexdigest()
        for case, (folder, filename) in FIXTURE_PATHS.items()
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    for case, (folder, filename) in FIXTURE_PATHS.items():
        assert sources[case] == fixture_root / folder / filename
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]
        assert f"connector-return-fixture/{case}" in EXPECTED_CONNECTOR_RETURN_STAGES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_native_validator_checks_fault_and_control() -> None:
    observations = {
        FAULT_CASE: missing_metadata_open_peer_netlist(),
        CONTROL_CASE: missing_metadata_open_peer_netlist(
            target_assignments=("SHARED_PORT", "SHARED_PORT")
        ),
    }
    context = cast(
        ConnectorReturnFixtureContext,
        SimpleNamespace(
            reports={(case, "first"): lint_report(value) for case, value in observations.items()},
            observed_contracts={(case, "first"): value for case, value in observations.items()},
            netlist_hashes={(case, "first"): "a" * 64 for case in FIXTURE_CASES},
        ),
    )

    receipts = verify_footprint_alias_peer_missing_metadata_open_outlier(context)

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
def test_native_open_metadata_fault_and_control_are_repeatable(
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
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)

    log = HostedLog(root, f"native-peer-missing-metadata-open-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="peer-missing-metadata-open-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "peer-missing-metadata-open-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_peer_missing_metadata_open_outlier(context)

    fault = context.reports[FAULT_CASE, "first"]
    control = context.reports[CONTROL_CASE, "first"]
    assert fault.status == "REVIEW"
    assert any(item.rule_id == RULE_ID for item in fault.findings)
    assert not any(item.rule_id == RULE_ID for item in control.findings)
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
