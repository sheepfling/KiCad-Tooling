"""Review generic connector pins assigned to an exact native UART pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import source_matched_connector_pin_evidence
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.serial_generic_connector_pair import (
    generic_serial_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.serial_generic_connector_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    netlist = observed or generic_serial_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-serial-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_pin_map() -> ConnectorCoverageReport:
    signals = (
        ("1", "UART_TX", "LINE_A"),
        ("2", "UART_RX", "LINE_B"),
        ("3", "GND", "BOARD_GND"),
        ("4", "3V3", "+3V3"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic UART connector inventory",
        project_interfaces=("synthetic-uart",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-uart",
                basis="Synthetic approved UART pin map",
                interface_pin_map={signal: number for number, signal, _ in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=("Pin_1", "Pin_2", "GND", "3V3")[int(number) - 1],
                        nets=(net,),
                    )
                    for number, signal, net in signals
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_native_uart_pair_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match UART TX/RX nets"
    assert finding.evidence["TX_net"] == ("LINE_A",)
    assert finding.evidence["TX_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["RX_net"] == ("LINE_B",)
    assert finding.evidence["RX_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["UART_endpoint_pairs"] == ("U1:default:TX=U1.1/LINE_A;RX=U1.2/LINE_B",)
    assert "does not infer connector purpose or signal direction from net labels" in finding.message
    assert "common grounds or power" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_roles_source_matched_map_and_not_applicable_suppress_review() -> None:
    named = generic_serial_connector_pair_netlist(connector_functions=("TXD", "RXD", "GND", "3V3"))
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    cases = (
        ("named pins", named, None),
        ("source-matched map", generic_serial_connector_pair_netlist(), _source_matched_pin_map()),
        ("not applicable", generic_serial_connector_pair_netlist(), not_applicable),
    )
    mapped_entry = cases[1][2].entries[0]
    assert mapped_entry.status == "COVERED"
    assert mapped_entry.interface_id is not None
    assert cases[1][2].interface_catalog_sha256 == "b" * 64
    assert mapped_entry.interface_pin_map == {
        "UART_TX": "1",
        "UART_RX": "2",
        "GND": "3",
        "3V3": "4",
    }
    assert len(mapped_entry.mapped_pins) == 4
    assert set(source_matched_connector_pin_evidence(cases[1][1], cases[1][2])) == {
        "J1.1",
        "J1.2",
        "J1.3",
        "J1.4",
    }
    for label, observed, coverage in cases:
        assert not any(
            item.rule_id == RULE_ID
            for item in _report(observed, connector_coverage=coverage).findings
        ), label

    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector map",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )
    assert any(
        item.rule_id == RULE_ID
        for item in _report(
            generic_serial_connector_pair_netlist(), connector_coverage=stale_map
        ).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_partial_dnp_incomplete_and_ambiguous_cases_stay_quiet() -> None:
    observed = generic_serial_connector_pair_netlist()
    ambiguous = observed.model_copy(update={"nets": {**observed.nets, "OTHER": ("J1.1",)}})
    same_net = observed.model_copy(
        update={"nets": {**observed.nets, "LINE_A": ("J1.1", "U1.1", "U1.2"), "LINE_B": ()}}
    )
    dnp_connector = observed.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = observed.model_copy(update={"dnp_components": ("U1",)})
    duplicate_tx = observed.model_copy(
        update={"pin_functions": {**observed.pin_functions, "U1.4": "TXD"}}
    )
    missing_endpoint_metadata = observed.model_copy(
        update={
            "pin_electrical_types": {
                key: value for key, value in observed.pin_electrical_types.items() if key != "U1.2"
            }
        }
    )

    cases = (
        generic_serial_connector_pair_netlist(include_rx_contact=False),
        ambiguous,
        same_net,
        dnp_connector,
        dnp_endpoint,
        duplicate_tx,
        missing_endpoint_metadata,
    )
    for case in cases:
        assert not any(item.rule_id == RULE_ID for item in _report(case).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    default = _finding(_report())
    blocked = _finding(
        _report(
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID, mode="block", reason="Synthetic policy control"
                    ),
                )
            )
        )
    )
    ignored = _report(
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default.fingerprint,
                    reason="Synthetic review",
                ),
            )
        )
    )

    assert default.mode == "review"
    assert blocked.mode == "block"
    assert _finding(ignored).disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_serial_connector_pair_netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    assert _report(observed) == _report(reordered)
