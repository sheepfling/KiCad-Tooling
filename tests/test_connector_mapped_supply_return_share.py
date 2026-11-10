"""Review mapped connector supply and return contacts assigned to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.connector_mapped_supply_return_sharing import (
    supply_return_coverage,
    supply_return_netlist,
    supply_return_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_supply_return_share_net"


def _rule_findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_supply_and_return_on_unclassified_shared_net_request_review() -> None:
    observed = supply_return_netlist()
    report, coverage = supply_return_report(observed)

    assert coverage.status == "COMPLETE"
    (finding,) = _rule_findings(report)
    assert finding.subject == (
        "J1: mapped supply and return contacts share native net AUX_SHARED_NODE"
    )
    assert finding.evidence == {
        "component_reference": ("J1",),
        "supply_component_pin": ("J1.1",),
        "supply_interface_signal": ("SUPPLY_CONTACT",),
        "return_component_pin": ("J1.2",),
        "return_interface_signal": ("RETURN_CONTACT",),
        "interface_role": ("supply", "return"),
        "assigned_net": ("AUX_SHARED_NODE",),
        "interface_catalog_sha256": ("e" * 64,),
    }
    assert "unintended supply-to-return short" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_nets_and_other_role_pairs_are_controls() -> None:
    separate, _ = supply_return_report(
        supply_return_netlist(
            supply_net="SUPPLY_SOURCE",
            return_net="RETURN_REFERENCE",
        )
    )
    same_role, _ = supply_return_report(
        supply_return_netlist(),
        coverage=supply_return_coverage(
            supply_return_netlist(),
            roles=("return", "return"),
        ),
    )
    supply_signal, _ = supply_return_report(
        supply_return_netlist(),
        coverage=supply_return_coverage(
            supply_return_netlist(),
            roles=("supply", "signal"),
        ),
    )

    assert not _rule_findings(separate)
    assert not _rule_findings(same_role)
    assert not _rule_findings(supply_signal)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_stale_and_incomplete_maps_are_controls() -> None:
    source = supply_return_netlist()
    coverage = supply_return_coverage(source)
    dnp, _ = supply_return_report(supply_return_netlist(dnp=("J1",)))
    open_coverage = supply_return_coverage(
        source,
        unconnected_pin_reasons={"2": "Synthetic intentional open disposition"},
    )
    reasoned_open, _ = supply_return_report(source, coverage=open_coverage)
    ambiguous_source = source.model_copy(
        update={"nets": {**source.nets, "SECOND_ASSIGNMENT": ("J1.1",)}}
    )
    ambiguous, _ = supply_return_report(
        ambiguous_source,
        coverage=supply_return_coverage(ambiguous_source),
    )
    stale_source = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "J1.1": "VBUS altered"}}
    )
    stale, _ = supply_return_report(stale_source, coverage=coverage)
    incomplete, _ = supply_return_report(
        source,
        coverage=coverage.model_copy(update={"status": "INCOMPLETE"}),
    )
    digestless, _ = supply_return_report(
        source,
        coverage=coverage.model_copy(update={"interface_catalog_sha256": None}),
    )

    assert not _rule_findings(dnp)
    assert not _rule_findings(reasoned_open)
    assert not _rule_findings(ambiguous)
    assert not _rule_findings(stale)
    assert not _rule_findings(incomplete)
    assert not _rule_findings(digestless)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_and_exact_ignore_apply() -> None:
    source = supply_return_netlist()
    baseline = _rule_findings(supply_return_report(source)[0])[0]
    blocked, _ = supply_return_report(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic supply/return shared assignment requires disposition.",
                ),
            )
        ),
    )
    disabled, _ = supply_return_report(
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
    ignored, _ = supply_return_report(
        source,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic fixture documents an intentional shared net.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _rule_findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _rule_findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_mapping_order() -> None:
    source = supply_return_netlist()
    reordered = source.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(source.nets.items()))
            }
        }
    )

    assert _rule_findings(supply_return_report(source)[0]) == _rule_findings(
        supply_return_report(reordered)[0]
    )
