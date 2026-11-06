"""Review generic connector contacts sharing a recognized CANH/CANL pair."""

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
from tests.design_lint_fixtures.can_generic_connector_pair import (
    generic_can_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.can_generic_connector_pair_review"


def _report(
    observed=None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    netlist = observed or generic_can_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-can-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(coach.project_id, coach, policy, connector_coverage)


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_can_pin_map() -> ConnectorCoverageReport:
    signals = (
        ("1", "VBUS", "+3V3"),
        ("2", "CANH", "CAN_H"),
        ("3", "CANL", "CAN_L"),
        ("4", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic CAN connector inventory",
        project_interfaces=("synthetic-can",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-can",
                basis="Synthetic approved CAN pin map",
                interface_pin_map={f"CAN_{signal}": number for number, signal, _ in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=f"CAN_{signal}",
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, signal, net in signals
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_fitted_can_pair_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match CANH/CANL bus nets"
    assert finding.evidence["CANH_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["CANL_generic_connector_pins"] == ("J1.3",)
    assert finding.evidence["CANH_net"] == ("CAN_H",)
    assert finding.evidence["CANL_net"] == ("CAN_L",)
    assert "does not infer connector identity" in finding.message
    assert "does not infer" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_roles_and_source_matched_maps_suppress_review() -> None:
    named = generic_can_connector_pair_netlist(connector_functions=("VBUS", "CANH", "CANL", "GND"))
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_can_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_pairs_dnp_and_incomplete_endpoint_inventory_are_quiet() -> None:
    incomplete_pair = generic_can_connector_pair_netlist(include_canl_contact=False)
    dnp = generic_can_connector_pair_netlist().model_copy(update={"dnp_components": ("J1",)})
    incomplete_endpoint = generic_can_connector_pair_netlist().model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2", "3", "4"), "U1": ("1", "2")}}
    )
    missing_pin_metadata = generic_can_connector_pair_netlist().model_copy(
        update={"pin_functions": {"J1.2": "Pin_2", "J1.3": "Pin_3"}}
    )

    for observed in (incomplete_pair, dnp, incomplete_endpoint, missing_pin_metadata):
        assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_connector_assignment_and_explicit_not_applicable_are_quiet() -> None:
    observed = generic_can_connector_pair_netlist()
    ambiguous = observed.model_copy(
        update={"nets": {**generic_can_connector_pair_netlist().nets, "OTHER": ("J1.2",)}}
    )
    same_net_endpoint = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "CAN_H": ("J1.2", "J1.3", "U1.1", "U1.2"),
                "CAN_L": (),
            }
        }
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(ambiguous).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(same_net_endpoint).findings)
    assert not any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=not_applicable).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires reviewed CAN connector pinouts",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID, mode="off", reason="This project has no CAN connectors"
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a non-CAN accessory connector",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_can_connector_pair_netlist()
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
