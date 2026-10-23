"""Review source-mapped connector shields assigned to return-labeled nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.connector_mapped_interface_support import interface_coverage
from tests.design_lint_fixtures.connector_mapped_named_rail import (
    mapped_named_rail_netlist,
    mapped_named_rail_report,
)
from tests.design_lint_fixtures.connector_mapped_other_named_rail import (
    native_return_board_coverage,
)
from tests.design_lint_fixtures.connector_return_cases import ret_return_label_case_contracts

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_shield_on_return_net"


def _report(
    source: NetlistContract,
    *,
    role: ConnectorPinRole = "shield",
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current_coverage = coverage or interface_coverage(source, target_role=role)
    return mapped_named_rail_report(
        source,
        role=role,
        coverage=current_coverage,
        policy=policy,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_shield_on_return_label_requests_review() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    report, coverage = _report(source)

    assert coverage.status == "COMPLETE"
    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.subject == ("J1.2: mapped shield contact is assigned to return-like net GND")
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("CHASSIS_SHIELD",),
        "interface_role": ("shield",),
        "interface_voltage_domain": ("chassis",),
        "native_pin_function": ("Pin_2",),
        "assigned_nets": ("GND",),
        "net_label_role_clue": ("return-like label",),
        "interface_catalog_sha256": ("b" * 64,),
    }
    assert "connecting this shield to the return-labeled net" in finding.message
    assert "do not prove a required bond" in finding.message


@pytest.mark.parametrize("net_name", ("GND", "0V", "DGND", "SIGNAL_RETURN", "RET"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_return_labels_are_review_clues(net_name: str) -> None:
    report, _coverage = _report(mapped_named_rail_netlist(target_net=net_name))

    assert len(_findings(report)) == 1
    assert _findings(report)[0].evidence["assigned_nets"] == (net_name,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_other_roles_and_ordinary_or_positive_labels_are_controls() -> None:
    ordinary_shield, _ = _report(mapped_named_rail_netlist(target_net="CHASSIS_SHIELD"))
    return_role, _ = _report(mapped_named_rail_netlist(target_net="GND"), role="return")
    signal_role, _ = _report(mapped_named_rail_netlist(target_net="RET"), role="signal")
    supply_role, _ = _report(mapped_named_rail_netlist(target_net="RET"), role="supply")
    positive_shield, _ = _report(mapped_named_rail_netlist(target_net="+5V"))
    dnp_shield, _ = _report(mapped_named_rail_netlist(target_net="GND", dnp=("J1",)))
    open_source = mapped_named_rail_netlist(target_net="GND")
    open_source = open_source.model_copy(
        update={
            "nets": {
                net: remaining
                for net, pins in open_source.nets.items()
                if (remaining := tuple(pin for pin in pins if pin != "J1.2"))
            }
        }
    )
    reasoned_open, reasoned_open_coverage = _report(
        open_source,
        coverage=interface_coverage(
            open_source,
            target_role="shield",
            unconnected_reason="Synthetic shield isolation is intentional.",
        ),
    )

    assert not _findings(ordinary_shield)
    assert not _findings(return_role)
    assert not _findings(signal_role)
    assert not _findings(supply_role)
    assert not _findings(positive_shield)
    assert not _findings(dnp_shield)
    assert reasoned_open_coverage.status == "COMPLETE"
    assert not _findings(reasoned_open)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_function_text_does_not_override_mapped_shield_role() -> None:
    report, _coverage = _report(
        mapped_named_rail_netlist(target_net="RET", target_function="SHIELD")
    )

    findings = _findings(report)
    assert len(findings) == 1
    assert findings[0].evidence["native_pin_function"] == ("SHIELD",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_digestless_and_multi_net_evidence_are_controls() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    complete = interface_coverage(source, target_role="shield")
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.2": "9"}}
    )
    stale, _ = _report(stale_source, coverage=complete)
    incomplete, _ = _report(
        source,
        coverage=complete.model_copy(update={"status": "INCOMPLETE"}),
    )
    digestless, _ = _report(
        source,
        coverage=complete.model_copy(update={"interface_catalog_sha256": None}),
    )
    multi_net_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.2",)}}
    )
    multi_net, _ = _report(multi_net_source)

    assert not _findings(stale)
    assert not _findings(incomplete)
    assert not _findings(digestless)
    assert not _findings(multi_net)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic mapped shields require reviewer disposition.",
                ),
            )
        ),
    )
    disabled, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed this optional heuristic.",
                ),
            )
        ),
    )
    ignored, _ = _report(
        source,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic project records the intentional shield bond.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_four_port_case_localizes_one_shield_map_mutation() -> None:
    observed = ret_return_label_case_contracts()["ret-control"]
    fault_coverage = native_return_board_coverage(
        observed,
        role_overrides={"J1.7": "shield"},
    )
    control_coverage = native_return_board_coverage(observed)
    fault, fault_coverage = mapped_named_rail_report(
        observed,
        role="shield",
        coverage=fault_coverage,
    )
    control, control_coverage = mapped_named_rail_report(
        observed,
        role="return",
        coverage=control_coverage,
    )

    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert [item.evidence["component_pin"] for item in _findings(fault)] == [("J1.7",)]
    assert not _findings(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    first = _findings(_report(source)[0])[0]
    second = _findings(_report(reordered)[0])[0]
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
