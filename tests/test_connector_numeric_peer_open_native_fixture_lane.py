"""Exact-version native acceptance for numeric-only connector peer contacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_context import (
    prepare_connector_return_fixture_context,
)
from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.generic_peer_pin_open_outlier"
FIXTURE_CASES = (
    "numeric-peer-open-fault",
    "numeric-peer-open-control",
    "numeric-peer-open-no-connect-ambiguity",
    "numeric-peer-open-part-id-fault",
    "numeric-peer-open-part-id-control",
)
EXPECTED_SOURCE_HASHES = {
    "numeric-peer-open-fault": "fecaec12fc64b0cbc9bbe8c90a0a604868782128b2ae206b71f52ad3e8d3496d",
    "numeric-peer-open-control": "9db45f6376dc7c10e7dea042a3912ab4afca4ae3e7554b10a6ab847dd96701eb",
    "numeric-peer-open-no-connect-ambiguity": "2abc2eb0203e003e91fb42e1be6a9975a53d1387fc26752ed16c232ac4757847",
    "numeric-peer-open-part-id-fault": "ad5df0aaf379b4db0386be2ed632c4c197b39c68db75d0028f05dc0b4c68387f",
    "numeric-peer-open-part-id-control": "329fdda52919463f4a3788f27353ae3510e51aaa48dcba93f3ac1dcc7d010115",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_numeric_peer_open_fixture_sources_match_the_manifest() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    expected_files = {
        "numeric-peer-open-fault": "fault.kicad_sch",
        "numeric-peer-open-control": "control.kicad_sch",
        "numeric-peer-open-no-connect-ambiguity": "no-connect-ambiguity.kicad_sch",
        "numeric-peer-open-part-id-fault": "part-id-fault.kicad_sch",
        "numeric-peer-open-part-id-control": "part-id-control.kicad_sch",
    }

    assert {
        case: hashlib.sha256(sources[case].read_bytes()).hexdigest() for case in FIXTURE_CASES
    } == EXPECTED_SOURCE_HASHES
    assert all(
        sources[case] == fixture_root / "connector-numeric-peer-open-native" / filename
        for case, filename in expected_files.items()
    )
    assert {
        case: CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] for case in FIXTURE_CASES
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_numeric_peer_open_fault_control_and_no_connect_are_repeatable(
    tmp_path: Path,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    project = f"numeric-peer-open-{version.replace('.', '-')}"
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic connector fixture exercises numeric generic peer review",
            ),
        )
    )
    root, _ = synthetic_design_lint_project(
        tmp_path / project,
        policy,
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-numeric-peer-open-{version}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="numeric-peer-open-fixture",
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        event for event in events if event.get("stage") == "numeric-peer-open-fixture/native-export"
    )
    assert tuple(event["status"] for event in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    fault = context.reports["numeric-peer-open-fault", "first"]
    new_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    assert fault.status == "REVIEW"
    assert len(new_findings) == 1
    assert new_findings[0].evidence["J2.1"] == ()
    assert new_findings[0].evidence["J1.1"] == ("+5V",)
    assert new_findings[0].evidence["shared_anchor_contacts"] == ("J1.2 / J2.2 -> GND",)
    assert (
        context.observed_contracts["numeric-peer-open-fault", "first"].pin_functions["J2.1"] == "1"
    )

    for case in FIXTURE_CASES[1:]:
        report = context.reports[case, "first"]
        if case.endswith("no-connect-ambiguity"):
            observed = context.observed_contracts[case, "first"]
            assert any("J2.1" in pins for pins in observed.unconnected_nets.values())
            no_connect_findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
            assert report.status == "REVIEW"
            assert len(no_connect_findings) == 1
        elif case.endswith("part-id-fault"):
            alias_findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
            assert report.status == "REVIEW"
            assert len(alias_findings) == 1
            assert alias_findings[0].evidence["peer_identity_basis"] == ("part_id",)
        else:
            assert not any(item.rule_id == RULE_ID for item in report.findings)
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )

    part_id_fault = context.reports["numeric-peer-open-part-id-fault", "first"]
    part_id_findings = tuple(item for item in part_id_fault.findings if item.rule_id == RULE_ID)
    assert part_id_fault.status == "REVIEW"
    assert len(part_id_findings) == 1
    assert part_id_findings[0].evidence["peer_identity_basis"] == ("part_id",)
    assert part_id_findings[0].evidence["peer_identity"] == ("SYNTHETIC-NUMERIC-PEER",)
    assert part_id_findings[0].evidence["J3.1"] == ()
    assert part_id_findings[0].evidence["shared_anchor_contacts"] == ("J1.2 / J2.2 / J3.2 -> GND",)
    part_id_observed = context.observed_contracts["numeric-peer-open-part-id-fault", "first"]
    assert (
        tuple(part_id_observed.components[ref].part_id for ref in ("J1", "J2", "J3"))
        == ("SYNTHETIC-NUMERIC-PEER",) * 3
    )
    assert {part_id_observed.component_symbols[ref] for ref in ("J1", "J2", "J3")} == {
        "Lint:PeerPowerPort",
        "Lint:PeerPowerPortAlt",
    }
    part_id_control = context.reports["numeric-peer-open-part-id-control", "first"]
    assert not any(item.rule_id == RULE_ID for item in part_id_control.findings)
