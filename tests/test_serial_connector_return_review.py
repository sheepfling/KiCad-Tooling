"""Review complete two-pin generic UART connectors without return roles."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
)
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.serial_connector_return import (
    two_pin_uart_connector_netlist,
    two_pin_uart_connector_return_map,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.serial_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_uart_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-uart-return",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage,
    )


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_generic_uart_connector_without_return_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: two-pin UART connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["TX_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["RX_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["UART_endpoint_pairs"] == ("U1:default:TX=U1.1/LINE_A;RX=U1.2/LINE_B",)
    assert "intentionally isolated" in finding.message
    assert "does not require connection to board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "return_function",
    ["GND", "SIGNAL_RETURN", "VSS", "GROUND"],
)
def test_connector_return_contact_stays_with_existing_role_rules(return_function: str) -> None:
    report = _report(two_pin_uart_connector_netlist(return_pin=return_function))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_open_return_role_is_left_to_existing_unconnected_return_review() -> None:
    observed = two_pin_uart_connector_netlist(return_pin="GND")
    nets = {
        name: tuple(pin for pin in pins if pin != "J1.3") for name, pins in observed.nets.items()
    }
    opened = observed.model_copy(
        update={"nets": {name: pins for name, pins in nets.items() if pins}}
    )

    report = _report(opened)

    assert not _findings(report)
    assert "connector.unconnected_return_pin" in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_uart_contacts_and_reviewed_maps_suppress_generic_pair_prompt() -> None:
    named = two_pin_uart_connector_netlist(connector_functions=("TXD", "RXD"))
    mapped = two_pin_uart_connector_return_map()
    mapped_return = two_pin_uart_connector_return_map(tx_contact_role="GND")
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed two-contact connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=mapped))
    assert not _findings(_report(connector_coverage=mapped_return))
    assert not _findings(_report(connector_coverage=not_applicable))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_more_than_two_pins_is_left_to_multiconductor_return_review() -> None:
    report = _report(two_pin_uart_connector_netlist(return_pin="AUX"))

    assert not _findings(report)
    assert "connector.no_connected_return" in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_ambiguous_and_dnp_inputs_stay_quiet() -> None:
    observed = two_pin_uart_connector_netlist()
    ambiguous = observed.model_copy(update={"nets": {**observed.nets, "OTHER": ("J1.1",)}})
    incomplete = observed.model_copy(
        update={"pin_electrical_types": {"J1.1": "passive", "J1.2": "passive"}}
    )
    dnp = observed.model_copy(update={"dnp_components": ("J1",)})
    wrong_pin_count = observed.model_copy(
        update={"component_pin_numbers": {**observed.component_pin_numbers, "J1": ("1", "2", "3")}}
    )

    for case in (ambiguous, incomplete, dnp, wrong_pin_count):
        assert not _findings(_report(case))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_and_exact_ignore_remain_available() -> None:
    finding = _findings(_report())[0]
    blocked = _report(
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project policy review",
                ),
            )
        )
    )
    ignored = _report(
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed two-wire interface",
                ),
            )
        )
    )

    assert _findings(blocked)[0].mode == "block"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_order_and_fingerprint_are_stable_under_mapping_reordering() -> None:
    observed = two_pin_uart_connector_netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    assert _findings(_report(observed)) == _findings(_report(reordered))
