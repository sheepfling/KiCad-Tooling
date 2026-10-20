"""Focused connector coverage checks for a single review theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_return_role_catalog,
    connector_return_role_netlist,
    connector_return_role_reviews,
    inventory_review,
)

pytestmark = [
    pytest.mark.connector_lint,
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
]


def test_reviewed_return_roles_refine_connector_net_heuristics() -> None:
    def role_coverage(
        netlist: NetlistContract,
        *,
        catalog_sha256: str | None = "b" * 64,
    ) -> ConnectorCoverageReport:
        return evaluate(
            netlist,
            ("usb-interface", "serial-interface"),
            connector_return_role_reviews(),
            interfaces=connector_return_role_catalog(),
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256=catalog_sha256,
            inventory_review=inventory_review(),
        )

    split = connector_return_role_netlist()
    split_coverage = role_coverage(split)
    assert (split_coverage.status) == ("COMPLETE")
    assert (
        next(entry for entry in split_coverage.entries if entry.reference == "J2")
        .mapped_pins[2]
        .role
    ) == ("return")

    split_report = evaluate_design_lint(
        "synthetic-reviewed-return-split",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-return-split",
            observed=split,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=split_coverage,
    )
    assert (split_report.status) == ("REVIEW")
    return_finding = next(
        finding
        for finding in split_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert (dict(return_finding.evidence)) == (
        {
            "J1.3": ("USB_RETURN",),
            "J2.3": ("SERIAL_RETURN",),
            "role_classification_sources": (
                "J1.3: project interface catalog role=return; native symbol function=GND",
                "J2.3: project interface catalog role=return; native symbol function=Pin_3",
            ),
        }
    )
    assert ("role classification alone does not require commonality") in (return_finding.message)
    rendered_split = text_report(split_report)
    assert (f"Interface catalog: catalog/interfaces.json ({'b' * 64})") in (rendered_split)
    assert (
        "role_classification_sources: J1.3: project interface catalog role=return; "
        "native symbol function=GND, "
        "J2.3: project interface catalog role=return; native symbol function=Pin_3"
    ) in (rendered_split)
    assert ("Interface pin 3 (RETURN) maps to J2.3: role=return") in (rendered_split)
    assert ("connector.no_connected_return") not in (
        {finding.rule_id for finding in split_report.findings}
    )

    source_interfaces = connector_return_role_catalog()
    reordered_interfaces = {
        interface_id: interface.model_copy(update={"pins": tuple(reversed(interface.pins))})
        for interface_id, interface in reversed(tuple(source_interfaces.items()))
    }
    reordered_reviews = tuple(
        review.model_copy(
            update={
                "pin_map": dict(reversed(tuple(review.pin_map.items()))),
                "unlisted_pin_reasons": dict(reversed(tuple(review.unlisted_pin_reasons.items()))),
            }
        )
        for review in reversed(connector_return_role_reviews())
    )
    reordered_coverage = evaluate(
        split,
        ("serial-interface", "usb-interface"),
        reordered_reviews,
        interfaces=reordered_interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="b" * 64,
        inventory_review=inventory_review(),
    )
    reordered_report = evaluate_design_lint(
        "synthetic-reviewed-return-split",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-return-split",
            observed=split,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=reordered_coverage,
    )
    assert (reordered_coverage) == (split_coverage)
    assert (reordered_report) == (split_report)

    disabled_report = evaluate_design_lint(
        "synthetic-reviewed-return-split-disabled",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-return-split-disabled",
            observed=split,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.repeated_pin_function",
                    mode="off",
                    reason="Synthetic project intentionally isolates these interface returns",
                ),
            )
        ),
        connector_coverage=split_coverage,
    )
    assert (disabled_report.status) == ("PASS")
    assert (len(disabled_report.findings)) == (1)
    assert (disabled_report.findings[0].mode) == ("off")
    assert (disabled_report.findings[0].disposition) == ("RULE_OFF")

    unbound_catalog_report = evaluate_design_lint(
        "synthetic-unbound-return-catalog",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-unbound-return-catalog",
            observed=split,
            netlist_sha256="b" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=role_coverage(split, catalog_sha256=None),
    )
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in unbound_catalog_report.findings}
    )

    incomplete_coverage = split_coverage.model_copy(
        update={
            "status": "INCOMPLETE",
            "entries": tuple(
                entry.model_copy(update={"status": "INCOMPLETE"})
                for entry in split_coverage.entries
            ),
        }
    )
    incomplete_map_report = evaluate_design_lint(
        "synthetic-incomplete-return-map",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-incomplete-return-map",
            observed=split,
            netlist_sha256="b" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=incomplete_coverage,
    )
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in incomplete_map_report.findings}
    )

    common = connector_return_role_netlist(common_return=True)
    common_coverage = role_coverage(common)
    common_report = evaluate_design_lint(
        "synthetic-reviewed-common-return",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-common-return",
            observed=common,
            netlist_sha256="c" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=common_coverage,
    )
    assert (common_report.status) == ("PASS")
    assert not (common_report.findings)

    open_return = connector_return_role_netlist(common_return=True, open_return=True)
    open_return_report = evaluate_design_lint(
        "synthetic-reviewed-open-return",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-open-return",
            observed=open_return,
            netlist_sha256="e" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=role_coverage(open_return),
    )
    assert (open_return_report.status) == ("REVIEW")
    return_pin_finding = next(
        finding
        for finding in open_return_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert (return_pin_finding.evidence["J2.3"]) == (())
    assert ("connector.no_connected_return") not in (
        {finding.rule_id for finding in open_return_report.findings}
    )

    open_supply = connector_return_role_netlist(common_return=True, open_supply=True)
    open_supply_report = evaluate_design_lint(
        "synthetic-reviewed-open-supply",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-reviewed-open-supply",
            observed=open_supply,
            netlist_sha256="f" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=role_coverage(open_supply),
    )
    supply_pin_finding = next(
        finding
        for finding in open_supply_report.findings
        if finding.rule_id == "connector.unconnected_supply_pin"
    )
    assert (supply_pin_finding.subject) == ("J2.4: V+")
    assert (supply_pin_finding.evidence["role_source"]) == (("project interface catalog",))

    stale_netlist = common.model_copy(
        update={
            "nets": {
                "COMMON_RETURN": ("J1.3",),
                "SERIAL_RETURN": ("J2.3",),
                "USB_DATA_1": ("J1.1",),
                "USB_DATA_2": ("J1.2",),
                "SERIAL_TX": ("J2.1",),
                "SERIAL_RX": ("J2.2",),
                "SERIAL_SUPPLY": ("J2.4",),
            }
        }
    )
    stale_report = evaluate_design_lint(
        "synthetic-stale-return-coverage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-stale-return-coverage",
            observed=stale_netlist,
            netlist_sha256="d" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=common_coverage,
    )
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in stale_report.findings}
    )


def test_split_return_across_two_usb_and_one_serial_peer_group_is_reviewed() -> None:
    interfaces = connector_return_role_catalog()
    observed = NetlistContract(
        components={},
        nets={
            "USB1_D+": ("J1.1",),
            "USB1_D-": ("J1.2",),
            "SERIAL_TX": ("J2.1",),
            "SERIAL_RX": ("J2.2",),
            "COMMON_RETURN": ("J1.3", "J2.3"),
            "SERIAL_SUPPLY": ("J2.4",),
            "USB2_D+": ("J3.1",),
            "USB2_D-": ("J3.2",),
            "USB2_RETURN": ("J3.3",),
        },
        component_symbols={
            "J1": "Connector:USB_C_Receptacle_USB2.0_16P",
            "J2": "Connector:DB9",
            "J3": "Connector:USB_C_Receptacle_USB2.0_16P",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3"),
            "J2": ("1", "2", "3", "4"),
            "J3": ("1", "2", "3"),
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J2.1": "TX",
            "J2.2": "RX",
            "J2.3": "Pin_3",
            "J2.4": "Pin_4",
            "J3.1": "D+",
            "J3.2": "D-",
            "J3.3": "GND",
        },
    )
    peer_specs = (
        ("J1", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-1"),
        ("J2", "serial-interface", {"1": "1", "2": "2", "3": "3", "4": "4"}, "serial-port"),
        ("J3", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-2"),
    )

    def coverage(netlist: NetlistContract) -> ConnectorCoverageReport:
        reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis=f"Synthetic source review for {interface_id}",
                interface_id=interface_id,
                pin_map=pin_map,
                peer_assignment_group=group,
                peer_assignment_basis=f"Reviewed {reference} in group {group}",
            )
            for reference, interface_id, pin_map, group in peer_specs
        )
        return evaluate(
            netlist,
            ("usb-interface", "serial-interface"),
            reviews,
            interfaces=interfaces,
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="9" * 64,
            inventory_review=inventory_review(),
        )

    def report(netlist: NetlistContract, project_id: str):
        return evaluate_design_lint(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=netlist,
                netlist_sha256="8" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage(netlist),
        )

    split_report = report(observed, "synthetic-two-usb-one-serial-split-return")
    split_findings = tuple(
        finding
        for finding in split_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )

    assert split_report.status == "REVIEW"
    assert split_findings
    connector_pin_evidence = {
        pin
        for finding in split_findings
        for pin in finding.evidence
        if pin in {"J1.1", "J1.2", "J1.3", "J2.1", "J2.2", "J2.3", "J2.4", "J3.1", "J3.2", "J3.3"}
    }
    assert connector_pin_evidence == {
        "J1.3",
        "J2.3",
        "J3.3",
    }
    assert all(item.mode == "review" for item in split_findings)

    common_nets = {name: pins for name, pins in observed.nets.items() if name != "USB2_RETURN"}
    common_nets["COMMON_RETURN"] = ("J1.3", "J2.3", "J3.3")
    common = observed.model_copy(update={"nets": common_nets})
    common_report = report(common, "synthetic-two-usb-one-serial-common-return")
    assert not any(
        finding.rule_id == "connector.repeated_pin_function" for finding in common_report.findings
    )
