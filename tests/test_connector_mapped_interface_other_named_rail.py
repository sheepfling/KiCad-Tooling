"""Review mapped-other connector contacts assigned to named rail-like nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
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
from tests.connector_mapped_interface_support import interface_coverage
from tests.design_lint_fixtures.connector_mapped_other_named_rail import (
    mapped_other_named_rail_netlist,
    mapped_other_named_rail_report,
    native_return_board_coverage,
)
from tests.design_lint_fixtures.connector_return_cases import ret_return_label_case_contracts

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_other_named_rail"


def _netlist(
    *,
    target_net: str = "GND",
    target_function: str = "2",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    return mapped_other_named_rail_netlist(
        target_net=target_net, target_function=target_function, dnp=dnp
    )


def _report(
    source: NetlistContract | None = None,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    observed = source or _netlist()
    return mapped_other_named_rail_report(observed, coverage=coverage, policy=policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_other_contact_on_single_return_label_requests_review() -> None:
    report, coverage = _report(_netlist(target_net="RET_USB"))

    assert coverage.status == "COMPLETE"
    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.subject == "J1.2: generic other contact is assigned to return-like net RET_USB"
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("OTHER",),
        "interface_role": ("other",),
        "native_pin_function": ("2",),
        "assigned_nets": ("RET_USB",),
        "net_label_role_clue": ("return-like label",),
        "interface_catalog_sha256": ("b" * 64,),
    }
    assert "net.return_labels_without_pin_roles" not in {item.rule_id for item in report.findings}
    assert "connector.mapped_interface_other_unassigned" not in {
        item.rule_id for item in report.findings
    }
    assert "does not prove" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_four_db9_map_role_change_localizes_one_generic_contact() -> None:
    observed = ret_return_label_case_contracts()["ret-control"]
    fault_coverage = native_return_board_coverage(observed, other_pins=frozenset({"J1.7"}))
    control_coverage = native_return_board_coverage(observed)
    fault, fault_coverage = mapped_other_named_rail_report(observed, coverage=fault_coverage)
    control, control_coverage = mapped_other_named_rail_report(observed, coverage=control_coverage)

    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert [item.evidence["component_pin"] for item in _findings(fault)] == [("J1.7",)]
    assert not _findings(control)
    assert "net.return_labels_without_pin_roles" not in {item.rule_id for item in fault.findings}


@pytest.mark.parametrize("net_name", ("+5V", "VBUS", "GND", "0V", "RET"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_only_recognized_supply_or_return_labels_are_review_clues(net_name: str) -> None:
    report, _coverage = _report(_netlist(target_net=net_name))

    finding = _findings(report)[0]
    expected_clue = "supply-like label" if net_name in {"+5V", "VBUS"} else "return-like label"
    assert finding.evidence["net_label_role_clue"] == (expected_clue,)
    assert finding.evidence["assigned_nets"] == (net_name,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordinary_net_and_explicit_or_mapped_roles_are_controls() -> None:
    source = _netlist(target_net="AUX_DATA")
    ordinary, _ = _report(source)
    named_function, _ = _report(_netlist(target_function="GND"))
    mapped_return, _ = _report(
        source,
        coverage=interface_coverage(source, target_role="return"),
    )
    mapped_supply_source = _netlist(target_net="+5V")
    mapped_supply, _ = _report(
        mapped_supply_source,
        coverage=interface_coverage(mapped_supply_source, target_role="supply"),
    )
    dnp, _ = _report(_netlist(dnp=("J1",)))

    assert not _findings(ordinary)
    assert not _findings(named_function)
    assert not _findings(mapped_return)
    assert not _findings(mapped_supply)
    assert not _findings(dnp)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_digestless_and_multi_net_evidence_are_controls() -> None:
    source = _netlist()
    complete = interface_coverage(source, target_role="other")
    changed_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.2": "9"}}
    )
    multi_net = source.model_copy(update={"nets": {**source.nets, "AUX": ("J1.2",)}})

    stale, _ = _report(changed_source, coverage=complete)
    incomplete, _ = _report(coverage=complete.model_copy(update={"status": "INCOMPLETE"}))
    digestless, _ = _report(coverage=complete.model_copy(update={"interface_catalog_sha256": None}))
    multiply_assigned, _ = _report(multi_net)

    assert not _findings(stale)
    assert not _findings(incomplete)
    assert not _findings(digestless)
    assert not _findings(multiply_assigned)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = _netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires explicit connector roles.",
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
                    reason="Synthetic project does not use this optional review.",
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
                    reason="Synthetic project records the reviewed connector role.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = _netlist()
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
