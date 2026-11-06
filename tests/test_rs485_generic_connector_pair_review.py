"""Review generic connector contacts assigned to an identified RS-485 pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures.rs485_generic_connector_pair import (
    generic_rs485_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.rs485_generic_connector_pair_review"


def _report(
    observed=None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    netlist = observed or generic_rs485_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-rs485-generic-connector",
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


def _source_matched_pin_map() -> ConnectorCoverageReport:
    signals = (
        ("1", "RS485_A", "LINE_A"),
        ("2", "RS485_B", "LINE_B"),
        ("3", "SUPPLY", "+3V3"),
        ("4", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic RS-485 connector inventory",
        project_interfaces=("synthetic-rs485",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-rs485",
                basis="Synthetic approved RS-485 pin map",
                interface_pin_map={signal: number for number, signal, _net in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
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
def test_generic_contacts_on_exact_identified_rs485_pair_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match RS-485 A/B bus nets"
    assert finding.evidence["A_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["B_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["A_net"] == ("LINE_A",)
    assert finding.evidence["B_net"] == ("LINE_B",)
    assert finding.evidence["RS485_endpoint_pairs"] == ("U1:A=U1.1/LINE_A;B=U1.2/LINE_B",)
    assert "does not infer connector identity" in finding.message
    assert "require any return, shield, or supply contacts to be common" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_roles_and_source_matched_map_suppress_review() -> None:
    named = generic_rs485_connector_pair_netlist(
        connector_functions=("RS485_A", "RS485_B", "VCC", "GND")
    )
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_dnp_unsupported_and_ambiguous_shapes_stay_quiet() -> None:
    observed = generic_rs485_connector_pair_netlist()
    incomplete_endpoint = observed.model_copy(
        update={
            "pin_electrical_types": {
                pin: pin_type
                for pin, pin_type in observed.pin_electrical_types.items()
                if pin != "U1.4"
            }
        }
    )
    duplicate_role = generic_rs485_connector_pair_netlist(line_functions=("A", "A"))
    unsupported_identity = generic_rs485_connector_pair_netlist(
        identity="Generic differential line driver",
        endpoint_symbol="Synthetic:GenericLineDriver",
    )
    ambiguous = observed.model_copy(update={"nets": {**observed.nets, "OTHER": ("J1.1",)}})
    same_net = observed.model_copy(
        update={
            "nets": {
                "LINE_A": ("J1.1", "J1.2", "U1.1", "U1.2"),
                "BOARD_GND": observed.nets["BOARD_GND"],
                "+3V3": observed.nets["+3V3"],
            }
        }
    )
    one_sided = generic_rs485_connector_pair_netlist(include_b_contact=False)

    cases = (
        ("connector_dnp", generic_rs485_connector_pair_netlist(connector_dnp=True)),
        ("endpoint_dnp", generic_rs485_connector_pair_netlist(endpoint_dnp=True)),
        ("incomplete_endpoint_metadata", incomplete_endpoint),
        ("duplicate_role", duplicate_role),
        ("unsupported_identity", unsupported_identity),
        ("ambiguous_connector_assignment", ambiguous),
        ("same_net_endpoint", same_net),
        ("one_sided_connector_match", one_sided),
    )
    for label, candidate in cases:
        assert not any(item.rule_id == RULE_ID for item in _report(candidate).findings), label


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_not_applicable_disposition_named_functions_and_partial_map_are_controls() -> None:
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )
    named = generic_rs485_connector_pair_netlist(connector_functions=("A", "B", "VCC", "GND"))
    partial_map = _source_matched_pin_map().model_copy(
        update={
            "entries": (
                _source_matched_pin_map()
                .entries[0]
                .model_copy(
                    update={"mapped_pins": _source_matched_pin_map().entries[0].mapped_pins[:1]}
                ),
            )
        }
    )

    assert not any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=not_applicable).findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=partial_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires reviewed RS-485 connector pinouts",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID, mode="off", reason="This project has no RS-485 connectors"
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a non-RS-485 accessory connector",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_rs485_connector_pair_netlist()
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
