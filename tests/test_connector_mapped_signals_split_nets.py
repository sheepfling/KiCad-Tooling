"""Review duplicate source-mapped signal contacts on separate native nets."""

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

RULE_ID = "connector.mapped_signals_split_nets"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    signal_names: tuple[str, str] = ("CONTROL_A", "control_a"),
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
def test_repeated_mapped_generic_signal_contacts_on_separate_nets_request_review() -> None:
    source = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")
    report, coverage = _report(source)

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "J1: mapped signal CONTROL_A spans native nets CONTACT_NET_A, CONTACT_NET_B"
    )
    assert finding.evidence == {
        "component_reference": ("J1",),
        "component_pin": ("J1.1", "J1.2"),
        "interface_signal": ("CONTROL_A",),
        "interface_role": ("signal",),
        "assigned_nets": ("CONTACT_NET_A", "CONTACT_NET_B"),
        "interface_catalog_sha256": ("c" * 64,),
    }
    assert "does not establish PCB copper continuity" in finding.message
    assert not any(item.rule_id == "connector.mapped_signals_share_net" for item in report.findings)
    assert not any(item.rule_id == "connector.repeated_pin_function" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_repeated_signal_and_distinct_signal_controls_are_quiet() -> None:
    common_net = signal_sharing_netlist()
    distinct_signals = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")

    common, _ = _report(common_net)
    distinct, _ = _report(distinct_signals, signal_names=("CONTROL_A", "CONTROL_B"))

    assert not _findings(common)
    assert not _findings(distinct)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_non_signal_roles_named_functions_dnp_and_ambiguous_pins_are_controls() -> None:
    source = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")
    mapped_returns, _ = _report(
        source,
        coverage=signal_sharing_coverage(source, roles=("return", "return")),
    )
    named_functions, _ = _report(
        signal_sharing_netlist(
            first_net="CONTACT_NET_A",
            second_net="CONTACT_NET_B",
            first_function="CTRL",
            second_function="CTRL",
        )
    )
    dnp, _ = _report(
        signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B", dnp=("J1",))
    )
    reasoned_open, _ = _report(
        source,
        coverage=signal_sharing_coverage(
            source,
            unconnected_pin_reasons={"1": "Synthetic intentional separate contact"},
        ),
    )
    multi_net_source = source.model_copy(update={"nets": {**source.nets, "THIRD_NET": ("J1.1",)}})
    multi_net, _ = _report(multi_net_source)

    assert not _findings(mapped_returns)
    assert not _findings(named_functions)
    assert not _findings(dnp)
    assert not _findings(reasoned_open)
    assert not _findings(multi_net)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_stale_and_digestless_coverage_are_controls() -> None:
    source = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")
    coverage = signal_sharing_coverage(source, signal_names=("CONTROL_A", "control_a"))
    incomplete, _ = _report(source, coverage=coverage.model_copy(update={"status": "INCOMPLETE"}))
    digestless, _ = _report(
        source,
        coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
    )
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "3"}}
    )
    stale, _ = _report(stale_source, coverage=coverage)

    assert not _findings(incomplete)
    assert not _findings(digestless)
    assert not _findings(stale)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_and_exact_ignore_apply() -> None:
    source = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")
    baseline = _findings(_report(source)[0])[0]
    blocked, _ = _report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="The reviewed synthetic interface groups these contacts.",
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
                    reason="The split is intentional in this synthetic project.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order_and_neutral_rename() -> None:
    source = signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B")
    reordered = source.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(source.nets.items()))
            }
        }
    )
    renamed = source.model_copy(
        update={
            "nets": {
                "NEUTRAL_B": source.nets["CONTACT_NET_B"],
                "NEUTRAL_A": source.nets["CONTACT_NET_A"],
            }
        }
    )

    first, _ = _report(source)
    second, _ = _report(reordered)
    renamed_report, _ = _report(renamed)

    assert _findings(first) == _findings(second)
    assert (
        _findings(first)[0].evidence["component_pin"]
        == _findings(renamed_report)[0].evidence["component_pin"]
    )
    assert (
        _findings(first)[0].evidence["assigned_nets"]
        != _findings(renamed_report)[0].evidence["assigned_nets"]
    )
