"""Review same-domain connector return contacts assigned to separate nets."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_connectors_return_domains import (
    mapped_same_domain_return_split_net_candidates,
)
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_return_domain_split_candidate_evidence import (
    MappedReturnDomainSplitCandidate,
    project_mapped_return_domain_split_evidence,
)
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_same_domain_return_split_nets"


def _findings(report: DesignLintReport):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_domain_return_contacts_split_across_nets_request_review() -> None:
    source = signal_sharing_netlist(
        first_net="RETURN_SEGMENT_A",
        second_net="RETURN_SEGMENT_B",
        first_function="Pin_1",
        second_function="Pin_2",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("RETURN_CONTACT_A", "RETURN_CONTACT_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )

    report, coverage = signal_sharing_report(source, coverage=coverage)

    assert coverage.status == "COMPLETE"
    (finding,) = _findings(report)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "J1: mapped return contacts in voltage domain signal-return use separate native nets"
    )
    assert finding.evidence["interface_role"] == ("return",)
    assert finding.evidence["voltage_domain"] == ("signal-return",)
    assert finding.evidence["split_native_nets"] == (
        "RETURN_SEGMENT_A",
        "RETURN_SEGMENT_B",
    )
    assert "does not require common nets" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_net_different_domains_and_other_roles_are_controls() -> None:
    common_net = signal_sharing_netlist()
    common_coverage = signal_sharing_coverage(
        common_net,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    different_domains = signal_sharing_netlist(
        first_net="RETURN_SEGMENT_A", second_net="RETURN_SEGMENT_B"
    )
    different_domain_coverage = signal_sharing_coverage(
        different_domains,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "isolated-return"),
    )
    non_return = signal_sharing_netlist(first_net="SIGNAL_A", second_net="SIGNAL_B")
    non_return_coverage = signal_sharing_coverage(
        non_return,
        signal_names=("SIGNAL_A", "SIGNAL_B"),
        roles=("signal", "signal"),
    )

    assert not _findings(signal_sharing_report(common_net, coverage=common_coverage)[0])
    assert not _findings(
        signal_sharing_report(different_domains, coverage=different_domain_coverage)[0]
    )
    assert not _findings(signal_sharing_report(non_return, coverage=non_return_coverage)[0])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_incomplete_and_digestless_controls() -> None:
    source = signal_sharing_netlist(first_net="RETURN_SEGMENT_A", second_net="RETURN_SEGMENT_B")
    coverage = signal_sharing_coverage(
        source,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    dnp_source = source.model_copy(update={"dnp_components": ("J1",)})
    open_coverage = signal_sharing_coverage(
        source,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
        unconnected_pin_reasons={"2": "Synthetic intentional open"},
    )
    ambiguous_source = source.model_copy(
        update={"nets": {**source.nets, "ALTERNATE_RETURN": ("J1.2",)}}
    )
    stale_source = source.model_copy(
        update={"nets": {"RETURN_SEGMENT_A": ("J1.1",), "RETURN_SEGMENT_C": ("J1.2",)}}
    )

    assert not _findings(
        signal_sharing_report(
            dnp_source,
            coverage=signal_sharing_coverage(
                dnp_source,
                signal_names=("RETURN_A", "RETURN_B"),
                roles=("return", "return"),
                voltage_domains=("signal-return", "signal-return"),
            ),
        )[0]
    )
    assert not _findings(signal_sharing_report(source, coverage=open_coverage)[0])
    assert not _findings(
        signal_sharing_report(
            ambiguous_source,
            coverage=signal_sharing_coverage(
                ambiguous_source,
                signal_names=("RETURN_A", "RETURN_B"),
                roles=("return", "return"),
                voltage_domains=("signal-return", "signal-return"),
            ),
        )[0]
    )
    assert not _findings(signal_sharing_report(stale_source, coverage=coverage)[0])
    assert not _findings(
        signal_sharing_report(
            source, coverage=coverage.model_copy(update={"status": "INCOMPLETE"})
        )[0]
    )
    assert not _findings(
        signal_sharing_report(
            source, coverage=coverage.model_copy(update={"interface_catalog_sha256": None})
        )[0]
    )
    assert not _findings(signal_sharing_report(source)[0])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_and_exact_fingerprint_ignore_apply() -> None:
    source = signal_sharing_netlist(first_net="RETURN_SEGMENT_A", second_net="RETURN_SEGMENT_B")
    coverage = signal_sharing_coverage(
        source,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    baseline = _findings(signal_sharing_report(source, coverage=coverage)[0])[0]
    blocked, _ = signal_sharing_report(
        source,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of split mapped returns.",
                ),
            )
        ),
    )
    off, _ = signal_sharing_report(
        source,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed its separated return topology.",
                ),
            )
        ),
    )
    ignored, _ = signal_sharing_report(
        source,
        coverage=coverage,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic project documents this intentional return split.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].disposition == "OPEN"
    assert _findings(off)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_deterministic_and_rejects_stale_source_projection() -> None:
    source = signal_sharing_netlist(first_net="RETURN_SEGMENT_A", second_net="RETURN_SEGMENT_B")
    coverage = signal_sharing_coverage(
        source,
        signal_names=("RETURN_A", "RETURN_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    reordered = source.model_copy(update={"nets": dict(reversed(tuple(source.nets.items())))})
    baseline = _findings(signal_sharing_report(source, coverage=coverage)[0])
    reordered_findings = _findings(signal_sharing_report(reordered, coverage=coverage)[0])
    assert baseline == reordered_findings

    source_candidate = mapped_same_domain_return_split_net_candidates(source, coverage)[0]
    assert isinstance(source_candidate, MappedReturnDomainSplitCandidate)
    assert source_candidate.evidence == baseline[0].evidence
    assert (
        project_mapped_return_domain_split_evidence(source_candidate.source_evidence).evidence
        == source_candidate.evidence
    )
    stale_source = source.model_copy(update={"nets": {"RETURN_SEGMENT_A": ("J1.1",)}})
    with pytest.raises(ValueError, match="current connector evidence"):
        replace(source_candidate.source_evidence, observed=stale_source)
