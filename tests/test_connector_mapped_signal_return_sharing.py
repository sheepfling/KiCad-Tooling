"""Review source-mapped connector signal and return contacts sharing a net."""

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
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_signal_return_share_net"


def _coverage(
    source: NetlistContract,
    *,
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("return", "signal"),
) -> ConnectorCoverageReport:
    return signal_sharing_coverage(
        source,
        signal_names=("SIGNAL_RETURN", "UART_RX"),
        roles=roles,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current = coverage if coverage is not None else _coverage(source)
    return signal_sharing_report(source, coverage=current, policy=policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_signal_sharing_a_return_net_requests_review() -> None:
    report, coverage = _report(signal_sharing_netlist())

    assert coverage.status == "COMPLETE"
    (finding,) = _findings(report)
    assert finding.subject == (
        "mapped return contacts J1.1 and signal contacts J1.2 share native net "
        "SHARED_SIGNAL_NET"
    )
    assert finding.evidence == {
        "return_component_pin": ("J1.1",),
        "return_interface_signal": ("SIGNAL_RETURN",),
        "signal_component_pin": ("J1.2",),
        "signal_interface_signal": ("UART_RX",),
        "assigned_net": ("SHARED_SIGNAL_NET",),
        "interface_catalog_sha256": ("c" * 64,),
    }
    assert "does not determine the required signal reference" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_nets_and_non_signal_peer_roles_are_controls() -> None:
    separate, _ = _report(
        signal_sharing_netlist(first_net="SIGNAL_RETURN", second_net="UART_RX")
    )
    return_and_shield, _ = _report(
        signal_sharing_netlist(),
        coverage=_coverage(signal_sharing_netlist(), roles=("return", "shield")),
    )
    two_signals, _ = _report(
        signal_sharing_netlist(),
        coverage=_coverage(signal_sharing_netlist(), roles=("signal", "signal")),
    )

    assert not _findings(separate)
    assert not _findings(return_and_shield)
    assert not _findings(two_signals)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_and_stale_coverage_are_controls() -> None:
    source = signal_sharing_netlist()
    dnp, _ = _report(signal_sharing_netlist(dnp=("J1",)))
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "Pin_9"}}
    )
    stale_source_report, _ = _report(stale_source, coverage=_coverage(source))
    open_coverage = signal_sharing_coverage(
        source,
        signal_names=("SIGNAL_RETURN", "UART_RX"),
        roles=("return", "signal"),
        unconnected_pin_reasons={"1": "Intentional synthetic open"},
    )
    reasoned_open, _ = _report(source, coverage=open_coverage)
    multi_net_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND": ("J1.1",)}}
    )
    multi_net, _ = _report(multi_net_source)
    incomplete, _ = _report(source, coverage=_coverage(source).model_copy(
        update={"status": "INCOMPLETE"}
    ))
    digestless, _ = _report(
        source, coverage=_coverage(source).model_copy(update={"interface_catalog_sha256": None})
    )

    assert not _findings(dnp)
    assert not _findings(stale_source_report)
    assert not _findings(reasoned_open)
    assert not _findings(multi_net)
    assert not _findings(incomplete)
    assert not _findings(digestless)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_apply() -> None:
    source = signal_sharing_netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(rules=(DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic project requires disposition of signal-to-return ties.",
        ),)),
    )
    disabled, _ = _report(
        source,
        policy=DesignLintPolicy(rules=(DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic project reviewed this heuristic.",
        ),)),
    )
    ignored, _ = _report(
        source,
        policy=DesignLintPolicy(ignores=(DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=baseline.fingerprint,
            reason="The mapped signal return tie is intentional in this fixture.",
        ),)),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = signal_sharing_netlist()
    reordered = source.model_copy(
        update={"nets": dict(reversed(tuple(source.nets.items())))}
    )

    assert _findings(_report(source)[0]) == _findings(_report(reordered)[0])
