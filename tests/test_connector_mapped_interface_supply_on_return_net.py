"""Review source-mapped supply contacts assigned to return-labeled nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import NetlistContract
from tests.connector_mapped_interface_support import CATALOG_SHA256, interface_coverage
from tests.design_lint_fixtures.connector_mapped_other_named_rail import (
    native_return_board_coverage,
)
from tests.design_lint_fixtures.connector_mapped_supply_return_net import (
    mapped_supply_return_net_netlist,
    mapped_supply_return_net_report,
)
from tests.design_lint_fixtures.connector_return_cases import ret_return_label_case_contracts

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_supply_on_return_net"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    role: ConnectorPinRole = "supply",
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current_coverage = coverage or interface_coverage(source, target_role=role)
    return mapped_supply_return_net_report(source, coverage=current_coverage, policy=policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_mapped_supply_on_return_label_requests_review() -> None:
    source = mapped_supply_return_net_netlist(target_net="RET")
    report, coverage = _report(source)

    assert coverage.status == "COMPLETE"
    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.subject == ("J1.2: mapped supply contact is assigned to return-like net RET")
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("SUPPLY",),
        "interface_role": ("supply",),
        "interface_voltage_domain": ("logic-supply",),
        "native_pin_function": ("Pin_2",),
        "assigned_nets": ("RET",),
        "net_label_role_clue": ("return-like label",),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }
    assert "do not prove electrical potential" in finding.message


@pytest.mark.parametrize("net_name", ("GND", "0V", "DGND", "SIGNAL_RETURN", "RET"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_return_labels_are_review_clues(net_name: str) -> None:
    report, _coverage = _report(mapped_supply_return_net_netlist(target_net=net_name))

    assert len(_findings(report)) == 1
    assert _findings(report)[0].evidence["assigned_nets"] == (net_name,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordinary_or_supply_labels_and_other_mapped_roles_are_controls() -> None:
    ordinary, _ = _report(mapped_supply_return_net_netlist(target_net="AUX_DATA"))
    positive, _ = _report(mapped_supply_return_net_netlist(target_net="+5V"))
    return_role, _ = _report(mapped_supply_return_net_netlist(target_net="GND"), role="return")
    other_role, _ = _report(mapped_supply_return_net_netlist(target_net="GND"), role="other")

    assert not _findings(ordinary)
    assert not _findings(positive)
    assert not _findings(return_role)
    assert not _findings(other_role)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_native_supply_function_stays_with_existing_specific_rule() -> None:
    report, _coverage = _report(
        mapped_supply_return_net_netlist(target_net="GND", target_function="VCC")
    )

    assert not _findings(report)
    assert any(item.rule_id == "power.pin_function_net_role_conflict" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_stale_incomplete_digestless_and_multi_net_cases_are_controls() -> None:
    source = mapped_supply_return_net_netlist(target_net="GND")
    complete = interface_coverage(source, target_role="supply")
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
    dnp, _ = _report(mapped_supply_return_net_netlist(target_net="GND", dnp=("J1",)))
    multi_net_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.2",)}}
    )
    multi_net, _ = _report(multi_net_source)

    assert not _findings(stale)
    assert not _findings(incomplete)
    assert not _findings(digestless)
    assert not _findings(dnp)
    assert not _findings(multi_net)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = mapped_supply_return_net_netlist(target_net="GND")
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic power-contact conflicts require reviewer disposition.",
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
                    reason="Synthetic project reviewed this optional map check.",
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
                    reason="Synthetic project recorded the pin-map disposition.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_four_port_case_localizes_one_supply_role_map_mutation() -> None:
    observed = ret_return_label_case_contracts()["ret-control"]
    fault_coverage = native_return_board_coverage(
        observed,
        role_overrides={"J1.7": "supply"},
    )
    control_coverage = native_return_board_coverage(observed)
    fault, fault_coverage = mapped_supply_return_net_report(
        observed,
        coverage=fault_coverage,
    )
    control, control_coverage = mapped_supply_return_net_report(
        observed,
        coverage=control_coverage,
    )

    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert [item.evidence["component_pin"] for item in _findings(fault)] == [("J1.7",)]
    assert _findings(fault)[0].evidence["assigned_nets"] == ("RET",)
    assert not _findings(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = mapped_supply_return_net_netlist(target_net="RET")
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
    assert first.fingerprint == fingerprint(
        Candidate(
            rule_id=first.rule_id,
            subject=first.subject,
            message=first.message,
            evidence=dict(first.evidence),
        )
    )
