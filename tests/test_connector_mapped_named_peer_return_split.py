"""Review named mapped same-domain return peers assigned to separate nets."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_connector_named_peer_return_split_candidate_evidence import (
    MappedNamedPeerReturnSplitCandidate,
    project_mapped_named_peer_return_split_evidence,
)
from kicad_tooling.hwrepo.design_lint_connectors_named_peer_return_splits import (
    mapped_named_peer_return_split_net_candidates,
)
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.connector_mapped_peer_return_split import (
    mapped_peer_return_coverage,
    mapped_peer_return_netlist,
    mapped_peer_return_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_named_peer_return_split_nets"


def _findings(report: DesignLintReport):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_mapped_return_domain_split_has_no_existing_specific_prompt() -> None:
    observed = mapped_peer_return_netlist()
    coverage = mapped_peer_return_coverage(observed)
    report, coverage = mapped_peer_return_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    existing_specific_rules = {
        "connector.repeated_pin_function",
        "connector.peer_pin_assignment_divergence",
        "connector.peer_pin_assignment_outlier",
        "connector.mapped_same_domain_return_split_nets",
        "connector.mapped_return_domains_share_net",
    }
    assert not any(item.rule_id in existing_specific_rules for item in report.findings)
    (finding,) = _findings(report)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "external-returns: mapped peer returns in voltage domain signal-return "
        "use separate native nets"
    )
    assert finding.evidence["return_comparison_group"] == ("external-returns",)
    assert finding.evidence["voltage_domain"] == ("signal-return",)
    assert finding.evidence["connector_references"] == ("J1", "J2")
    assert finding.evidence["split_native_nets"] == (
        "RETURN_SEGMENT_A",
        "RETURN_SEGMENT_B",
    )
    assert "do not require common nets" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_net_domain_scope_and_existing_return_groups_are_controls() -> None:
    common = mapped_peer_return_netlist(
        assignments=(("SHARED_RETURN",), ("SHARED_RETURN",)),
    )
    different_domains = mapped_peer_return_netlist()
    different_domain_coverage = mapped_peer_return_coverage(
        different_domains,
        domains=("signal-return", "chassis-return"),
    )
    different_groups = mapped_peer_return_netlist()
    different_group_coverage = mapped_peer_return_coverage(
        different_groups,
        groups=("left-returns", "right-returns"),
    )
    unscoped = mapped_peer_return_netlist()
    unscoped_coverage = mapped_peer_return_coverage(unscoped, groups=(None, None))
    partial_scope = mapped_peer_return_netlist(
        assignments=(
            ("RETURN_SEGMENT_A",),
            ("RETURN_SEGMENT_B",),
            ("RETURN_SEGMENT_C",),
        ),
    )
    partial_scope_coverage = mapped_peer_return_coverage(
        partial_scope,
        groups=("external-returns", "external-returns", None),
    )
    generic = mapped_peer_return_netlist(functions=("Pin_1", "Pin_1"))
    return_aliases = mapped_peer_return_netlist(functions=("GND", "RETURN"))

    for observed, coverage in (
        (common, None),
        (different_domains, different_domain_coverage),
        (different_groups, different_group_coverage),
        (unscoped, unscoped_coverage),
        (partial_scope, partial_scope_coverage),
        (generic, None),
        (return_aliases, None),
    ):
        report, _ = mapped_peer_return_report(observed, coverage=coverage)
        assert not _findings(report)

    assert any(
        item.rule_id == "connector.repeated_pin_function"
        for item in mapped_peer_return_report(generic)[0].findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_incomplete_and_digestless_controls() -> None:
    dnp = mapped_peer_return_netlist(dnp=("J2",))
    open_pin = mapped_peer_return_netlist(assignments=(("RETURN_SEGMENT_A",), ()))
    open_coverage = mapped_peer_return_coverage(
        open_pin,
        opens=(None, "Intentionally open in this synthetic case"),
    )
    ambiguous = mapped_peer_return_netlist(
        assignments=(("RETURN_SEGMENT_A",), ("RETURN_SEGMENT_B", "OTHER_ASSIGNMENT")),
    )
    stale = mapped_peer_return_netlist(
        assignments=(("RETURN_SEGMENT_A",), ("UPDATED_RETURN_SEGMENT",)),
    )
    base = mapped_peer_return_netlist()
    base_coverage = mapped_peer_return_coverage(base)
    incomplete = base_coverage.model_copy(update={"status": "INCOMPLETE"})
    digestless = base_coverage.model_copy(update={"interface_catalog_sha256": None})

    for observed, coverage in (
        (dnp, None),
        (open_pin, open_coverage),
        (ambiguous, None),
        (stale, base_coverage),
        (base, incomplete),
        (base, digestless),
    ):
        report, _ = mapped_peer_return_report(observed, coverage=coverage)
        assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_and_exact_fingerprint_ignore_apply() -> None:
    observed = mapped_peer_return_netlist()
    coverage = mapped_peer_return_coverage(observed)
    baseline = _findings(mapped_peer_return_report(observed, coverage=coverage)[0])[0]
    blocked, _ = mapped_peer_return_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of its named return peers.",
                ),
            )
        ),
    )
    off, _ = mapped_peer_return_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed its named return peers already.",
                ),
            )
        ),
    )
    ignored, _ = mapped_peer_return_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic project documented the intentional return split.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].disposition == "OPEN"
    assert _findings(off)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_deterministic_and_source_projection_rejects_stale_netlist() -> None:
    observed = mapped_peer_return_netlist()
    coverage = mapped_peer_return_coverage(observed)
    candidates = mapped_named_peer_return_split_net_candidates(observed, coverage)
    (candidate,) = candidates
    assert isinstance(candidate, MappedNamedPeerReturnSplitCandidate)
    reordered = observed.model_copy(update={"nets": dict(reversed(tuple(observed.nets.items())))})
    reordered_coverage = mapped_peer_return_coverage(reordered)
    reordered_candidates = mapped_named_peer_return_split_net_candidates(
        reordered, reordered_coverage
    )

    assert candidate == reordered_candidates[0]
    assert (
        project_mapped_named_peer_return_split_evidence(candidate.source_evidence).evidence
        == candidate.evidence
    )
    stale = observed.model_copy(
        update={
            "nets": {
                "RETURN_SEGMENT_A": ("J1.1",),
                "UPDATED_RETURN_SEGMENT": ("J2.1",),
            }
        }
    )
    with pytest.raises(ValueError, match="current source evidence"):
        replace(candidate.source_evidence, observed=stale)
