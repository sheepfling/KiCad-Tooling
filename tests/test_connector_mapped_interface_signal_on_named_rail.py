"""Review mapped signal contacts assigned to named rail-like nets."""

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

RULE_ID = "connector.mapped_interface_signal_on_named_rail"


def _report(
    source: NetlistContract,
    *,
    role: ConnectorPinRole = "signal",
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
def test_generic_mapped_signal_on_named_rail_requests_review() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    report, coverage = _report(source)

    assert coverage.status == "COMPLETE"
    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.subject == ("J1.2: mapped signal contact is assigned to return-like net GND")
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("UART_RX",),
        "interface_role": ("signal",),
        "interface_voltage_domain": ("logic-3v3",),
        "native_pin_function": ("Pin_2",),
        "assigned_nets": ("GND",),
        "net_label_role_clue": ("return-like label",),
        "interface_catalog_sha256": ("b" * 64,),
    }
    assert "do not prove electrical potential" in finding.message


@pytest.mark.parametrize("net_name", ("+5V", "VBUS", "GND", "0V", "RET"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_supply_and_return_labels_are_review_clues(net_name: str) -> None:
    report, _coverage = _report(mapped_named_rail_netlist(target_net=net_name))

    finding = _findings(report)[0]
    expected = "supply-like label" if net_name in {"+5V", "VBUS"} else "return-like label"
    assert finding.evidence["net_label_role_clue"] == (expected,)
    assert finding.evidence["assigned_nets"] == (net_name,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unrelated_net_and_other_mapped_roles_are_controls() -> None:
    ordinary, _ = _report(mapped_named_rail_netlist(target_net="AUX_DATA"))
    return_source = mapped_named_rail_netlist(target_net="GND")
    mapped_return, _ = _report(return_source, role="return")
    supply_source = mapped_named_rail_netlist(target_net="+5V")
    mapped_supply, _ = _report(supply_source, role="supply")
    other_source = mapped_named_rail_netlist(target_net="GND")
    mapped_other, _ = _report(other_source, role="other")
    named_native_function, _ = _report(
        mapped_named_rail_netlist(target_net="GND", target_function="GND")
    )
    dnp, _ = _report(mapped_named_rail_netlist(target_net="GND", dnp=("J1",)))

    assert not _findings(ordinary)
    assert not _findings(mapped_return)
    assert not _findings(mapped_supply)
    assert not _findings(mapped_other)
    assert not _findings(named_native_function)
    assert not _findings(dnp)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_digestless_and_multi_net_evidence_are_controls() -> None:
    source = mapped_named_rail_netlist(target_net="GND")
    complete = interface_coverage(source, target_role="signal")
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
                    reason="Synthetic mapped contacts require reviewer disposition.",
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
                    reason="Synthetic project records the intentional signal strap.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_four_port_case_localizes_one_signal_role_map_mutation() -> None:
    observed = ret_return_label_case_contracts()["ret-control"]
    fault_coverage = native_return_board_coverage(
        observed,
        role_overrides={"J1.7": "signal"},
    )
    control_coverage = native_return_board_coverage(observed)
    fault, fault_coverage = mapped_named_rail_report(
        observed, role="signal", coverage=fault_coverage
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
