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
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
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
    "connector-return-fixture/four-db9-pwm-fault",
    "connector-return-fixture/four-db9-pwm-control",
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
    "connector-return-fixture/component-peer-assignment-outlier-fault",
    "connector-return-fixture/component-peer-assignment-outlier-control",
    "connector-return-fixture/connector-named-power-input-open-fault",
    "connector-return-fixture/connector-named-power-input-open-control",
    "connector-return-fixture/connector-named-power-input-all-open-fault",
    "connector-return-fixture/connector-named-power-input-divergent-fault",
    "connector-return-fixture/connector-named-power-output-open-fault",
    "connector-return-fixture/connector-named-power-output-open-control",
    "connector-return-fixture/connector-named-power-output-all-open-fault",
    "connector-return-fixture/connector-named-power-output-divergent-fault",
    "connector-return-fixture/peer-generic-power-input-fault",
    "connector-return-fixture/peer-generic-power-input-control",
    "connector-return-fixture/peer-named-power-input-open-fault",
    "connector-return-fixture/peer-named-power-input-open-control",
    "connector-return-fixture/peer-named-power-input-divergence-fault",
    "connector-return-fixture/peer-named-power-input-divergence-control",
    "connector-return-fixture/peer-named-power-input-all-open-fault",
    "connector-return-fixture/peer-named-power-input-all-open-control",
    "connector-return-fixture/unconnected-named-supply-fault",
    "connector-return-fixture/unconnected-named-return-fault",
    "connector-return-fixture/unconnected-named-power-control",
    "connector-return-fixture/unconnected-named-component-supply-fault",
    "connector-return-fixture/unconnected-named-component-return-fault",
    "connector-return-fixture/unconnected-named-component-power-control",
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


def _assert_native_named_connector_power_pin_cases(
    tmp_path: Path,
    version: str,
    cases: tuple[str, ...],
    fault_case: str,
    rule_id: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_pin_lane import (
        connector_named_power_pin_fixture_lane,
    )
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.hwrepo.electrical import selected_config
    from kicad_tooling.hwrepo.models import DesignLintPolicy

    project = "controller" if version == "10.0.0" else "raspberry-pi-status-led"
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

    log = HostedLog(root, f"native-named-connector-power-pins-{project}")
    connector_named_power_pin_fixture_lane(
        root, project=project, image=config.image, log=log, case_names=cases
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-named-power-pin-fixture/"
    results = {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}
    assert set(results) == {f"{prefix}native-export", *(f"{prefix}{case}" for case in cases)}
    native_export = results[f"{prefix}native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(item.split(":", 1)[0] for item in native_export["source_hashes"].split(",")) == cases
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    expected = {
        fault_case: ("REVIEW", rule_id),
        "unconnected-named-power-control": ("PASS", "none"),
    }
    for case, (lint_status, findings) in expected.items():
        result = results[f"{prefix}{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == lint_status
        assert result["findings"] == findings
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_unconnected_named_connector_supply_pin_cases_repeat(
    tmp_path: Path, version: str
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_pins import (
        NAMED_CONNECTOR_SUPPLY_PIN_CASES,
    )

    _assert_native_named_connector_power_pin_cases(
        tmp_path,
        version,
        NAMED_CONNECTOR_SUPPLY_PIN_CASES,
        "unconnected-named-supply-fault",
        "connector.unconnected_supply_pin",
    )


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_unconnected_named_connector_return_pin_cases_repeat(
    tmp_path: Path, version: str
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_pins import (
        NAMED_CONNECTOR_RETURN_PIN_CASES,
    )

    _assert_native_named_connector_power_pin_cases(
        tmp_path,
        version,
        NAMED_CONNECTOR_RETURN_PIN_CASES,
        "unconnected-named-return-fault",
        "connector.unconnected_return_pin",
    )
