"""Review complete connector supply mappings that share a native net."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfaceRecord,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
)

RULE_ID = "connector.mapped_supply_domains_share_net"
_INTERFACE_CATALOG_PATH = "catalog/interfaces.json"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _coverage(
    observed: NetlistContract,
    *,
    serial_voltage_domain: str = "serial-vbus",
    reviews: tuple[ConnectorInterfaceReview, ...] | None = None,
    interfaces: Mapping[str, InterfaceRecord] | None = None,
) -> ConnectorCoverageReport:
    selected_interfaces = (
        connector_supply_role_catalog(serial_voltage_domain=serial_voltage_domain)
        if interfaces is None
        else interfaces
    )
    return evaluate_connector_coverage(
        observed,
        tuple(sorted(selected_interfaces)),
        connector_supply_role_reviews() if reviews is None else reviews,
        interfaces=selected_interfaces,
        interface_catalog_path=_INTERFACE_CATALOG_PATH,
        interface_catalog_sha256="d" * 64,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered every connector in this fixture"
        ),
    )


def _report(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    *,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate_design_lint(
        "synthetic-supply-domain-net-sharing",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-supply-domain-net-sharing",
            observed=observed,
            netlist_sha256="e" * 64,
        ),
        DesignLintPolicy() if policy is None else policy,
        connector_coverage=coverage,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(finding for finding in report.findings if finding.rule_id == RULE_ID)


def test_distinct_mapped_supply_domains_on_one_net_prompt_review() -> None:
    observed = connector_supply_role_netlist(common_supply=True)
    report = _report(observed, _coverage(observed))

    assert report.status == "REVIEW"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "SHARED_SUPPLY: mapped connector supply domains share one native net"
    assert finding.evidence["native_shared_net"] == ("SHARED_SUPPLY",)
    assert finding.evidence["reviewed_voltage_domains"] == ("external-5v", "serial-vbus")
    assert finding.evidence["mapped_supply_assignments"] == (
        "J1.2=SHARED_SUPPLY; voltage_domain=external-5v",
        "J2.5=SHARED_SUPPLY; voltage_domain=serial-vbus",
    )
    assert finding.evidence["J1.2"] == ("SHARED_SUPPLY",)
    assert finding.evidence["J2.5"] == ("SHARED_SUPPLY",)
    assert finding.evidence["interface_catalog_sha256"] == ("d" * 64,)
    assert finding.evidence["interface_catalog_path"] == (_INTERFACE_CATALOG_PATH,)
    assert "do not establish different nominal voltages" in finding.message


def test_intentional_same_domain_and_distinct_net_controls_are_quiet() -> None:
    common_net = connector_supply_role_netlist(common_supply=True)
    same_domain_coverage = _coverage(
        common_net,
        serial_voltage_domain="external-5v",
    )
    assert not _findings(_report(common_net, same_domain_coverage))

    distinct_nets = connector_supply_role_netlist()
    distinct_domain_coverage = _coverage(distinct_nets)
    assert not _findings(_report(distinct_nets, distinct_domain_coverage))


def test_stale_or_missing_source_matched_maps_do_not_prompt() -> None:
    mapped_source = connector_supply_role_netlist(common_supply=True)
    stale_coverage = _coverage(mapped_source)
    changed_netlist = connector_supply_role_netlist()

    assert not _findings(_report(changed_netlist, stale_coverage))
    assert not _findings(_report(mapped_source, None))


def test_multiply_assigned_and_dnp_supply_contacts_are_skipped() -> None:
    common_netlist = connector_supply_role_netlist(common_supply=True)
    multiply_assigned = common_netlist.model_copy(
        update={
            "nets": {
                "SHARED_SUPPLY": ("J1.2", "J2.5"),
                "ALTERNATE_SUPPLY": ("J2.5",),
            }
        }
    )
    ambiguous_coverage = _coverage(multiply_assigned)
    assert not _findings(_report(multiply_assigned, ambiguous_coverage))

    dnp_connector = common_netlist.model_copy(update={"dnp_components": ("J2",)})
    dnp_coverage = _coverage(dnp_connector)
    assert not _findings(_report(dnp_connector, dnp_coverage))


def test_project_policy_can_block_disable_or_ignore_the_review() -> None:
    observed = connector_supply_role_netlist(common_supply=True)
    coverage = _coverage(observed)
    blocked_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires connector supply-domain merges to be resolved",
            ),
        )
    )
    blocked_report = _report(observed, coverage, policy=blocked_policy)
    assert blocked_report.status == "FAIL"
    assert _findings(blocked_report)[0].disposition == "OPEN"

    off_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="This project reviewed the shared connector supply node",
            ),
        )
    )
    disabled_findings = _findings(_report(observed, coverage, policy=off_policy))
    assert len(disabled_findings) == 1
    assert disabled_findings[0].disposition == "RULE_OFF"

    candidate = _findings(_report(observed, coverage))[0]
    exact_ignore = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=candidate.fingerprint,
                reason="The two mapped interfaces intentionally share this reviewed node",
            ),
        )
    )
    ignored_report = _report(observed, coverage, policy=exact_ignore)
    assert ignored_report.status == "PASS"
    assert _findings(ignored_report)[0].disposition == "IGNORED"


def test_finding_is_stable_under_netlist_and_review_ordering() -> None:
    observed = connector_supply_role_netlist(common_supply=True)
    coverage = _coverage(observed)
    baseline = _findings(_report(observed, coverage))
    reordered_observed = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    reordered_coverage = _coverage(
        reordered_observed,
        reviews=tuple(reversed(connector_supply_role_reviews())),
        interfaces=dict(
            reversed(
                tuple(connector_supply_role_catalog(serial_voltage_domain="serial-vbus").items())
            )
        ),
    )
    reordered = _findings(_report(reordered_observed, reordered_coverage))

    assert len(baseline) == len(reordered) == 1
    assert (
        baseline[0].subject,
        baseline[0].message,
        dict(baseline[0].evidence),
        baseline[0].fingerprint,
    ) == (
        reordered[0].subject,
        reordered[0].message,
        dict(reordered[0].evidence),
        reordered[0].fingerprint,
    )
