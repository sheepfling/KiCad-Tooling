"""Digest-pinned native connector return and grounding acceptance."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests.hosted_ci_component_power_support import assert_unconnected_component_power_input_cases
from tests.hosted_ci_connector_common_support import normalized_connector_return_patterns
from tests.hosted_ci_connector_peer_support import assert_connector_peer_pin_cases
from tests.hosted_ci_connector_power_support import assert_connector_power_and_role_cases
from tests.hosted_ci_connector_return_support import (
    assert_base_connector_return_cases,
    assert_grounding_contract_cases,
    assert_positive_rail_return_cases,
)
from tests.hosted_connector_return_expected_stages import EXPECTED_CONNECTOR_RETURN_STAGES
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
@pytest.mark.interface_lint
def test_footprint_alias_peer_assignments_are_validated_on_pinned_native_versions(
    connector_return_results_by_version, version
):
    results = connector_return_results_by_version[version]
    fault = results["connector-return-fixture/footprint-alias-fault"]
    control = results["connector-return-fixture/footprint-alias-control"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "connector.footprint_peer_pin_assignment_divergence"
    assert fault["subjects"] == ("Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2")
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"

    fault_coverage = json.loads(fault["connector_peer_pin_coverage"])["footprint_alias_coverage"]
    control_coverage = json.loads(control["connector_peer_pin_coverage"])[
        "footprint_alias_coverage"
    ]
    assert fault_coverage["status"] == "EVALUATED"
    assert fault_coverage["netlist_sha256"] == fault["netlist_sha256"]
    assert fault_coverage["candidate_group_count"] == 1
    assert fault_coverage["compared_pin_group_count"] == 2
    assert fault_coverage["common_anchor_group_count"] == 1
    assert fault_coverage["divergence_finding_count"] == 1
    assert control_coverage["status"] == "NO_DIVERGENT_ASSIGNMENTS"
    assert control_coverage["common_assignment_pin_group_count"] == 2
    numeric_fault = results["connector-return-fixture/footprint-alias-numeric-fault"]
    numeric_control = results["connector-return-fixture/footprint-alias-numeric-control"]
    assert numeric_fault["lint_status"] == "REVIEW"
    assert numeric_fault["findings"] == "connector.footprint_peer_pin_assignment_divergence"
    assert numeric_fault["pin_functions"] == "J1.1=1;J1.2=7;J2.1=1;J2.2=7"
    assert numeric_control["lint_status"] == "PASS"
    assert numeric_control["findings"] == "none"
    for result in (fault, control, numeric_fault, numeric_control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
def test_footprint_alias_open_peer_is_validated_on_pinned_native_versions(
    connector_return_results_by_version, version
):
    results = connector_return_results_by_version[version]
    fault = results["connector-return-fixture/footprint-alias-open-fault"]
    control = results["connector-return-fixture/footprint-alias-control"]
    numeric_fault = results["connector-return-fixture/footprint-alias-numeric-open-fault"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "connector.footprint_peer_pin_open_outlier"
    assert fault["subjects"] == ("Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2")
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert numeric_fault["lint_status"] == "REVIEW"
    assert numeric_fault["findings"] == "connector.footprint_peer_pin_open_outlier"
    assert numeric_fault["pin_functions"] == "J1.1=1;J1.2=7;J2.1=1;J2.2=7"

    fault_coverage = json.loads(fault["connector_peer_pin_coverage"])["footprint_alias_coverage"]
    assert fault_coverage["status"] == "PARTIALLY_EVALUATED"
    assert fault_coverage["netlist_sha256"] == fault["netlist_sha256"]
    assert fault_coverage["candidate_group_count"] == 1
    assert fault_coverage["common_anchor_group_count"] == 1
    assert fault_coverage["open_peer_pin_group_count"] == 1
    assert fault_coverage["open_outlier_finding_count"] == 1
    for result in (fault, control, numeric_fault):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

    named_fault = results["connector-return-fixture/footprint-alias-named-power-input-fault"]
    named_control = results["connector-return-fixture/footprint-alias-named-power-input-control"]
    assert named_fault["lint_status"] == "REVIEW"
    assert named_fault["findings"] == "connector.footprint_named_power_input_open_outlier"
    assert named_fault["pin_functions"] == "J1.1=BIAS_IN;J1.2=2;J2.1=BIAS_IN;J2.2=2"
    assert named_control["lint_status"] == "PASS"
    assert named_control["findings"] == "none"
    named_coverage = json.loads(named_fault["connector_peer_pin_coverage"])[
        "footprint_alias_coverage"
    ]
    assert named_coverage["status"] == "PARTIALLY_EVALUATED"
    assert named_coverage["netlist_sha256"] == named_fault["netlist_sha256"]
    assert named_coverage["candidate_group_count"] == 1
    assert named_coverage["common_anchor_group_count"] == 1
    assert named_coverage["open_peer_pin_group_count"] == 1
    assert named_coverage["open_outlier_finding_count"] == 1
    for result in (named_fault, named_control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

    signal_fault = results["connector-return-fixture/footprint-alias-named-signal-input-fault"]
    signal_control = results["connector-return-fixture/footprint-alias-named-signal-input-control"]
    assert signal_fault["lint_status"] == "REVIEW"
    assert signal_fault["findings"] == "connector.footprint_named_signal_input_open_outlier"
    assert signal_fault["pin_functions"] == "J1.1=UART_RX;J1.2=2;J2.1=UART_RX;J2.2=2"
    assert signal_control["lint_status"] == "PASS"
    assert signal_control["findings"] == "none"
    signal_coverage = json.loads(signal_fault["connector_peer_pin_coverage"])[
        "footprint_alias_coverage"
    ]
    assert signal_coverage["status"] == "PARTIALLY_EVALUATED"
    assert signal_coverage["netlist_sha256"] == signal_fault["netlist_sha256"]
    assert signal_coverage["candidate_group_count"] == 1
    assert signal_coverage["common_anchor_group_count"] == 1
    assert signal_coverage["open_peer_pin_group_count"] == 1
    assert signal_coverage["open_outlier_finding_count"] == 1
    for result in (signal_fault, signal_control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
def test_footprint_alias_all_open_peer_is_validated_on_pinned_native_versions(
    connector_return_results_by_version, version
):
    results = connector_return_results_by_version[version]
    fault = results["connector-return-fixture/footprint-alias-all-open-fault"]
    control = results["connector-return-fixture/footprint-alias-control"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "connector.footprint_peer_pin_all_open"
    assert fault["subjects"] == ("Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2")
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"

    fault_coverage = json.loads(fault["connector_peer_pin_coverage"])["footprint_alias_coverage"]
    control_coverage = json.loads(control["connector_peer_pin_coverage"])[
        "footprint_alias_coverage"
    ]
    assert fault_coverage["status"] == "PARTIALLY_EVALUATED"
    assert fault_coverage["netlist_sha256"] == fault["netlist_sha256"]
    assert fault_coverage["candidate_group_count"] == 1
    assert fault_coverage["common_anchor_group_count"] == 1
    assert fault_coverage["all_open_peer_pin_group_count"] == 1
    assert fault_coverage["all_open_finding_count"] == 1
    assert control_coverage["all_open_finding_count"] == 0


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
def test_footprint_alias_named_signal_divergence_is_validated_on_pinned_native_versions(
    connector_return_results_by_version, version
):
    results = connector_return_results_by_version[version]
    fault = results["connector-return-fixture/footprint-alias-named-signal-divergence-fault"]
    control = results["connector-return-fixture/footprint-alias-named-signal-output-control"]

    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "connector.footprint_named_signal_assignment_divergence"
    assert fault["pin_functions"] == "J1.1=UART_TX;J1.2=2;J2.1=UART_TX;J2.2=2"
    coverage = json.loads(fault["connector_peer_pin_coverage"])["footprint_alias_coverage"]
    assert coverage["named_signal_different_assignment_pin_group_count"] == 1
    assert coverage["named_signal_divergence_finding_count"] == 1
    assert coverage["unanchored_named_signal_divergence_pin_group_count"] == 0
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.connector_lint
@pytest.mark.component_lint
@pytest.mark.power_lint
def test_power_pin_and_reviewed_role_cases(connector_return_results_by_version, version):
    assert_connector_power_and_role_cases(connector_return_results_by_version[version], version)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
@pytest.mark.component_lint
def test_unconnected_component_power_input_faults_and_controls(
    connector_return_results_by_version, version
):
    assert_unconnected_component_power_input_cases(
        connector_return_results_by_version[version],
        version,
    )


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
