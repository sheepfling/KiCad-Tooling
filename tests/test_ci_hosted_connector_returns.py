"""Digest-pinned native connector return and grounding acceptance."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests.hosted_ci_connector_common_support import normalized_connector_return_patterns
from tests.hosted_ci_connector_peer_support import assert_connector_peer_pin_cases
from tests.hosted_ci_connector_power_support import assert_connector_power_and_role_cases
from tests.hosted_ci_connector_return_support import (
    assert_base_connector_return_cases,
    assert_grounding_contract_cases,
    assert_positive_rail_return_cases,
)
from tests.support import reference_root

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.native_kicad,
    pytest.mark.return_path_lint,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned package acceptance lane",
    ),
]


EXPECTED_CONNECTOR_RETURN_STAGES = {
    "connector-return-fixture/native-export",
    "connector-return-fixture/fault",
    "connector-return-fixture/control",
    "connector-return-fixture/return-positive-rail-fault",
    "connector-return-fixture/return-positive-rail-control",
    "connector-return-fixture/unconnected-generic-power-input-fault",
    "connector-return-fixture/unconnected-generic-power-input-control",
    "connector-return-fixture/unconnected-generic-component-power-input-fault",
    "connector-return-fixture/unconnected-generic-component-power-input-control",
    "connector-return-fixture/unconnected-generic-component-power-input-no-connect-fault",
    "connector-return-fixture/unconnected-generic-component-power-input-dnp-control",
    "connector-return-fixture/cross-symbol-fault",
    "connector-return-fixture/cross-symbol-control",
    "connector-return-fixture/cross-symbol-open",
    "connector-return-fixture/mapped-supply-fault",
    "connector-return-fixture/mapped-supply-control",
    "connector-return-fixture/channel-power-fault",
    "connector-return-fixture/channel-power-control",
    "connector-return-fixture/peer-power-fault",
    "connector-return-fixture/peer-power-control",
    "connector-return-fixture/peer-pin-outlier-fault",
    "connector-return-fixture/peer-pin-outlier-control",
    "connector-return-fixture/peer-pin-part-id-open-fault",
    "connector-return-fixture/part-id-all-open-generic-peer-fault",
    "connector-return-fixture/peer-pin-part-id-common-control",
    "connector-return-fixture/peer-pin-part-id-split-fault",
    "connector-return-fixture/two-peer-open-fault",
    "connector-return-fixture/two-peer-no-connect-fault",
    "connector-return-fixture/two-peer-common-control",
    "connector-return-fixture/all-open-generic-peer-fault",
    "connector-return-fixture/all-open-generic-peer-control",
    "connector-return-fixture/all-open-generic-signal-peer-fault",
    "connector-return-fixture/all-open-generic-signal-peer-control",
    "connector-return-fixture/all-open-generic-signal-types-fault",
    "connector-return-fixture/all-open-generic-signal-types-control",
    "connector-return-fixture/single-offboard-port-control",
    "connector-return-fixture/offboard-inventory-unreviewed",
    "connector-return-fixture/offboard-interface-control",
    "connector-return-fixture/peer-pin-minority-fault",
    "connector-return-fixture/peer-pin-divergence-fault",
    "connector-return-fixture/generic-placeholder-divergence-fault",
    "connector-return-fixture/generic-placeholder-control",
    "connector-return-fixture/peer-scope-split-return-fault",
    "connector-return-fixture/peer-scope-separate-fault",
    "connector-return-fixture/peer-scope-shared-fault",
    "connector-return-fixture/peer-scope-shared-control",
    "connector-return-fixture/four-db9-fault",
    "connector-return-fixture/four-db9-control",
    "connector-return-fixture/four-db9-neutral-fault",
    "connector-return-fixture/four-db9-neutral-control",
    "connector-return-fixture/ground-contract-common-fault",
    "connector-return-fixture/ground-contract-common-control",
    "connector-return-fixture/ground-contract-isolated-fault",
    "connector-return-fixture/ground-contract-isolated-control",
    "connector-return-fixture/pin-connectivity-contract-common-fault",
    "connector-return-fixture/pin-connectivity-contract-common-control",
    "connector-return-fixture/pin-connectivity-contract-isolated-fault",
    "connector-return-fixture/pin-connectivity-contract-isolated-control",
    "connector-return-fixture/pin-connectivity-contract-peer-common-open-fault",
    "connector-return-fixture/pin-connectivity-contract-peer-common-control",
    "connector-return-fixture/pin-connectivity-contract-peer-independent-control",
    "connector-return-fixture/pin-connectivity-contract-peer-independent-common-net-mismatch",
    "connector-return-fixture/pin-connectivity-contract-stale-pin-reference",
    "connector-return-fixture/reviewed-role-fault",
    "connector-return-fixture/reviewed-role-control",
    "connector-return-fixture/reviewed-supply-fault",
    "connector-return-fixture/reviewed-supply-control",
    "connector-return-fixture/reviewed-supply-domain-control",
}


@pytest.fixture(scope="module")
def connector_return_results_by_version() -> dict[str, dict[str, dict[str, Any]]]:
    from kicad_tooling.ci_hosted import HostedLog, connector_return_lint_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-connector-return-project-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_versions = {
        "controller": "10.0.0",
        "raspberry-pi-status-led": "10.0.5",
    }
    results_by_version: dict[str, dict[str, dict[str, Any]]] = {}
    for project, version in expected_versions.items():
        config = selected_config(root, project)
        if config.kicad_version != version:
            raise AssertionError(
                f"{project} selected KiCad {config.kicad_version}; expected {version}"
            )
        log = HostedLog(root, f"native-connector-return-{project}")
        connector_return_lint_fixture_lane(
            root,
            project=project,
            image=config.image,
            log=log,
        )
        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("connector-return-fixture/")
        }
        if set(results) != EXPECTED_CONNECTOR_RETURN_STAGES:
            missing = sorted(EXPECTED_CONNECTOR_RETURN_STAGES - set(results))
            extra = sorted(set(results) - EXPECTED_CONNECTOR_RETURN_STAGES)
            raise AssertionError(
                f"Connector fixture stage mismatch: missing={missing}, extra={extra}"
            )
        results_by_version[version] = results
    return results_by_version


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.return_path_lint
def test_return_pin_on_positive_rail(connector_return_results_by_version, version):
    assert_positive_rail_return_cases(connector_return_results_by_version[version], version)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.return_path_lint
def test_return_net_and_cross_symbol_findings(connector_return_results_by_version, version):
    assert_base_connector_return_cases(connector_return_results_by_version[version], version)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.interface_lint
def test_peer_pin_assignments_and_offboard_scope(connector_return_results_by_version, version):
    assert_connector_peer_pin_cases(connector_return_results_by_version[version], version)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.component_lint
@pytest.mark.power_lint
def test_power_pin_and_reviewed_role_cases(connector_return_results_by_version, version):
    assert_connector_power_and_role_cases(connector_return_results_by_version[version], version)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.return_path_lint
def test_grounding_and_pin_connectivity_contracts(connector_return_results_by_version, version):
    assert_grounding_contract_cases(connector_return_results_by_version[version], version)


@pytest.mark.connector_lint
@pytest.mark.return_path_lint
def test_normalized_return_patterns_match_across_versions(connector_return_results_by_version):
    patterns_by_version = {
        version: normalized_connector_return_patterns(results)
        for version, results in connector_return_results_by_version.items()
    }
    assert patterns_by_version["10.0.0"] == patterns_by_version["10.0.5"]
