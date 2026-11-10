"""Review named mapped peer supplies in one domain assigned to split nets."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_connector_named_peer_supply_split_candidate_evidence import (
    MappedNamedPeerSupplySplitCandidate,
    project_mapped_named_peer_supply_split_evidence,
)
from kicad_tooling.hwrepo.design_lint_connectors_named_peer_supply_splits import (
    mapped_named_peer_supply_split_net_candidates,
)
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.connector_mapped_peer_supply_split import (
    mapped_peer_supply_coverage,
    mapped_peer_supply_netlist,
    mapped_peer_supply_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]

RULE_ID = "connector.mapped_named_peer_supply_split_nets"
LEGACY_RULE_IDS = frozenset(
    {
        "connector.repeated_pin_function",
        "connector.reviewed_peer_power_input_split",
        "connector.reviewed_peer_power_output_split",
        "connector.mapped_same_domain_supply_split_nets",
        "connector.mapped_supply_domains_share_net",
    }
)


def _findings(report: DesignLintReport):
    return tuple(finding for finding in report.findings if finding.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_peer_supply_split_baseline_has_no_existing_specific_prompt() -> None:
    observed = mapped_peer_supply_netlist()
    coverage = mapped_peer_supply_coverage(observed)
    report, coverage = mapped_peer_supply_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    legacy_findings = tuple(
        finding for finding in report.findings if finding.rule_id in LEGACY_RULE_IDS
    )
    assert not legacy_findings
    (finding,) = _findings(report)
    assert report.status == "REVIEW"
    assert finding.subject == (
        "external-power: mapped peer supplies in voltage domain board-input "
        "use separate native nets"
    )
    assert finding.evidence["supply_comparison_group"] == ("external-power",)
    assert finding.evidence["voltage_domain"] == ("board-input",)
    assert finding.evidence["connector_references"] == ("J1", "J2")
    assert finding.evidence["split_native_nets"] == ("NODE_ALPHA", "NODE_BETA")
    assert "do not require common nets" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_net_domain_group_and_participant_scopes_are_controls() -> None:
    common = mapped_peer_supply_netlist(assignments=(("COMMON_NODE",), ("COMMON_NODE",)))
    split = mapped_peer_supply_netlist()
    different_domains = mapped_peer_supply_coverage(
        split,
        domains=("board-input", "isolated-input"),
    )
    different_groups = mapped_peer_supply_coverage(
        split,
        groups=("usb-power", "serial-power"),
    )
    unscoped = mapped_peer_supply_coverage(split, groups=("external-power", None))
    partial_scope = mapped_peer_supply_netlist(
        assignments=(("NODE_ALPHA",), ("NODE_BETA",), ("NODE_GAMMA",)),
    )
    partial_coverage = mapped_peer_supply_coverage(
        partial_scope,
        groups=("external-power", "external-power", None),
    )
    generic = mapped_peer_supply_netlist(functions=("Pin_1", "Pin_1"))
    recognized = mapped_peer_supply_netlist(functions=("VBUS", "VDD"))
    return_label = mapped_peer_supply_netlist(functions=("SUPPLY_A", "GND"))
    other_role = mapped_peer_supply_coverage(split, roles=("signal", "signal"))

    for observed, coverage in (
        (common, None),
        (split, different_domains),
        (split, different_groups),
        (split, unscoped),
        (partial_scope, partial_coverage),
        (generic, None),
        (recognized, None),
        (return_label, None),
        (split, other_role),
    ):
        report, _ = mapped_peer_supply_report(observed, coverage=coverage)
        assert not _findings(report)

    assert any(
        finding.rule_id == "connector.repeated_pin_function"
        for finding in mapped_peer_supply_report(generic)[0].findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_incomplete_and_digestless_controls() -> None:
    dnp = mapped_peer_supply_netlist(dnp=("J2",))
    opened = mapped_peer_supply_netlist(assignments=(("NODE_ALPHA",), ()))
    opened_coverage = mapped_peer_supply_coverage(
        opened,
        opens=(None, "Synthetic intentionally open power pin"),
    )
    ambiguous = mapped_peer_supply_netlist(
        assignments=(("NODE_ALPHA",), ("NODE_BETA", "ALTERNATE_NODE")),
    )
    observed = mapped_peer_supply_netlist()
    current = mapped_peer_supply_coverage(observed)

    for candidate, coverage in (
        (dnp, None),
        (opened, opened_coverage),
        (ambiguous, None),
        (
            observed.model_copy(
                update={"nets": {"NODE_ALPHA": ("J1.1",), "REVISED_NODE": ("J2.1",)}}
            ),
            current,
        ),
        (observed, current.model_copy(update={"status": "INCOMPLETE"})),
        (observed, current.model_copy(update={"interface_catalog_sha256": None})),
    ):
        report, _ = mapped_peer_supply_report(candidate, coverage=coverage)
        assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_and_exact_fingerprint_ignore_apply() -> None:
    observed = mapped_peer_supply_netlist()
    coverage = mapped_peer_supply_coverage(observed)
    baseline = _findings(mapped_peer_supply_report(observed, coverage=coverage)[0])[0]
    blocked, _ = mapped_peer_supply_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of separated supply peers.",
                ),
            )
        ),
    )
    off, _ = mapped_peer_supply_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed the separate supply branches.",
                ),
            )
        ),
    )
    ignored, _ = mapped_peer_supply_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic project documented the intentional supply split.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].disposition == "OPEN"
    assert _findings(off)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_deterministic_and_projection_rejects_stale_netlist() -> None:
    observed = mapped_peer_supply_netlist()
    coverage = mapped_peer_supply_coverage(observed)
    candidates = mapped_named_peer_supply_split_net_candidates(observed, coverage)
    (candidate,) = candidates
    assert isinstance(candidate, MappedNamedPeerSupplySplitCandidate)
    reordered = observed.model_copy(update={"nets": dict(reversed(tuple(observed.nets.items())))})
    reordered_candidates = mapped_named_peer_supply_split_net_candidates(
        reordered,
        mapped_peer_supply_coverage(reordered),
    )
    assert candidate == reordered_candidates[0]
    assert (
        project_mapped_named_peer_supply_split_evidence(candidate.source_evidence).evidence
        == candidate.evidence
    )

    stale = observed.model_copy(
        update={"nets": {"NODE_ALPHA": ("J1.1",), "UPDATED_NODE": ("J2.1",)}}
    )
    with pytest.raises(ValueError, match="current scope"):
        replace(candidate.source_evidence, observed=stale)
