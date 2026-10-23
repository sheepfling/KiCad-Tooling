"""Review open generic connector contacts mapped to the other interface role."""

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
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import NetlistContract
from tests.connector_mapped_interface_support import CATALOG_SHA256, interface_coverage
from tests.design_lint_fixtures.connector_mapped_interface_other import (
    mapped_interface_other_report,
)
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_other_unassigned"
NATIVE_FAULT_CASE = "mapped-interface-signal-unassigned-fault"
NATIVE_CONTROL_CASE = "mapped-interface-signal-unassigned-control"
NATIVE_FIXTURE_CASES = (NATIVE_FAULT_CASE, NATIVE_CONTROL_CASE)
EXPECTED_NATIVE_SOURCE_HASHES = {
    NATIVE_FAULT_CASE: "8d7cad1a7b1b0579890e0e2ad06af3b18f192f2a0ecf9260ebc3cae78c8c0554",
    NATIVE_CONTROL_CASE: "634af7ee73a4cdbcc1a52967df2f08a0ca68b1a3100a8e13fef34225ef2eb6e1",
}


def _netlist(
    *,
    target_net: str | None = None,
    target_function: str = "2",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    return mapped_interface_netlist(
        target_net=target_net,
        target_function=target_function,
        target_type="input",
        dnp=dnp,
    )


def _report(
    source: NetlistContract | None = None,
    *,
    unconnected_reason: str | None = None,
    policy: DesignLintPolicy | None = None,
    coverage: ConnectorCoverageReport | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    observed = source or _netlist()
    return mapped_interface_other_report(
        observed,
        coverage=coverage,
        unconnected_reason=unconnected_reason,
        policy=policy,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_generic_other_contact_requests_review_with_source_evidence() -> None:
    report, coverage = _report()

    assert coverage.status == "COMPLETE"
    assert report.status == "REVIEW"
    finding = _findings(report)[0]
    assert finding.subject == "J1.2: reviewed connector contact has no net or open disposition"
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("OTHER",),
        "interface_role": ("other",),
        "native_pin_function": ("2",),
        "assigned_nets": (),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connected_reasoned_dnp_and_ineligible_contacts_are_controls() -> None:
    connected, _ = _report(_netlist(target_net="AUXILIARY"))
    reasoned, coverage = _report(unconnected_reason="Reviewed as intentionally unused")
    dnp, _ = _report(_netlist(dnp=("J1",)))
    named, _ = _report(_netlist(target_function="RESERVED"))
    signal_role_coverage = interface_coverage(_netlist(), target_role="signal")
    signal_role, _ = _report(_netlist(), coverage=signal_role_coverage)

    assert not _findings(connected)
    assert not _findings(reasoned)
    assert coverage.entries[0].mapped_pins[1].unconnected_reason == (
        "Reviewed as intentionally unused"
    )
    assert not _findings(dnp)
    assert not _findings(named)
    assert not _findings(signal_role)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_or_incomplete_interface_evidence_cannot_trigger_review() -> None:
    source = _netlist()
    coverage = interface_coverage(source, target_role="other")
    changed = source.model_copy(update={"pin_functions": {**source.pin_functions, "J1.2": "9"}})
    stale, _ = _report(changed, coverage=coverage)
    incomplete, _ = _report(coverage=coverage.model_copy(update={"status": "INCOMPLETE"}))
    digestless, _ = _report(coverage=coverage.model_copy(update={"interface_catalog_sha256": None}))

    assert not _findings(stale)
    assert not _findings(incomplete)
    assert not _findings(digestless)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_order_stable_and_clears_when_connected() -> None:
    source = _netlist()
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
    connected, _ = _report(_netlist(target_net="AUXILIARY"))

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
    source = _netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires every contact to have a disposition.",
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
                    reason="Synthetic project defers this optional review.",
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
                    reason="Synthetic project records an intentional unused contact.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_fault_and_control_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)

    assert sources[NATIVE_FAULT_CASE] == (
        fixture_root / "mapped-interface-signal-native/fault.kicad_sch"
    )
    assert sources[NATIVE_CONTROL_CASE] == (
        fixture_root / "mapped-interface-signal-native/control.kicad_sch"
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
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_other_contact_fault_and_control_are_repeatable(
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

    log = HostedLog(root, f"native-mapped-interface-other-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=NATIVE_FIXTURE_CASES,
        stage_prefix="mapped-interface-other-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-interface-other-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_NATIVE_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    for case in NATIVE_FIXTURE_CASES:
        observed = context.observed_contracts[case, "first"]
        assert observed.component_pin_numbers["J1"] == ("1", "2")
        assert observed.pin_functions["J1.2"] == "2"
        assert observed.pin_electrical_types["J1.2"] == "input"
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )

        coverage = interface_coverage(
            observed,
            target_role="other",
            pin_numbers=("1", "2"),
        )
        report, coverage = mapped_interface_other_report(observed, coverage=coverage)
        assert coverage.status == "COMPLETE"
        findings = _findings(report)
        if case == NATIVE_FAULT_CASE:
            assert len(findings) == 1
            assert findings[0].evidence["component_pin"] == ("J1.2",)
        else:
            assert findings == ()
