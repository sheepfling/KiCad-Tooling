"""Review source-mapped generic supply and return contacts with no schematic net."""

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

RULE_ID = "connector.mapped_interface_power_contact_unassigned"
PROJECT_ID = "synthetic-mapped-interface-power-contact"
NETLIST_SHA256 = "a" * 64
NATIVE_FIXTURE_CASES = (
    "mapped-interface-signal-unassigned-fault",
    "mapped-interface-signal-unassigned-control",
)
EXPECTED_NATIVE_SOURCE_HASHES = {
    NATIVE_FIXTURE_CASES[0]: "8d7cad1a7b1b0579890e0e2ad06af3b18f192f2a0ecf9260ebc3cae78c8c0554",
    NATIVE_FIXTURE_CASES[1]: "634af7ee73a4cdbcc1a52967df2f08a0ca68b1a3100a8e13fef34225ef2eb6e1",
}


def _source(
    *,
    target_net: str | None = None,
    target_function: str = "Pin_2",
    target_type: str = "input",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    return mapped_interface_netlist(
        target_net=target_net,
        target_function=target_function,
        target_type=target_type,
        dnp=dnp,
    )


def _coverage(
    source: NetlistContract,
    *,
    role: ConnectorPinRole = "return",
    unconnected_reason: str | None = None,
    pin_numbers: tuple[str, ...] = ("1", "2", "3"),
) -> ConnectorCoverageReport:
    return interface_coverage(
        source,
        target_role=role,
        unconnected_reason=unconnected_reason,
        pin_numbers=pin_numbers,
    )


def _report(
    source: NetlistContract,
    *,
    role: ConnectorPinRole = "return",
    unconnected_reason: str | None = None,
    policy: DesignLintPolicy | None = None,
    coverage: ConnectorCoverageReport | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current_coverage = coverage or _coverage(
        source,
        role=role,
        unconnected_reason=unconnected_reason,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=source,
        netlist_sha256=NETLIST_SHA256,
    )
    report = evaluate(
        PROJECT_ID,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=current_coverage,
    )
    return report, current_coverage


def _findings(report: DesignLintReport):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_generic_mapped_supply_contact_requests_review() -> None:
    role: ConnectorPinRole = "supply"
    report, coverage = _report(_source(), role=role)

    assert coverage.status == "COMPLETE"
    assert report.status == "REVIEW"
    finding = _findings(report)[0]
    assert finding.subject == f"J1.2: reviewed {role} contact has no net assignment"
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("SUPPLY" if role == "supply" else "SIGNAL_RETURN",),
        "interface_role": (role,),
        "interface_voltage_domain": ("logic-supply" if role == "supply" else "signal-return",),
        "native_pin_function": ("Pin_2",),
        "native_pin_electrical_type": ("input",),
        "assigned_nets": (),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }


@pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function")
def test_open_mapped_return_contacts_are_reported_once_by_peer_rule() -> None:
    report, coverage = _report(_source(), role="return")

    assert coverage.status == "COMPLETE"
    assert not _findings(report)
    peer_findings = tuple(
        item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
    )
    assert len(peer_findings) == 1
    assert peer_findings[0].evidence["J1.2"] == ()
    assert peer_findings[0].evidence["J1.3"] == ("SIGNAL_RETURN",)


@pytest.mark.parametrize("role", ("supply", "return"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connected_and_reasoned_open_contacts_are_controls(role: ConnectorPinRole) -> None:
    connected, _ = _report(_source(target_net="REVIEWED_POWER_NET"), role=role)
    reasoned, coverage = _report(
        _source(),
        role=role,
        unconnected_reason="Reviewed as intentionally unconnected in this interface mode",
    )
    dnp, _ = _report(_source(dnp=("J1",)), role=role)
    other_role, _ = _report(_source(), role="signal")

    assert not _findings(connected)
    assert not _findings(reasoned)
    assert coverage.entries[0].mapped_pins[1].unconnected_reason == (
        "Reviewed as intentionally unconnected in this interface mode"
    )
    assert not _findings(dnp)
    assert not _findings(other_role)


@pytest.mark.parametrize("electrical_type", ("power_in", "power_out"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_mapped_role_reviews_open_native_power_types(
    electrical_type: str,
) -> None:
    report, _ = _report(_source(target_type=electrical_type), role="supply")

    assert len(_findings(report)) == 1
    assert _findings(report)[0].evidence["native_pin_electrical_type"] == (electrical_type,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_supply_function_stays_with_existing_specific_check() -> None:
    supply, _ = _report(_source(target_function="VCC"), role="supply")

    assert not _findings(supply)
    assert any(item.rule_id == "connector.unconnected_supply_pin" for item in supply.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_or_incomplete_interface_evidence_cannot_trigger_review() -> None:
    source = _source()
    coverage = _coverage(source)
    changed = source.model_copy(update={"nets": {**source.nets, "REVIEWED_POWER_NET": ("J1.2",)}})
    stale, _ = _report(changed, coverage=coverage)
    digestless_coverage = coverage.model_copy(update={"interface_catalog_sha256": None})
    digestless, _ = _report(source, coverage=digestless_coverage)
    incomplete_coverage = coverage.model_copy(update={"status": "INCOMPLETE"})
    incomplete, _ = _report(source, coverage=incomplete_coverage)

    assert not _findings(stale)
    assert not _findings(digestless)
    assert not _findings(incomplete)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_order_stable_and_clears_when_contact_is_assigned() -> None:
    source = _source()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    first = _findings(_report(source, role="supply")[0])[0]
    second = _findings(_report(reordered, role="supply")[0])[0]
    repaired, _ = _report(_source(target_net="REVIEWED_POWER_NET"), role="supply")

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert first.fingerprint == fingerprint(
        Candidate(
            rule_id=first.rule_id,
            subject=first.subject,
            message=first.message,
            evidence=dict(first.evidence),
        )
    )
    assert not _findings(repaired)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = _source()
    baseline = _findings(_report(source, role="supply")[0])[0]
    blocked, _ = _report(
        source,
        role="supply",
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic connector requires disposition of mapped power contacts.",
                ),
            )
        ),
    )
    disabled, _ = _report(
        source,
        role="supply",
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic connector defers this optional review.",
                ),
            )
        ),
    )
    ignored, _ = _report(
        source,
        role="supply",
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic interface records this contact as externally handled.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)

    assert sources[NATIVE_FIXTURE_CASES[0]] == (
        fixture_root / "mapped-interface-signal-native/fault.kicad_sch"
    )
    assert sources[NATIVE_FIXTURE_CASES[1]] == (
        fixture_root / "mapped-interface-signal-native/control.kicad_sch"
    )
    for case, expected in EXPECTED_NATIVE_SOURCE_HASHES.items():
        source = sources[case]
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
def test_native_mapped_power_contact_fault_and_control_are_repeatable(
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
    log = HostedLog(root, f"native-mapped-interface-power-contact-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=NATIVE_FIXTURE_CASES,
        stage_prefix="mapped-interface-power-contact-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-interface-power-contact-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_NATIVE_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    for role in ("supply", "return"):
        for case in NATIVE_FIXTURE_CASES:
            observed = context.observed_contracts[case, "first"]
            assert observed.component_pin_numbers["J1"] == ("1", "2")
            assert observed.pin_functions["J1.2"] == "2"
            assert observed.pin_electrical_types["J1.2"] == "input"
            assert (
                context.normalized_netlist_hashes[case, "first"]
                == context.normalized_netlist_hashes[case, "repeat"]
            )
            coverage = _coverage(observed, role=role, pin_numbers=("1", "2"))
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
            if case == NATIVE_FIXTURE_CASES[0]:
                assert report.status == "REVIEW"
                assert len(findings) == 1
                assert findings[0].evidence["interface_role"] == (role,)
                assert findings[0].evidence["assigned_nets"] == ()
            else:
                assert observed.nets["UART_RX"] == ("J1.2",)
                assert not findings
