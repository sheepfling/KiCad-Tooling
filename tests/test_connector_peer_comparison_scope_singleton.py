"""Detect connector comparison scopes that isolate comparable peer contacts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
)
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_return_role_catalog,
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    inventory_review,
)
from tests.design_lint_fixtures.connector_mixed_return import (
    two_usb_one_serial_return_case,
)

RULE_ID = "connector.return_supply_scope_singleton"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    netlist: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    *,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate_design_lint(
        "synthetic-peer-comparison-scope-singleton",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-peer-comparison-scope-singleton",
            observed=netlist,
            netlist_sha256="c" * 64,
        ),
        DesignLintPolicy() if policy is None else policy,
        connector_coverage=coverage,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(finding for finding in report.findings if finding.rule_id == RULE_ID)


def test_scoped_return_peer_without_comparison_partner_is_reviewed() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            "J1": "usb-returns",
            "J2": "serial-return",
            "J3": "usb-returns",
        },
    )

    findings = _findings(_report(netlist, coverage))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "return: reviewed connector scope leaves a comparable reference without peers"
    )
    assert finding.evidence["comparable_references"] == ("J1", "J2", "J3")
    assert finding.evidence["isolated_references"] == ("J2",)
    assert finding.evidence["J1.3"] == ("COMMON_RETURN",)
    assert finding.evidence["J2.3"] == ("COMMON_RETURN",)
    assert finding.evidence["J3.3"] == ("COMMON_RETURN",)
    assert finding.evidence["interface_catalog_sha256"] == ("9" * 64,)
    assert "does not require a shared net" in finding.message


def test_one_shared_scope_keeps_common_return_control_quiet() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            reference: "external-returns" for reference in ("J1", "J2", "J3")
        },
    )

    assert not _findings(_report(netlist, coverage))


def test_singleton_supply_scopes_are_reviewed_with_common_scope_control() -> None:
    observed = connector_supply_role_netlist(common_supply=True)
    interfaces = connector_supply_role_catalog()

    def coverage_for(groups: dict[str, str]) -> ConnectorCoverageReport:
        reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis=f"Synthetic supply contact map for {reference}",
                interface_id=interface_id,
                pin_map={component_pin: component_pin},
                supply_comparison_group=groups[reference],
                supply_comparison_basis=f"Reviewed {reference} in {groups[reference]}",
            )
            for reference, interface_id, component_pin in (
                ("J1", "usb-power", "2"),
                ("J2", "serial-power", "5"),
            )
        )
        return evaluate_connector_coverage(
            observed,
            tuple(sorted(interfaces)),
            reviews,
            interfaces=interfaces,
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="b" * 64,
            inventory_review=inventory_review(),
        )

    isolated = _findings(
        _report(observed, coverage_for({"J1": "usb-supply", "J2": "serial-supply"}))
    )
    assert len(isolated) == 1
    assert isolated[0].evidence["comparison_role"] == ("supply in voltage domain external-5v",)
    assert isolated[0].evidence["isolated_references"] == ("J1", "J2")

    shared = coverage_for({"J1": "external-supply", "J2": "external-supply"})
    assert not _findings(_report(observed, shared))


def test_distinct_scopes_with_multiple_peers_each_are_quiet() -> None:
    netlist, _ = two_usb_one_serial_return_case(common_return=True)
    nets = dict(netlist.nets)
    nets.update(
        {
            "SERIAL2_TX": ("J4.1",),
            "SERIAL2_RX": ("J4.2",),
            "COMMON_RETURN": ("J1.3", "J2.3", "J3.3", "J4.3"),
            "SERIAL2_SUPPLY": ("J4.4",),
        }
    )
    four_peers = netlist.model_copy(
        update={
            "nets": nets,
            "component_symbols": {
                **netlist.component_symbols,
                "J4": "Connector:DB9",
            },
            "component_pin_numbers": {
                **netlist.component_pin_numbers,
                "J4": ("1", "2", "3", "4"),
            },
            "pin_functions": {
                **netlist.pin_functions,
                "J4.1": "TX",
                "J4.2": "RX",
                "J4.3": "Pin_3",
                "J4.4": "Pin_4",
            },
        }
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Synthetic source review for {interface_id}",
            interface_id=interface_id,
            pin_map=pin_map,
            return_comparison_group=scope,
            return_comparison_basis=f"Reviewed {reference} in group {scope}",
        )
        for reference, interface_id, pin_map, scope in (
            ("J1", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-returns"),
            (
                "J2",
                "serial-interface",
                {"1": "1", "2": "2", "3": "3", "4": "4"},
                "serial-returns",
            ),
            ("J3", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-returns"),
            (
                "J4",
                "serial-interface",
                {"1": "1", "2": "2", "3": "3", "4": "4"},
                "serial-returns",
            ),
        )
    )
    coverage = evaluate_connector_coverage(
        four_peers,
        ("usb-interface", "serial-interface"),
        reviews,
        interfaces=connector_return_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="9" * 64,
        inventory_review=inventory_review(),
    )

    assert not _findings(_report(four_peers, coverage))


def test_missing_or_stale_scopes_do_not_create_a_coverage_candidate() -> None:
    netlist, incomplete = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={"J1": "usb-returns", "J3": "usb-returns"},
    )
    assert not _findings(_report(netlist, incomplete))

    complete, stale = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={reference: "all-returns" for reference in ("J1", "J2", "J3")},
    )
    changed_nets = dict(complete.nets)
    changed_nets["REVISED_RETURN"] = changed_nets.pop("COMMON_RETURN")
    changed = complete.model_copy(update={"nets": changed_nets})
    assert not _findings(_report(changed, stale))


def test_project_policy_can_block_disable_or_ignore_scope_review() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            "J1": "usb-returns",
            "J2": "serial-return",
            "J3": "usb-returns",
        },
    )
    blocked = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Every scoped connector comparison must retain a peer",
            ),
        )
    )
    assert _report(netlist, coverage, policy=blocked).status == "FAIL"

    off = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="The isolated comparison scope has been reviewed",
            ),
        )
    )
    assert _findings(_report(netlist, coverage, policy=off))[0].disposition == "RULE_OFF"

    candidate = _findings(_report(netlist, coverage))[0]
    ignore = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=candidate.fingerprint,
                reason="The serial return is intentionally outside the USB peer scope",
            ),
        )
    )
    ignored = _report(netlist, coverage, policy=ignore)
    assert _findings(ignored)[0].disposition == "IGNORED"


def test_scope_candidate_is_stable_under_netlist_ordering() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            "J1": "usb-returns",
            "J2": "serial-return",
            "J3": "usb-returns",
        },
    )
    baseline = _findings(_report(netlist, coverage))[0]
    reordered_nets = dict(reversed(tuple(netlist.nets.items())))
    reordered = netlist.model_copy(
        update={
            "nets": reordered_nets,
            "component_symbols": dict(reversed(tuple(netlist.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(netlist.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(netlist.pin_functions.items()))),
        }
    )
    reordered_coverage = coverage.model_copy(update={"entries": tuple(reversed(coverage.entries))})
    changed = _findings(_report(reordered, reordered_coverage))[0]

    assert (
        baseline.subject,
        baseline.message,
        dict(baseline.evidence),
        baseline.fingerprint,
    ) == (
        changed.subject,
        changed.message,
        dict(changed.evidence),
        changed.fingerprint,
    )
