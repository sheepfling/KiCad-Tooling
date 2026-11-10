"""Review mapped return domains assigned to one native net."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import InterfacePin, InterfaceRecord, NetlistContract
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id="connector.mapped_return_domains_share_net"),
]

RULE_ID = "connector.mapped_return_domains_share_net"


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _two_connector_return_case(
    *,
    first_domain: str = "signal-return",
    second_domain: str = "chassis-return",
    second_net: str = "SHARED_RETURN_NET",
) -> tuple[NetlistContract, ConnectorCoverageReport]:
    observed = NetlistContract(
        components={},
        nets={
            "SHARED_RETURN_NET": ("J1.1",)
            + (("J2.1",) if second_net == "SHARED_RETURN_NET" else ()),
            **({second_net: ("J2.1",)} if second_net != "SHARED_RETURN_NET" else {}),
        },
        component_symbols={
            "J1": "Connector_Generic:Conn_01x01",
            "J2": "Connector_Generic:Conn_01x01",
        },
        component_pin_numbers={"J1": ("1",), "J2": ("1",)},
        pin_functions={"J1.1": "Pin_1", "J2.1": "Pin_1"},
        pin_electrical_types={"J1.1": "passive", "J2.1": "passive"},
    )
    interfaces = {
        "signal-return-port": InterfaceRecord(
            id="signal-return-port",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="SIGNAL_RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain=first_domain,
                    mating="SIGNAL_RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
        "chassis-return-port": InterfaceRecord(
            id="chassis-return-port",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="CHASSIS_RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain=second_domain,
                    mating="CHASSIS_RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
    }
    coverage = evaluate_connector_coverage(
        observed,
        tuple(sorted(interfaces)),
        (
            ConnectorInterfaceReview(
                reference="J1",
                disposition="interface",
                basis="Synthetic reviewed peer connector pinout",
                interface_id="signal-return-port",
                pin_map={"1": "1"},
            ),
            ConnectorInterfaceReview(
                reference="J2",
                disposition="interface",
                basis="Synthetic reviewed peer connector pinout",
                interface_id="chassis-return-port",
                pin_map={"1": "1"},
            ),
        ),
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered both connector references"
        ),
    )
    return observed, coverage


def test_distinct_mapped_return_domains_on_one_net_request_review() -> None:
    source = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SIGNAL_RETURN", "CHASSIS_RETURN"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )

    report, coverage = signal_sharing_report(source, coverage=coverage)

    assert coverage.status == "COMPLETE"
    (finding,) = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "SHARED_SIGNAL_NET: mapped connector return domains share one native net"
    )
    assert finding.evidence["native_shared_net"] == ("SHARED_SIGNAL_NET",)
    assert finding.evidence["interface_role"] == ("return",)
    assert finding.evidence["reviewed_voltage_domains"] == ("chassis-return", "signal-return")
    assert finding.evidence["mapped_return_assignments"] == (
        "J1.2=SHARED_SIGNAL_NET; voltage_domain=chassis-return",
        "J1.1=SHARED_SIGNAL_NET; voltage_domain=signal-return",
    )
    assert "do not establish" in finding.message


def test_distinct_return_domains_on_separate_connectors_sharing_one_net_request_review() -> None:
    observed, coverage = _two_connector_return_case()

    report, coverage = signal_sharing_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    assert _finding(report).evidence["mapped_return_assignments"] == (
        "J2.1=SHARED_RETURN_NET; voltage_domain=chassis-return",
        "J1.1=SHARED_RETURN_NET; voltage_domain=signal-return",
    )


def test_two_connector_same_domain_or_separate_net_assignments_are_controls() -> None:
    same_domain, same_domain_coverage = _two_connector_return_case(
        first_domain="signal-return",
        second_domain="signal-return",
    )
    same_domain_report, _ = signal_sharing_report(same_domain, coverage=same_domain_coverage)
    assert not tuple(item for item in same_domain_report.findings if item.rule_id == RULE_ID)

    separate_net, separate_net_coverage = _two_connector_return_case(second_net="J2_RETURN")
    separate_net_report, _ = signal_sharing_report(separate_net, coverage=separate_net_coverage)
    assert not tuple(item for item in separate_net_report.findings if item.rule_id == RULE_ID)


def test_same_return_domain_and_separate_return_nets_are_controls() -> None:
    same_domain = signal_sharing_netlist()
    same_domain_coverage = signal_sharing_coverage(
        same_domain,
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    same_domain_report, _ = signal_sharing_report(same_domain, coverage=same_domain_coverage)
    assert not tuple(item for item in same_domain_report.findings if item.rule_id == RULE_ID)

    separate_nets = signal_sharing_netlist(first_net="RETURN_A", second_net="RETURN_B")
    separate_coverage = signal_sharing_coverage(
        separate_nets,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    separate_report, _ = signal_sharing_report(separate_nets, coverage=separate_coverage)
    assert not tuple(item for item in separate_report.findings if item.rule_id == RULE_ID)


def test_supply_domains_do_not_emit_the_return_domain_rule() -> None:
    source = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        source,
        roles=("supply", "supply"),
        voltage_domains=("logic-5v", "external-5v"),
    )

    report, _ = signal_sharing_report(source, coverage=coverage)

    assert not tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert tuple(
        item
        for item in report.findings
        if item.rule_id == "connector.mapped_supply_domains_share_net"
    )


def test_stale_incomplete_digestless_ambiguous_open_and_dnp_maps_do_not_prompt() -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    changed_source = signal_sharing_netlist(first_net="CHANGED_RETURN_NET")
    stale_report, _ = signal_sharing_report(changed_source, coverage=coverage)
    assert not tuple(item for item in stale_report.findings if item.rule_id == RULE_ID)

    incomplete_coverage = coverage.model_copy(
        update={
            "entries": tuple(
                entry.model_copy(update={"status": "INCOMPLETE"}) for entry in coverage.entries
            )
        }
    )
    incomplete_report, _ = signal_sharing_report(observed, coverage=incomplete_coverage)
    assert not tuple(item for item in incomplete_report.findings if item.rule_id == RULE_ID)

    digestless_coverage = coverage.model_copy(update={"interface_catalog_sha256": None})
    digestless_report, _ = signal_sharing_report(observed, coverage=digestless_coverage)
    assert not tuple(item for item in digestless_report.findings if item.rule_id == RULE_ID)

    ambiguous = observed.model_copy(
        update={
            "nets": {
                "SHARED_SIGNAL_NET": ("J1.1", "J1.2"),
                "ALTERNATE_RETURN_NET": ("J1.1",),
            }
        }
    )
    ambiguous_coverage = signal_sharing_coverage(
        ambiguous,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    ambiguous_report, _ = signal_sharing_report(ambiguous, coverage=ambiguous_coverage)
    assert not tuple(item for item in ambiguous_report.findings if item.rule_id == RULE_ID)

    dnp = observed.model_copy(update={"dnp_components": ("J1",)})
    dnp_coverage = signal_sharing_coverage(
        dnp,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    dnp_report, _ = signal_sharing_report(dnp, coverage=dnp_coverage)
    assert not tuple(item for item in dnp_report.findings if item.rule_id == RULE_ID)

    open_coverage = signal_sharing_coverage(
        observed,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
        unconnected_pin_reasons={"1": "unused by this interface", "2": "unused by this interface"},
    )
    open_report, _ = signal_sharing_report(observed, coverage=open_coverage)
    assert not tuple(item for item in open_report.findings if item.rule_id == RULE_ID)


def test_project_policy_can_block_disable_or_exactly_ignore_the_review() -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    blocked, _ = signal_sharing_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="The project requires return-domain merges to be reviewed",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert _finding(blocked).disposition == "OPEN"

    disabled, _ = signal_sharing_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Reviewed as an intentional common reference",
                ),
            )
        ),
    )
    assert _finding(disabled).disposition == "RULE_OFF"

    review, _ = signal_sharing_report(observed, coverage=coverage)
    finding = _finding(review)
    ignored, _ = signal_sharing_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="The reviewed connector pinout intentionally joins these returns",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert _finding(ignored).disposition == "IGNORED"


def test_typed_return_source_projection_rejects_changed_netlist() -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    _report, coverage = signal_sharing_report(observed, coverage=coverage)
    from kicad_tooling.hwrepo.design_lint_connector_domain_shared_net_candidate_evidence import (
        MappedConnectorDomainsCandidate,
    )
    from kicad_tooling.hwrepo.design_lint_connectors_return_domains_shared_net import (
        mapped_return_domains_shared_net_candidates,
    )

    (candidate,) = mapped_return_domains_shared_net_candidates(observed, coverage)
    assert isinstance(candidate, MappedConnectorDomainsCandidate)
    assert isinstance(candidate, Candidate)
    with pytest.raises(ValueError, match="current source netlist"):
        replace(
            candidate.source_evidence,
            observed=signal_sharing_netlist(first_net="CHANGED_RETURN_NET"),
        )


def test_return_domain_review_is_deterministic_under_input_ordering() -> None:
    observed = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        observed,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    baseline, _ = signal_sharing_report(observed, coverage=coverage)
    reordered = observed.model_copy(update={"nets": {"SHARED_SIGNAL_NET": ("J1.2", "J1.1")}})
    reordered_coverage = signal_sharing_coverage(
        reordered,
        roles=("return", "return"),
        voltage_domains=("signal-return", "chassis-return"),
    )
    reordered_report, _ = signal_sharing_report(reordered, coverage=reordered_coverage)
    baseline_finding = _finding(baseline)
    reordered_finding = _finding(reordered_report)

    assert reordered_finding.model_dump(mode="json") == baseline_finding.model_dump(mode="json")
