"""Review generic connector contacts on Ethernet MDC/MDIO management nets."""

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
from tests.design_lint_fixtures.ethernet_management_generic_connector import (
    generic_ethernet_management_connector_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_management_generic_connector_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    netlist: NetlistContract = observed or generic_ethernet_management_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-ethernet-management-generic-connector",
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


def _source_matched_management_pin_map() -> ConnectorCoverageReport:
    pins = (
        ("1", "MDC", "ETH_MDC"),
        ("2", "MDIO", "ETH_MDIO"),
        ("3", "AUX_3", "PORT_AUX_3"),
        ("4", "AUX_4", "PORT_AUX_4"),
        ("5", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic Ethernet management connector inventory",
        project_interfaces=("synthetic-ethernet-management",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-ethernet-management",
                basis="Synthetic approved MDC/MDIO connector pinout",
                interface_pin_map={signal: number for number, signal, _net in pins},
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
def test_generic_contacts_on_exact_mdc_mdio_nets_emit_review() -> None:
    findings = _findings(_report())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "J1: generic pins match Ethernet MDC/MDIO management nets"
    assert finding.evidence["Ethernet_MDC_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["Ethernet_MDIO_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["Ethernet_management_endpoint_pairs"] == (
        "U1:U1.1=MDC/ETH_MDC;U1.2=MDIO/ETH_MDIO",
    )
    assert finding.mode == "review"
    assert "does not identify the connector's purpose" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_finding_includes_other_contacts_and_assignment_changes() -> None:
    finding = _findings(_report())[0]

    assert finding.evidence["other_connector_contacts"] == (
        "J1.3 function=Pin_3 nets=PORT_AUX_3",
        "J1.4 function=Pin_4 nets=PORT_AUX_4",
        "J1.5 function=Pin_5 nets=BOARD_GND",
    )

    changed = generic_ethernet_management_connector_netlist(
        connector_assignments={
            "1": "ETH_MDC",
            "2": "ETH_MDIO",
            "3": "PORT_AUX_3",
            "4": "PORT_AUX_4",
            "5": "AUX_RETURN",
        }
    )
    changed_finding = _findings(_report(changed))[0]

    assert changed_finding.evidence["other_connector_contacts"][-1] == (
        "J1.5 function=Pin_5 nets=AUX_RETURN"
    )
    assert changed_finding.fingerprint != finding.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_contacts_and_current_reviewed_pinout_are_quiet() -> None:
    named = generic_ethernet_management_connector_netlist(
        connector_functions=("MDC", "MDIO", "Pin_3", "Pin_4", "GND")
    )

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=_source_matched_management_pin_map()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_one_sided_dnp_ambiguous_and_same_net_cases_are_quiet() -> None:
    base = generic_ethernet_management_connector_netlist()
    one_sided = generic_ethernet_management_connector_netlist(
        connector_assignments={
            "1": "ETH_MDC",
            "2": "PORT_AUX_2",
            "3": "PORT_AUX_3",
            "4": "PORT_AUX_4",
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
    missing_connector_metadata = base.model_copy(
        update={
            "pin_functions": {
                pin: function for pin, function in base.pin_functions.items() if pin != "J1.5"
            }
        }
    )
    ambiguous_connector = base.model_copy(update={"nets": {**base.nets, "OTHER": ("J1.1",)}})
    same_net_endpoint = generic_ethernet_management_connector_netlist(
        endpoint_assignments={"1": "ETH_MDC", "2": "ETH_MDC", "3": "ETH_TX_P", "4": "ETH_TX_N"}
    )
    duplicate_endpoint_role = base.model_copy(
        update={"pin_functions": {**base.pin_functions, "U1.3": "MDC"}}
    )

    for observed in (
        one_sided,
        dnp_connector,
        dnp_endpoint,
        incomplete_connector,
        missing_endpoint_metadata,
        missing_connector_metadata,
        ambiguous_connector,
        same_net_endpoint,
        duplicate_endpoint_role,
    ):
        assert not _findings(_report(observed))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_not_applicable_stale_wrong_role_and_partial_maps_do_not_claim_coverage() -> None:
    correct = _source_matched_management_pin_map()
    entry = correct.entries[0]
    stale_pin = entry.mapped_pins[0].model_copy(update={"nets": ("OLD_MDC",)})
    stale = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (stale_pin, *entry.mapped_pins[1:])}),
            )
        }
    )
    wrong_role_pin = entry.mapped_pins[0].model_copy(update={"interface_signal": "MDIO"})
    wrong_role = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (wrong_role_pin, *entry.mapped_pins[1:])}),
            )
        }
    )
    partial = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(
                    update={
                        "interface_pin_map": {"MDC": "1", "MDIO": "2"},
                        "mapped_pins": entry.mapped_pins[:2],
                    }
                ),
            )
        }
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not _findings(_report(connector_coverage=correct))
    assert _findings(_report(connector_coverage=stale))
    assert _findings(_report(connector_coverage=wrong_role))
    assert _findings(_report(connector_coverage=partial))
    assert not _findings(_report(connector_coverage=not_applicable))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _findings(_report())[0]
    blocked = _findings(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires a reviewed management connector pinout",
            )
        )
    )[0]
    off = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This project has no external management connector",
        )
    )
    ignored = _findings(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a local PHY management fixture",
            )
        )
    )[0]

    assert blocked.mode == "block"
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_native_mappings_are_reordered() -> None:
    observed = generic_ethernet_management_connector_netlist()
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

    first, second = _findings(_report(observed)), _findings(_report(reordered))
    assert [(item.fingerprint, item.evidence) for item in second] == [
        (item.fingerprint, item.evidence) for item in first
    ]
