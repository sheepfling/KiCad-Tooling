"""Review generic two-contact CAN connectors without an identified return."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.can_generic_connector_pair import can_connector_return_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]

RULE_ID = "connector.can_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    netlist = observed or can_connector_return_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-can-connector-return",
        observed=netlist,
        netlist_sha256="c" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(coach.project_id, coach, policy, connector_coverage)


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_can_pin_map() -> ConnectorCoverageReport:
    pins = (
        ("1", "CANH", "CAN_H"),
        ("2", "CANL", "CAN_L"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic two-contact CAN interface",
        project_interfaces=("synthetic-can",),
        inventory_review_basis="Synthetic reviewed CAN connector pinout",
        interface_catalog_sha256="d" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-can",
                basis="Synthetic approved two-line CAN pinout",
                interface_pin_map={f"CAN_{role}": number for number, role, _net in pins},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=f"CAN_{role}",
                        interface_signal=role,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, role, net in pins
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_generic_can_pair_without_return_emits_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: two-pin CAN connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["CANH_net"] == ("CAN_H",)
    assert finding.evidence["CANH_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["CANL_net"] == ("CAN_L",)
    assert finding.evidence["CANL_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["CAN_endpoint_pairs"] == ("U1:U1.1=CANH/CAN_H;U1.2=CANL/CAN_L",)
    assert "does not require connection to board ground" in finding.message
    assert "intentionally isolated" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_roles_and_current_source_matched_map_are_review_controls() -> None:
    named = can_connector_return_netlist(connector_functions=("CANH", "CANL"))
    stale = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Stale synthetic CAN interface",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_can_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_extra_native_return_contact_is_left_to_existing_multiconductor_rules() -> None:
    observed = can_connector_return_netlist(with_return_contact=True)

    assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_endpoint_or_connector_pair_and_dnp_are_quiet() -> None:
    observed = can_connector_return_netlist()
    incomplete_endpoint = observed.model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2"), "U1": ("1", "2")}}
    )
    incomplete_connector = observed.model_copy(
        update={"pin_functions": {"J1.1": "Pin_1", "U1.1": "CANH", "U1.2": "CANL"}}
    )
    dnp = observed.model_copy(update={"dnp_components": ("J1",)})
    one_line = can_connector_return_netlist(include_canl_contact=False)

    for item in (incomplete_endpoint, incomplete_connector, dnp, one_line):
        assert not any(finding.rule_id == RULE_ID for finding in _report(item).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_assignment_and_not_applicable_disposition_are_quiet() -> None:
    observed = can_connector_return_netlist()
    ambiguous = observed.model_copy(update={"nets": {**observed.nets, "OTHER": ("J1.1",)}})
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Reviewed synthetic inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(ambiguous).findings)
    assert not any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=not_applicable).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_exact_ignore_and_fingerprint_are_stable() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires a reviewed CAN connector reference decision",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID, mode="off", reason="The project has no external CAN interface"
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="The two-wire interface is explicitly reviewed as isolated",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"
    assert ignored.fingerprint == base.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_evidence_is_order_stable() -> None:
    observed = can_connector_return_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    first = _finding(_report(observed))
    second = _finding(_report(reordered))
    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
