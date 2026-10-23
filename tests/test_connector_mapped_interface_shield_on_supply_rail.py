"""Review mapped connector shields assigned to named supply-like rails."""

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

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_shield_on_supply_rail"


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
def test_mapped_shield_on_supply_label_requests_review() -> None:
    report, coverage = _report(mapped_named_rail_netlist(target_net="+5V"))

    assert coverage.status == "COMPLETE"
    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.subject == ("J1.2: mapped shield contact is assigned to supply-like net +5V")
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("CHASSIS_SHIELD",),
        "interface_role": ("shield",),
        "interface_voltage_domain": ("chassis",),
        "native_pin_function": ("Pin_2",),
        "assigned_nets": ("+5V",),
        "net_label_role_clue": ("supply-like label",),
        "interface_catalog_sha256": ("b" * 64,),
    }
    assert "do not prove actual voltage or a wiring defect" in finding.message
    assert "does not prescribe shield bonding" in finding.message


@pytest.mark.parametrize("net_name", ("+5V", "+3V3", "VBUS", "VCC", "-12V"))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_recognized_supply_labels_request_review(net_name: str) -> None:
    report, _coverage = _report(mapped_named_rail_netlist(target_net=net_name))

    assert len(_findings(report)) == 1
    assert _findings(report)[0].evidence["assigned_nets"] == (net_name,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_function_text_does_not_override_mapped_shield_role() -> None:
    report, _coverage = _report(
        mapped_named_rail_netlist(target_net="VBUS", target_function="POWER_IN")
    )

    assert len(_findings(report)) == 1
    assert _findings(report)[0].evidence["native_pin_function"] == ("POWER_IN",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_non_supply_labels_and_other_mapped_roles_are_controls() -> None:
    ordinary, _ = _report(mapped_named_rail_netlist(target_net="CHASSIS_SHIELD"))
    return_net, _ = _report(mapped_named_rail_netlist(target_net="GND"))
    return_role, _ = _report(mapped_named_rail_netlist(target_net="+5V"), role="return")
    signal_role, _ = _report(mapped_named_rail_netlist(target_net="+5V"), role="signal")
    supply_role, _ = _report(mapped_named_rail_netlist(target_net="+5V"), role="supply")
    dnp, _ = _report(mapped_named_rail_netlist(target_net="+5V", dnp=("J1",)))

    assert not _findings(ordinary)
    assert not _findings(return_net)
    assert not _findings(return_role)
    assert not _findings(signal_role)
    assert not _findings(supply_role)
    assert not _findings(dnp)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_digestless_and_multi_net_evidence_are_controls() -> None:
    source = mapped_named_rail_netlist(target_net="+5V")
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
    source = mapped_named_rail_netlist(target_net="+5V")
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
                    reason="Synthetic project records an intentional shield rail connection.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = mapped_named_rail_netlist(target_net="+5V")
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    original, _ = _report(source)
    shuffled, _ = _report(reordered)

    assert _findings(original) == _findings(shuffled)
