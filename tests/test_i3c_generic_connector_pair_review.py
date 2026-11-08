"""Review generic connector contacts assigned to recognized I3C pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.i3c_generic_connector_pair import (
    generic_i3c_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i3c_generic_connector_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    netlist = observed or generic_i3c_connector_pair_netlist()
    source = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i3c-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(source.project_id, source, policy, connector_coverage)


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_i3c_pin_map(*, scl_net: str = "I3C0_SCL") -> ConnectorCoverageReport:
    signals = (
        ("1", "I3C0_SDA", "I3C0_SDA"),
        ("2", "I3C0_SCL", "I3C0_SCL"),
        ("3", "3V3", "+3V3"),
        ("4", "GND", "BOARD_GND"),
        ("5", "AUX", ""),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic I3C connector inventory",
        project_interfaces=("synthetic-i3c",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-i3c",
                basis="Synthetic approved I3C pin map",
                interface_pin_map={signal: number for number, signal, _net in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(scl_net,) if signal == "I3C0_SCL" else (() if not net else (net,)),
                    )
                    for number, signal, net in signals
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_i3c_channel_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match I3C SDA/SCL bus nets"
    assert finding.evidence["SDA_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["SCL_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["SDA_net"] == ("I3C0_SDA",)
    assert finding.evidence["SCL_net"] == ("I3C0_SCL",)
    assert finding.evidence["I3C_endpoint_pairs"] == (
        "U1:I3C0 U1.1=SDA/I3C0_SDA;U1.2=SCL/I3C0_SCL",
    )
    assert finding.evidence["connector_map_state"] == (
        "no source-matched connector map confirms these exact I3C SDA/SCL pin assignments",
    )
    assert finding.evidence["other_connector_contacts"] == (
        "J1.3 function=Pin_3 nets=+3V3",
        "J1.4 function=Pin_4 nets=BOARD_GND",
        "J1.5 function=Pin_5 nets=unassigned",
    )
    assert "does not infer connector identity" in finding.message
    assert "require common grounds or power" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_roles_and_exact_source_matched_map_suppress_review() -> None:
    named = generic_i3c_connector_pair_netlist(
        connector_functions=("I3C0_SDA", "I3C0_SCL", "3V3", "GND", "AUX")
    )
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale I3C connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_i3c_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_contact_connector_is_left_to_missing_return_review() -> None:
    report = _report(generic_i3c_connector_pair_netlist(connector_functions=("Pin_1", "Pin_2")))

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert any(
        item.rule_id == "connector.i3c_pair_without_return_review" for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_sided_pair_dnp_and_incomplete_inventories_are_quiet() -> None:
    base = generic_i3c_connector_pair_netlist()
    cases = (
        generic_i3c_connector_pair_netlist(include_scl_contact=False),
        base.model_copy(update={"dnp_components": ("J1",)}),
        base.model_copy(update={"dnp_components": ("U1",)}),
        base.model_copy(
            update={
                "component_pin_numbers": {"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")}
            }
        ),
        base.model_copy(
            update={
                "pin_functions": {
                    pin: function
                    for pin, function in base.pin_functions.items()
                    if pin not in {"U1.1", "U1.2"}
                }
            }
        ),
    )

    for observed in cases:
        assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_assignments_same_net_endpoints_and_not_applicable_are_quiet() -> None:
    base = generic_i3c_connector_pair_netlist()
    ambiguous = base.model_copy(update={"nets": {**base.nets, "OTHER": ("J1.1",)}})
    same_net = base.model_copy(
        update={
            "nets": {
                **base.nets,
                "I3C0_SDA": ("J1.1", "J1.2", "U1.1", "U1.2"),
                "I3C0_SCL": (),
            }
        }
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed I3C connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(ambiguous).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(same_net).findings)
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
                reason="This project requires reviewed I3C connector pinouts",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID, mode="off", reason="This project has no I3C connectors"
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a non-I3C accessory connector",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_order_independent_and_source_map_requires_exact_nets() -> None:
    observed = generic_i3c_connector_pair_netlist()
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
    baseline = _finding(_report(observed))
    permuted = _finding(_report(reordered))
    assert baseline.evidence == permuted.evidence
    assert baseline.fingerprint == permuted.fingerprint

    wrong_net_map = _source_matched_i3c_pin_map(scl_net="OTHER")
    assert any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=wrong_net_map).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_other_contact_assignment_is_part_of_source_bound_finding() -> None:
    baseline = _finding(_report())
    assigned_aux = generic_i3c_connector_pair_netlist(other_contact_net="AUXILIARY")
    changed = _finding(_report(assigned_aux))

    assert baseline.evidence["other_connector_contacts"][-1] == (
        "J1.5 function=Pin_5 nets=unassigned"
    )
    assert changed.evidence["other_connector_contacts"][-1] == (
        "J1.5 function=Pin_5 nets=AUXILIARY"
    )
    assert baseline.fingerprint != changed.fingerprint
