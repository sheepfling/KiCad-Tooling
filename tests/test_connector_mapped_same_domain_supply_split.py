"""Review source-mapped same-domain supplies split across one connector."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_connectors_supply_domains import (
    mapped_same_domain_supply_split_net_candidates,
)
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_supply_domain_split_candidate_evidence import (
    MappedSupplyDomainSplitCandidate,
    project_mapped_supply_domain_split_evidence,
)
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_same_domain_supply_split_nets"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_domain_supply_contacts_split_across_nets_request_review() -> None:
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
        first_function="Pin_1",
        second_function="Pin_2",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )

    report, coverage = signal_sharing_report(source, coverage=coverage)
    assert coverage.status == "COMPLETE"
    (finding,) = _findings(report)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "J1: mapped supply contacts in voltage domain logic-5v use separate native nets"
    )
    assert finding.evidence == {
        "component_reference": ("J1",),
        "interface_role": ("supply",),
        "voltage_domain": ("logic-5v",),
        "split_native_nets": ("SUPPLY_SEGMENT_A", "SUPPLY_SEGMENT_B"),
        "mapped_supply_assignments": (
            "J1.1=SUPPLY_SEGMENT_A; voltage_domain=logic-5v",
            "J1.2=SUPPLY_SEGMENT_B; voltage_domain=logic-5v",
        ),
        "interface_catalog_sha256": ("c" * 64,),
        "interface_catalog_path": ("catalog/interfaces.json",),
        "J1.1": ("SUPPLY_SEGMENT_A",),
        "J1.2": ("SUPPLY_SEGMENT_B",),
    }
    assert "does not require common nets" in finding.message


def _findings(report: DesignLintReport):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_distinct_domains_and_non_supply_roles_are_controls() -> None:
    same_net_source = signal_sharing_netlist()
    same_net_coverage = signal_sharing_coverage(
        same_net_source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    distinct_domain_source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    distinct_domain_coverage = signal_sharing_coverage(
        distinct_domain_source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
        voltage_domains=("logic-5v", "isolated-5v"),
    )
    non_supply_source = signal_sharing_netlist(
        first_net="SIGNAL_A",
        second_net="SIGNAL_B",
    )
    non_supply_coverage = signal_sharing_coverage(
        non_supply_source,
        roles=("signal", "signal"),
    )

    assert not _findings(signal_sharing_report(same_net_source, coverage=same_net_coverage)[0])
    assert not _findings(
        signal_sharing_report(distinct_domain_source, coverage=distinct_domain_coverage)[0]
    )
    assert not _findings(signal_sharing_report(non_supply_source, coverage=non_supply_coverage)[0])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_incomplete_and_digestless_controls() -> None:
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    dnp_source = source.model_copy(update={"dnp_components": ("J1",)})
    reasoned_open_coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
        unconnected_pin_reasons={"2": "Synthetic intentional open"},
    )
    ambiguous_source = source.model_copy(
        update={"nets": {**source.nets, "ALTERNATE_SUPPLY": ("J1.2",)}}
    )
    stale_source = source.model_copy(
        update={"nets": {"SUPPLY_SEGMENT_A": ("J1.1",), "SUPPLY_SEGMENT_C": ("J1.2",)}}
    )

    assert not _findings(
        signal_sharing_report(dnp_source, coverage=signal_sharing_coverage(dnp_source))[0]
    )
    assert not _findings(signal_sharing_report(source, coverage=reasoned_open_coverage)[0])
    assert not _findings(
        signal_sharing_report(ambiguous_source, coverage=signal_sharing_coverage(ambiguous_source))[
            0
        ]
    )
    assert not _findings(signal_sharing_report(stale_source, coverage=coverage)[0])
    assert not _findings(
        signal_sharing_report(
            source, coverage=coverage.model_copy(update={"status": "INCOMPLETE"})
        )[0]
    )
    assert not _findings(
        signal_sharing_report(
            source,
            coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
        )[0]
    )
    assert not _findings(signal_sharing_report(source)[0])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_and_exact_fingerprint_ignore_apply() -> None:
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
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
                    reason="Synthetic supply pin domains require reviewer disposition.",
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
                    reason="Synthetic project reviewed the separated supply contacts.",
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
                    reason="Synthetic project documents an intentional split supply path.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].disposition == "OPEN"
    assert _findings(off)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    reordered = source.model_copy(update={"nets": dict(reversed(tuple(source.nets.items())))})
    baseline = _findings(signal_sharing_report(source, coverage=coverage)[0])
    reordered_findings = _findings(signal_sharing_report(reordered, coverage=coverage)[0])

    assert baseline == reordered_findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_retains_exact_source_records_and_rejects_stale_projection() -> None:
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    finding = _findings(signal_sharing_report(source, coverage=coverage)[0])[0]
    candidate = mapped_same_domain_supply_split_net_candidates(source, coverage)[0]
    assert candidate.evidence == finding.evidence

    stale_source = source.model_copy(update={"nets": {"SUPPLY_SEGMENT_A": ("J1.1",)}})
    assert (
        project_mapped_supply_domain_split_evidence(candidate.source_evidence).evidence
        == candidate.evidence
    )
    with pytest.raises(ValueError, match="current connector evidence"):
        replace(candidate.source_evidence, observed=stale_source)
    assert isinstance(
        MappedSupplyDomainSplitCandidate.from_source_evidence(
            candidate.source_evidence,
            subject=candidate.subject,
            message=candidate.message,
        ),
        MappedSupplyDomainSplitCandidate,
    )
