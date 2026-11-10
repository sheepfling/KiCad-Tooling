"""Exact KiCad exports for mapped connector supply/return net sharing."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_report,
)
from tests.design_lint_fixtures.connector_mapped_supply_return_sharing import (
    supply_return_coverage,
    supply_return_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_supply_return_share_net"
SUPPLY_SHIELD_RULE_ID = "connector.mapped_supply_shield_share_net"
RETURN_SHIELD_RULE_ID = "connector.mapped_return_shield_share_net"
SAME_DOMAIN_SUPPLY_SPLIT_RULE_ID = "connector.mapped_same_domain_supply_split_nets"
SAME_DOMAIN_RETURN_SPLIT_RULE_ID = "connector.mapped_same_domain_return_split_nets"
RETURN_DOMAINS_SHARED_NET_RULE_ID = "connector.mapped_return_domains_share_net"
FIXTURE_CASES = {
    "mapped-supply-return-share-fault": (
        "fault.kicad_sch",
        "7050c0df9e0861b8650c438e6cfe2cdaa54159e7628b343e90d45f192ce73471",
    ),
    "mapped-supply-return-share-control": (
        "control.kicad_sch",
        "43db3b6ec2c64cc09c6551489363b8c8f1a87e42e49b565761fc2ca5e15c70da",
    ),
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=SUPPLY_SHIELD_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=RETURN_SHIELD_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=SAME_DOMAIN_SUPPLY_SPLIT_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=SAME_DOMAIN_RETURN_SPLIT_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=RETURN_DOMAINS_SHARED_NET_RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="exact-version native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
@pytest.mark.parametrize("fixture_case", tuple(FIXTURE_CASES))
def test_native_mapped_supply_return_share_fault_and_control(
    tmp_path: Path,
    project: str,
    version: str,
    fixture_case: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
    from tests.native_fixture_support import assert_native_fixture_mounts
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    source_name, source_sha256 = FIXTURE_CASES[fixture_case]
    source = fixture_root / "mapped-supply-return-share" / source_name
    assert connector_return_fixture_sources(fixture_root)[fixture_case] == source
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256
    assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[fixture_case] == source_sha256

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

    log = HostedLog(root, f"native-mapped-supply-return-share-{project}-{fixture_case}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=(fixture_case,),
        stage_prefix="mapped-supply-return-share-native",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-supply-return-share-native/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == {fixture_case: source_sha256}
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    observed = context.observed_contracts[fixture_case, "first"]
    mapped_return_coverage = signal_sharing_coverage(
        observed,
        signal_names=("SIGNAL_RETURN", "CHASSIS_RETURN"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    mapped_return_report, _ = signal_sharing_report(observed, coverage=mapped_return_coverage)
    mapped_return_findings = tuple(
        item
        for item in mapped_return_report.findings
        if item.rule_id == RETURN_DOMAINS_SHARED_NET_RULE_ID
    )
    if fixture_case.endswith("fault"):
        assert len(mapped_return_findings) == 1
        assert mapped_return_findings[0].evidence["native_shared_net"] == ("AUX_SHARED_NODE",)
    else:
        assert not mapped_return_findings

    assert observed.pin_functions["J1.1"] == "1"
    assert observed.pin_functions["J1.2"] == "2"
    report, coverage = supply_return_report(
        observed,
        coverage=supply_return_coverage(observed),
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert coverage.status == "COMPLETE"
    assert (
        context.normalized_netlist_hashes[fixture_case, "first"]
        == context.normalized_netlist_hashes[fixture_case, "repeat"]
    )
    if fixture_case.endswith("fault"):
        assert observed.nets["AUX_SHARED_NODE"] == ("J1.1", "J1.2")
        assert len(findings) == 1
        assert findings[0].evidence["assigned_net"] == ("AUX_SHARED_NODE",)
    else:
        assert observed.nets["SUPPLY_SOURCE"] == ("J1.1",)
        assert observed.nets["RETURN_REFERENCE"] == ("J1.2",)
        assert not findings

    shield_coverage = signal_sharing_coverage(
        observed,
        signal_names=("SUPPLY_CONTACT", "CABLE_SHIELD"),
        roles=("supply", "shield"),
    )
    shield_report, _ = signal_sharing_report(observed, coverage=shield_coverage)
    shield_findings = tuple(
        item for item in shield_report.findings if item.rule_id == SUPPLY_SHIELD_RULE_ID
    )
    assert shield_coverage.status == "COMPLETE"
    if fixture_case.endswith("fault"):
        assert observed.nets["AUX_SHARED_NODE"] == ("J1.1", "J1.2")
        assert len(shield_findings) == 1
        assert shield_findings[0].evidence["interface_role"] == ("supply", "shield")
    else:
        assert observed.nets["SUPPLY_SOURCE"] == ("J1.1",)
        assert observed.nets["RETURN_REFERENCE"] == ("J1.2",)
        assert not shield_findings

    return_shield_coverage = signal_sharing_coverage(
        observed,
        signal_names=("SIGNAL_RETURN", "CABLE_SHIELD"),
        roles=("return", "shield"),
    )
    return_shield_report, _ = signal_sharing_report(observed, coverage=return_shield_coverage)
    return_shield_findings = tuple(
        item for item in return_shield_report.findings if item.rule_id == RETURN_SHIELD_RULE_ID
    )
    assert return_shield_coverage.status == "COMPLETE"
    if fixture_case.endswith("fault"):
        assert observed.nets["AUX_SHARED_NODE"] == ("J1.1", "J1.2")
        assert len(return_shield_findings) == 1
        assert return_shield_findings[0].evidence["interface_role"] == ("return", "shield")
    else:
        assert observed.nets["SUPPLY_SOURCE"] == ("J1.1",)
        assert observed.nets["RETURN_REFERENCE"] == ("J1.2",)
        assert not return_shield_findings

    split_coverage = signal_sharing_coverage(
        observed,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    split_report, _ = signal_sharing_report(observed, coverage=split_coverage)
    split_findings = tuple(
        item for item in split_report.findings if item.rule_id == SAME_DOMAIN_SUPPLY_SPLIT_RULE_ID
    )
    if fixture_case.endswith("control"):
        assert observed.nets["SUPPLY_SOURCE"] == ("J1.1",)
        assert observed.nets["RETURN_REFERENCE"] == ("J1.2",)
        assert len(split_findings) == 1
        assert split_findings[0].evidence["split_native_nets"] == (
            "RETURN_REFERENCE",
            "SUPPLY_SOURCE",
        )
    else:
        assert observed.nets["AUX_SHARED_NODE"] == ("J1.1", "J1.2")
        assert not split_findings

    return_coverage = signal_sharing_coverage(
        observed,
        signal_names=("RETURN_CONTACT_A", "RETURN_CONTACT_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    return_report, _ = signal_sharing_report(observed, coverage=return_coverage)
    return_findings = tuple(
        item for item in return_report.findings if item.rule_id == SAME_DOMAIN_RETURN_SPLIT_RULE_ID
    )
    # The shared-node fixture is a control for this split-net rule; the
    # separately assigned fixture is its fault, the inverse of LINT-371.
    if fixture_case.endswith("control"):
        assert observed.nets["SUPPLY_SOURCE"] == ("J1.1",)
        assert observed.nets["RETURN_REFERENCE"] == ("J1.2",)
        assert len(return_findings) == 1
        assert return_findings[0].evidence["split_native_nets"] == (
            "RETURN_REFERENCE",
            "SUPPLY_SOURCE",
        )
    else:
        assert observed.nets["AUX_SHARED_NODE"] == ("J1.1", "J1.2")
        assert not return_findings
