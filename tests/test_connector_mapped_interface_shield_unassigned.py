"""Review source-mapped shield contacts without a schematic net."""

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
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from tests.connector_mapped_interface_support import CATALOG_SHA256, interface_coverage
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_shield_unassigned"
PROJECT_ID = "synthetic-mapped-interface-shield"
NETLIST_SHA256 = "a" * 64
NATIVE_FAULT_CASE = "mapped-interface-shield-unassigned-fault"
NATIVE_CONTROL_CASE = "mapped-interface-shield-unassigned-control"
NATIVE_FIXTURE_CASES = (NATIVE_FAULT_CASE, NATIVE_CONTROL_CASE)
EXPECTED_NATIVE_SOURCE_HASHES = {
    NATIVE_FAULT_CASE: "ef64edfafefdc9e724474c5686d8638577ec1c1719883f3f34f8b365de068821",
    NATIVE_CONTROL_CASE: "1cf322d88271b585ae9e97e356f1078b8573a9a2cd25122caf3352a28ed3cd9d",
}


def _report(
    source: NetlistContract,
    *,
    target_role: ConnectorPinRole = "shield",
    unconnected_reason: str | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    coverage = interface_coverage(
        source,
        target_role=target_role,
        unconnected_reason=unconnected_reason,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=source,
        netlist_sha256=NETLIST_SHA256,
    )
    report = evaluate(PROJECT_ID, coach, policy or DesignLintPolicy(), connector_coverage=coverage)
    return report, coverage


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _shield_netlist(*, target_net: str | None = None, dnp: tuple[str, ...] = ()) -> NetlistContract:
    return mapped_interface_netlist(
        target_net=target_net,
        target_function="CHASSIS_SHIELD",
        target_type="passive",
        dnp=dnp,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_mapped_shield_contact_requests_review_with_source_evidence() -> None:
    report, coverage = _report(_shield_netlist())

    assert coverage.status == "COMPLETE"
    assert report.status == "REVIEW"
    finding = _findings(report)[0]
    assert finding.subject == "J1.2: reviewed shield contact has no net assignment"
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("CHASSIS_SHIELD",),
        "interface_role": ("shield",),
        "native_pin_function": ("CHASSIS_SHIELD",),
        "native_pin_electrical_type": ("passive",),
        "assigned_nets": (),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connected_reasoned_dnp_and_nonshield_contacts_are_controls() -> None:
    connected, _ = _report(_shield_netlist(target_net="CHASSIS"))
    reasoned, coverage = _report(
        _shield_netlist(),
        unconnected_reason="Reviewed as intentionally isolated from board ground",
    )
    dnp, _ = _report(_shield_netlist(dnp=("J1",)))
    signal_role, _ = _report(_shield_netlist(), target_role="signal")

    assert not _findings(connected)
    assert not _findings(reasoned)
    assert coverage.entries[0].mapped_pins[1].unconnected_reason == (
        "Reviewed as intentionally isolated from board ground"
    )
    assert not _findings(dnp)
    assert not _findings(signal_role)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_mismatched_or_digestless_coverage_cannot_trigger_review() -> None:
    source = _shield_netlist()
    coverage = interface_coverage(source, target_role="shield")
    changed_source = source.model_copy(update={"nets": {**source.nets, "CHASSIS": ("J1.2",)}})
    stale_report = evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=changed_source,
            netlist_sha256=NETLIST_SHA256,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    digestless_report = evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=source,
            netlist_sha256=NETLIST_SHA256,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
    )

    assert not _findings(stale_report)
    assert not _findings(digestless_report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_order_stable_and_connection_clears_it() -> None:
    source = _shield_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    first = _findings(_report(source)[0])[0]
    second = _findings(_report(reordered)[0])[0]
    connected, _ = _report(_shield_netlist(target_net="CHASSIS"))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert first.fingerprint == fingerprint(
        Candidate(
            rule_id=first.rule_id,
            subject=first.subject,
            message=first.message,
            evidence=dict(first.evidence),
        )
    )
    assert not _findings(connected)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_obeys_project_policy_and_exact_ignore() -> None:
    source = _shield_netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires shield contact disposition.",
                ),
            )
        ),
    )
    disabled, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project defers the optional shield review.",
                ),
            )
        ),
    )
    ignored, _ = _report(
        source,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic project records an intentional isolation choice.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)

    assert sources[NATIVE_FAULT_CASE] == (
        fixture_root / "mapped-interface-shield-native/fault.kicad_sch"
    )
    assert sources[NATIVE_CONTROL_CASE] == (
        fixture_root / "mapped-interface-shield-native/control.kicad_sch"
    )
    for case in NATIVE_FIXTURE_CASES:
        source = sources[case]
        expected = EXPECTED_NATIVE_SOURCE_HASHES[case]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == expected


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
def test_native_mapped_shield_contact_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.native_fixture_support import assert_native_fixture_mounts
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

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

    log = HostedLog(root, f"native-mapped-interface-shield-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=NATIVE_FIXTURE_CASES,
        stage_prefix="mapped-interface-shield-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-interface-shield-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_NATIVE_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    for case in NATIVE_FIXTURE_CASES:
        observed = context.observed_contracts[case, "first"]
        assert observed.component_pin_numbers["J1"] == ("1", "2")
        assert observed.pin_functions["J1.2"] == "CHASSIS_SHIELD"
        assert observed.pin_electrical_types["J1.2"] == "passive"
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )

        coverage = interface_coverage(
            observed,
            target_role="shield",
            pin_numbers=("1", "2"),
        )
        assert coverage.status == "COMPLETE"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=observed,
            netlist_sha256=context.netlist_hashes[case, "first"],
        )
        report = evaluate(
            PROJECT_ID,
            coach,
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        findings = _findings(report)
        if case == NATIVE_FAULT_CASE:
            assert report.status == "REVIEW"
            assert len(findings) == 1
            assert findings[0].evidence["native_pin_electrical_type"] == ("passive",)
            assert findings[0].evidence["assigned_nets"] == ()
        else:
            assert observed.nets["CHASSIS"] == ("J1.2",)
            assert not findings
