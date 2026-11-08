"""Review generic connector contacts sharing recognized Ethernet PHY data pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.ethernet_generic_connector import (
    generic_ethernet_connector_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_generic_connector_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    netlist: NetlistContract = observed or generic_ethernet_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-ethernet-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(coach.project_id, coach, policy, connector_coverage)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_ethernet_pin_map() -> ConnectorCoverageReport:
    pins = (
        ("1", "TDP", "ETH_TX_P"),
        ("2", "TDN", "ETH_TX_N"),
        ("3", "RDP", "ETH_RX_P"),
        ("4", "RDN", "ETH_RX_N"),
        ("5", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic Ethernet connector inventory",
        project_interfaces=("synthetic-ethernet",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-ethernet",
                basis="Synthetic approved Ethernet connector pinout",
                interface_pin_map={signal: number for number, signal, _ in pins},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, signal, net in pins
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_ethernet_tx_and_rx_pairs_emit_review() -> None:
    findings = _findings(_report())

    assert tuple(item.subject for item in findings) == (
        "J1: generic pins match Ethernet RX pair nets",
        "J1: generic pins match Ethernet TX pair nets",
    )
    tx = next(item for item in findings if item.evidence["Ethernet_pair_direction"] == ("TX",))
    assert tx.evidence["Ethernet_TX_positive_generic_connector_pins"] == ("J1.1",)
    assert tx.evidence["Ethernet_TX_negative_generic_connector_pins"] == ("J1.2",)
    assert tx.evidence["Ethernet_endpoint_pairs"] == ("U1:U1.1=TX+/ETH_TX_P;U1.2=TX-/ETH_TX_N",)
    assert tx.mode == "review"
    assert "does not identify the connector as Ethernet" in tx.message
    assert "determine whether magnetics or termination are required" in tx.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_findings_include_other_contacts_and_assignment_changes() -> None:
    baseline = _findings(_report())
    tx = next(item for item in baseline if item.evidence["Ethernet_pair_direction"] == ("TX",))

    assert tx.evidence["other_connector_contacts"] == (
        "J1.3 function=Pin_3 nets=ETH_RX_P",
        "J1.4 function=Pin_4 nets=ETH_RX_N",
        "J1.5 function=Pin_5 nets=BOARD_GND",
    )

    changed = generic_ethernet_connector_netlist(
        connector_assignments={
            "1": "ETH_TX_P",
            "2": "ETH_TX_N",
            "3": "ETH_RX_P",
            "4": "ETH_RX_N",
            "5": "AUX_RETURN",
        }
    )
    changed_tx = next(
        item
        for item in _findings(_report(changed))
        if item.evidence["Ethernet_pair_direction"] == ("TX",)
    )

    assert changed_tx.evidence["other_connector_contacts"][-1] == (
        "J1.5 function=Pin_5 nets=AUX_RETURN"
    )
    assert changed_tx.fingerprint != tx.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_roles_and_source_matched_pin_map_are_quiet() -> None:
    named_connector = generic_ethernet_connector_netlist(
        connector_functions=("TDP", "TDN", "RDP", "RDN", "GND")
    )

    assert not _findings(_report(named_connector))
    assert not _findings(_report(connector_coverage=_source_matched_ethernet_pin_map()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_one_sided_dnp_and_ambiguous_cases_are_quiet() -> None:
    base = generic_ethernet_connector_netlist()
    one_sided = generic_ethernet_connector_netlist(
        connector_assignments={
            "1": "ETH_TX_P",
            "2": "AUX",
            "3": "ETH_RX_P",
            "4": "AUX2",
            "5": "BOARD_GND",
        }
    )
    dnp_connector = base.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = base.model_copy(update={"dnp_components": ("U1",)})
    incomplete_connector = base.model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")}}
    )
    missing_endpoint_metadata = base.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in base.pin_electrical_types.items() if pin != "U1.2"
            }
        }
    )
    ambiguous_connector = base.model_copy(update={"nets": {**base.nets, "OTHER": ("J1.1",)}})
    same_net_endpoint = generic_ethernet_connector_netlist(
        endpoint_assignments={
            "1": "ETH_TX_P",
            "2": "ETH_TX_P",
            "3": "ETH_RX_P",
            "4": "ETH_RX_P",
        }
    )
    duplicate_endpoint_role = base.model_copy(
        update={
            "pin_functions": {**base.pin_functions, "U1.5": "TDP"},
            "pin_electrical_types": {**base.pin_electrical_types, "U1.5": "passive"},
            "component_pin_numbers": {
                **base.component_pin_numbers,
                "U1": ("1", "2", "3", "4", "5"),
            },
        }
    )

    controls = (
        ("one-sided connector contacts", one_sided),
        ("DNP connector", dnp_connector),
        ("DNP endpoint", dnp_endpoint),
        ("incomplete connector inventory", incomplete_connector),
        ("missing endpoint metadata", missing_endpoint_metadata),
        ("ambiguous connector contact", ambiguous_connector),
        ("same-net endpoint pairs", same_net_endpoint),
    )
    for name, observed in controls:
        assert not _findings(_report(observed)), name

    duplicate_role_findings = _findings(_report(duplicate_endpoint_role))
    assert tuple(item.evidence["Ethernet_pair_direction"] for item in duplicate_role_findings) == (
        ("RX",),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_not_applicable_connector_disposition_is_quiet() -> None:
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not _findings(_report(connector_coverage=not_applicable))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _findings(_report())[0]
    blocked = _findings(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires reviewed Ethernet connector pinouts",
            )
        )
    )[0]
    off = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This project contains no Ethernet interfaces",
        )
    )
    ignored = _findings(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a local PHY test connector",
            )
        )
    )[0]

    assert blocked.mode == "block"
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_map_must_cover_exact_pair_roles_and_current_nets() -> None:
    correct = _source_matched_ethernet_pin_map()
    entries = list(correct.entries)
    entry = entries[0]
    stale_pin = entry.mapped_pins[0].model_copy(update={"nets": ("OLD_NET",)})
    stale = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (stale_pin, *entry.mapped_pins[1:])}),
            )
        }
    )
    wrong_role_pin = entry.mapped_pins[0].model_copy(update={"interface_signal": "RDP"})
    wrong_role = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (wrong_role_pin, *entry.mapped_pins[1:])}),
            )
        }
    )

    assert not _findings(_report(connector_coverage=correct))
    assert _findings(_report(connector_coverage=stale))
    assert _findings(_report(connector_coverage=wrong_role))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_native_mappings_are_reordered() -> None:
    observed = generic_ethernet_connector_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    first = _findings(_report(observed))
    second = _findings(_report(reordered))
    assert tuple((item.subject, item.evidence, item.fingerprint) for item in second) == tuple(
        (item.subject, item.evidence, item.fingerprint) for item in first
    )
