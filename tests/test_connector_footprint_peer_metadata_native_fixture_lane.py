"""Exact-version native acceptance for connector peer metadata divergence."""

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
from kicad_tooling.ci_hosted_connector_return_peer_metadata_divergence import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_peer_metadata_divergence,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.connector_footprint_peer_support import lint_report
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = {
    FAULT_CASE: "eb57ac1553fa4a6d76a297375ec840d8b6b01c401401877a470968e4c12a45d6",
    CONTROL_CASE: "1377db1444bf8c1c15bbde73358fe81e36c11581869ea5f31f2082464e97f45e",
}


def _observed_fixture(*, common_target: bool) -> NetlistContract:
    components = {
        reference: ComponentContract(
            value="Synthetic peer metadata connector",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    nets = {
        "COMMON_REFERENCE": ("J1.2", "J2.2"),
        **(
            {"SHARED_PORT": ("J1.1", "J2.1")}
            if common_target
            else {
                "UART_RX_NET": ("J1.1",),
                "UART_TX_NET": ("J2.1",),
            }
        ),
    }
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={
            "J1": "Lint:PeerMetadataDivergenceA",
            "J2": "Lint:PeerMetadataDivergenceB",
        },
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={
            "J1.1": "UART_RX",
            "J1.2": "2",
            "J2.1": "UART_TX",
            "J2.2": "2",
        },
        pin_electrical_types={
            "J1.1": "input",
            "J1.2": "passive",
            "J2.1": "output",
            "J2.2": "passive",
        },
    )


def test_metadata_divergence_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-peer-metadata-native"
    )
    assert {
        case: hashlib.sha256((fixture_root / f"{name}.kicad_sch").read_bytes()).hexdigest()
        for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control"))
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_divergence_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    for case, filename in zip(FIXTURE_CASES, ("fault.kicad_sch", "control.kicad_sch"), strict=True):
        assert sources[case] == (
            fixture_root / "connector-footprint-peer-metadata-native" / filename
        )
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_divergence_validator_checks_fault_and_control() -> None:
    fault_observed = _observed_fixture(common_target=False)
    control_observed = _observed_fixture(common_target=True)
    fault_report = lint_report(fault_observed)
    control_report = lint_report(control_observed)
    netlist_sha256 = "a" * 64
    context = SimpleNamespace(
        reports={
            (FAULT_CASE, "first"): fault_report,
            (CONTROL_CASE, "first"): control_report,
        },
        observed_contracts={
            (FAULT_CASE, "first"): fault_observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={
            (FAULT_CASE, "first"): netlist_sha256,
            (CONTROL_CASE, "first"): netlist_sha256,
        },
    )

    receipts = verify_footprint_alias_peer_metadata_divergence(context)

    assert tuple(receipts) == (FAULT_CASE,)
    assert json.loads(receipts[FAULT_CASE])["netlist_sha256"] == netlist_sha256


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
def test_native_metadata_divergence_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic native fixture enables this bounded review heuristic.",
            ),
        )
    )
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)

    log = HostedLog(root, f"native-peer-metadata-divergence-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="peer-metadata-divergence-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "peer-metadata-divergence-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_peer_metadata_divergence(context)

    fault = context.reports[FAULT_CASE, "first"]
    assert fault.status == "REVIEW"
    assert any(item.rule_id == RULE_ID for item in fault.findings)
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
