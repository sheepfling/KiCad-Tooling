"""Review distinct source-mapped connector signals assigned to one native net."""

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
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_signals_share_net"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    signal_names: tuple[str, str] = ("CONTROL_A", "CONTROL_B"),
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    current_coverage = (
        coverage
        if coverage is not None
        else signal_sharing_coverage(source, signal_names=signal_names)
    )
    return signal_sharing_report(source, coverage=current_coverage, policy=policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_mapped_generic_signals_sharing_one_net_request_review() -> None:
    report, coverage = _report(signal_sharing_netlist())

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "J1: distinct mapped signals CONTROL_A, CONTROL_B share native net SHARED_SIGNAL_NET"
    )
    assert finding.evidence == {
        "component_reference": ("J1",),
        "component_pin": ("J1.1", "J1.2"),
        "interface_signal": ("CONTROL_A", "CONTROL_B"),
        "interface_role": ("signal",),
        "assigned_nets": ("SHARED_SIGNAL_NET",),
        "interface_catalog_sha256": ("c" * 64,),
    }
    assert "do not prove" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_signal_alias_and_separate_nets_are_controls() -> None:
    same_signal, _ = _report(
        signal_sharing_netlist(),
        signal_names=("CONTROL_A", "control_a"),
    )
    separate_nets, _ = _report(
        signal_sharing_netlist(first_net="CONTROL_A_NET", second_net="CONTROL_B_NET")
    )

    assert not _findings(same_signal)
    assert not _findings(separate_nets)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_non_signal_roles_named_functions_dnp_and_multi_net_evidence_are_controls() -> None:
    source = signal_sharing_netlist()
    mapped_return, _ = _report(
        source,
        coverage=signal_sharing_coverage(source, roles=("return", "return")),
    )
    reasoned_open, _ = _report(
        source,
        coverage=signal_sharing_coverage(
            source,
            unconnected_pin_reasons={"1": "Synthetic intentional open disposition"},
        ),
    )
    named_native_function, _ = _report(signal_sharing_netlist(second_function="ANALOG_INPUT"))
    dnp, _ = _report(signal_sharing_netlist(dnp=("J1",)))
    multi_net_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.1",)}}
    )
    multi_net, _ = _report(multi_net_source)

    assert not _findings(mapped_return)
    assert not _findings(reasoned_open)
    assert not _findings(named_native_function)
    assert not _findings(dnp)
    assert not _findings(multi_net)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_stale_and_digestless_coverage_are_controls() -> None:
    source = signal_sharing_netlist()
    coverage = signal_sharing_coverage(source)
    incomplete, _ = _report(source, coverage=coverage.model_copy(update={"status": "INCOMPLETE"}))
    digestless, _ = _report(
        source,
        coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
    )
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "9"}}
    )
    stale, _ = _report(stale_source, coverage=coverage)

    assert not _findings(incomplete)
    assert not _findings(digestless)
    assert not _findings(stale)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = signal_sharing_netlist()
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic independent signal assignments are reviewed.",
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
                    reason="Synthetic project explicitly disables this review heuristic.",
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
                    reason="The mapped signals are intentionally tied in this synthetic case.",
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

    first, _ = _report(source)
    second, _ = _report(reordered)

    assert _findings(first) == _findings(second)
