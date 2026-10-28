"""Exact-version native acceptance for connector metadata-open review."""

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
from kicad_tooling.ci_hosted_connector_return_peer_metadata_open import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_peer_metadata_open_outlier,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    NetlistContract,
)
from tests.connector_footprint_peer_support import lint_report
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
            "connector-footprint-peer-metadata-open-native",
            "fault.kicad_sch",
        ),
        CONTROL_CASE: (
            "connector-footprint-peer-metadata-open-native",
            "control.kicad_sch",
        ),
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        FAULT_CASE: "e6b24ecc2ecbafb23410b23ba18fb34ae78537957e66d4425f59a9265c0c5ed4",
        CONTROL_CASE: "b7f54dfda65d777fc3532f4debb4f399c405b4e34a6d3d3d50d86f655089c8a4",
    }
)


def _observed_fixture(*, common_anchor: bool) -> NetlistContract:
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic peer metadata connector",
                footprint="Synthetic:Package",
            )
            for reference in ("J1", "J2")
        },
        nets={
            "UART_RX_NET": ("J1.1",),
            **(
                {"COMMON_REFERENCE": ("J1.2", "J2.2")}
                if common_anchor
                else {"REFERENCE_A": ("J1.2",), "REFERENCE_B": ("J2.2",)}
            ),
        },
        component_symbols={
            "J1": "Lint:PeerMetadataDivergenceA",
            "J2": "Lint:PeerMetadataDivergenceB",
        },
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={
            "J1.1": "UART_RX",
            "J2.1": "UART_TX",
            "J1.2": "2",
            "J2.2": "2",
        },
        pin_electrical_types={
            "J1.1": "input",
            "J2.1": "output",
            "J1.2": "passive",
            "J2.2": "passive",
        },
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_open_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    assert {
        case: hashlib.sha256((fixture_root / folder / filename).read_bytes()).hexdigest()
        for case, (folder, filename) in FIXTURE_PATHS.items()
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_open_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    for case, (folder, filename) in FIXTURE_PATHS.items():
        assert sources[case] == fixture_root / folder / filename
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]
        assert f"connector-return-fixture/{case}" in EXPECTED_CONNECTOR_RETURN_STAGES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_open_native_validator_checks_fault_and_control() -> None:
    observations = {
        FAULT_CASE: _observed_fixture(common_anchor=True),
        CONTROL_CASE: _observed_fixture(common_anchor=False),
    }
    context = cast(
        ConnectorReturnFixtureContext,
        SimpleNamespace(
            reports={(case, "first"): lint_report(value) for case, value in observations.items()},
            observed_contracts={(case, "first"): value for case, value in observations.items()},
            netlist_hashes={(case, "first"): "a" * 64 for case in FIXTURE_CASES},
        ),
    )

    receipts = verify_footprint_alias_peer_metadata_open_outlier(context)

    assert tuple(receipts) == (FAULT_CASE,)
    assert json.loads(receipts[FAULT_CASE])["netlist_sha256"] == "a" * 64


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
def test_native_metadata_open_fault_and_control_are_repeatable(
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

    log = HostedLog(root, f"native-peer-metadata-open-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="peer-metadata-open-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item for item in events if item.get("stage") == "peer-metadata-open-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_peer_metadata_open_outlier(context)

    fault = context.reports[FAULT_CASE, "first"]
    control = context.reports[CONTROL_CASE, "first"]
    assert fault.status == "REVIEW"
    assert any(item.rule_id == RULE_ID for item in fault.findings)
    assert not any(item.rule_id == RULE_ID for item in control.findings)
    coverage = fault.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.incomplete_pin_metadata_group_count == 0
    assert alias.differing_pin_metadata_group_count == 1
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
