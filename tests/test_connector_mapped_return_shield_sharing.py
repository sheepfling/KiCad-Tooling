"""Review mapped connector return and shield contacts sharing a net."""

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
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_return_shield_share_net"


def _coverage(
    observed: NetlistContract,
    *,
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("return", "shield"),
    unconnected_pin_reasons: dict[str, str] | None = None,
) -> ConnectorCoverageReport:
    return signal_sharing_coverage(
        observed,
        signal_names=("SIGNAL_RETURN", "CABLE_SHIELD"),
        roles=roles,
        unconnected_pin_reasons=unconnected_pin_reasons,
    )


def _report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current_coverage = coverage if coverage is not None else _coverage(observed)
    report, _ = signal_sharing_report(observed, coverage=current_coverage, policy=policy)
    return report, current_coverage


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_return_and_shield_on_unclassified_shared_net_request_review() -> None:
    report, coverage = _report(signal_sharing_netlist())

    assert coverage.status == "COMPLETE"
    (finding,) = _findings(report)
    assert finding.subject == (
        "J1: mapped return and shield contacts share native net SHARED_SIGNAL_NET"
    )
    assert finding.evidence == {
        "component_reference": ("J1",),
        "interface_role": ("return", "shield"),
        "return_component_pin": ("J1.1",),
        "return_interface_signal": ("SIGNAL_RETURN",),
        "shield_component_pin": ("J1.2",),
        "shield_interface_signal": ("CABLE_SHIELD",),
        "assigned_net": ("SHARED_SIGNAL_NET",),
        "interface_catalog_sha256": ("c" * 64,),
    }
    assert "intentional" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_nets_and_other_role_pairs_are_controls() -> None:
    source = signal_sharing_netlist()
    separate, _ = _report(signal_sharing_netlist(first_net="SIGNAL_RETURN", second_net="CHASSIS"))
    supply_shield, _ = _report(source, coverage=_coverage(source, roles=("supply", "shield")))
    signal_shield, _ = _report(source, coverage=_coverage(source, roles=("signal", "shield")))

    assert not _findings(separate)
    assert not _findings(supply_shield)
    assert not _findings(signal_shield)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_and_incomplete_maps_are_controls() -> None:
    source = signal_sharing_netlist()
    coverage = _coverage(source)
    dnp, _ = _report(signal_sharing_netlist(dnp=("J1",)))
    reasoned_open, _ = _report(
        source,
        coverage=_coverage(
            source,
            unconnected_pin_reasons={"1": "Synthetic intentional return disconnect"},
        ),
    )
    ambiguous_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.1",)}}
    )
    ambiguous, _ = _report(ambiguous_source, coverage=_coverage(ambiguous_source))
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "Pin_9 altered"}}
    )
    stale, _ = _report(stale_source, coverage=coverage)
    incomplete, _ = _report(source, coverage=coverage.model_copy(update={"status": "INCOMPLETE"}))
    digestless, _ = _report(
        source,
        coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
    )

    assert not _findings(dnp)
    assert not _findings(reasoned_open)
    assert not _findings(ambiguous)
    assert not _findings(stale)
    assert not _findings(incomplete)
    assert not _findings(digestless)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_and_exact_ignore_apply() -> None:
    source = signal_sharing_netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic return/shield bond requires reviewer disposition.",
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
                    reason="Synthetic project disables this review prompt.",
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
                    reason="Synthetic chassis and return bond is intentional.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = signal_sharing_netlist()
    reordered = source.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(source.nets.items()))
            }
        }
    )

    assert _findings(_report(source)[0]) == _findings(_report(reordered)[0])
