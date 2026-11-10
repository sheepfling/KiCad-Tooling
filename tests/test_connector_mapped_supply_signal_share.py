"""Review a mapped connector supply and signal assigned to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures.connector_mapped_supply_signal_sharing import (
    supply_signal_coverage,
    supply_signal_netlist,
    supply_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_supply_signal_share_net"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    return supply_signal_report(source, coverage=coverage, policy=policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_supply_and_signal_on_same_net_request_review() -> None:
    report, coverage = _report(supply_signal_netlist())

    assert coverage.status == "COMPLETE"
    (finding,) = _findings(report)
    assert finding.subject == "J1: mapped supply and signal contacts share native net SHARED_NET"
    assert finding.evidence == {
        "component_reference": ("J1",),
        "supply_component_pin": ("J1.1",),
        "supply_interface_signal": ("SUPPLY_IN",),
        "signal_component_pin": ("J1.2",),
        "signal_interface_signal": ("DATA_IN",),
        "interface_role": ("supply", "signal"),
        "assigned_net": ("SHARED_NET",),
        "interface_catalog_sha256": ("d" * 64,),
    }
    assert "do not prove" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_nets_and_non_supply_signal_role_pairs_are_controls() -> None:
    separate, _ = _report(supply_signal_netlist(supply_net="SUPPLY_NET", signal_net="DATA_NET"))
    return_signal, _ = _report(
        supply_signal_netlist(),
        coverage=supply_signal_coverage(supply_signal_netlist(), roles=("return", "signal")),
    )
    supply_only, _ = _report(
        supply_signal_netlist(),
        coverage=supply_signal_coverage(supply_signal_netlist(), roles=("supply", "supply")),
    )

    assert not _findings(separate)
    assert not _findings(return_signal)
    assert not _findings(supply_only)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_and_incomplete_maps_are_controls() -> None:
    source = supply_signal_netlist()
    coverage = supply_signal_coverage(source)
    dnp, _ = _report(supply_signal_netlist(dnp=("J1",)))
    open_coverage = supply_signal_coverage(
        source,
        unconnected_pin_reasons={"1": "Synthetic intentional open disposition"},
    )
    reasoned_open, _ = _report(source, coverage=open_coverage)
    multi_net_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.1",)}}
    )
    ambiguous, _ = _report(multi_net_source)
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "1 altered"}}
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
def test_review_policy_and_exact_ignore_apply() -> None:
    source = supply_signal_netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic shared supply/signal assignment is explicitly blocking.",
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
                    reason="Synthetic project explicitly disables this heuristic.",
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
                    reason="This connector intentionally uses a shared contact net.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = supply_signal_netlist()
    reordered = source.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(source.nets.items()))
            }
        }
    )

    assert _findings(_report(source)[0]) == _findings(_report(reordered)[0])
