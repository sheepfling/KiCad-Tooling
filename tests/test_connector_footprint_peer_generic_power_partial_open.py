"""Source-bound review for generic power contacts open on some alias peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.connector_footprint_peer_support import NETLIST_SHA256, peer_netlist
from tests.connector_peer_unanchored_scope_support import reviewed_coverage

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_peer_generic_power_pin_open_outlier"
PROJECT_ID = "synthetic-generic-power-peer-open"


def _source(
    *,
    power_type: str = "power_in",
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("COMMON_RETURN", "COMMON_RETURN"),
        ("VBUS", None),
    ),
):
    source = peer_netlist(assignments=assignments).model_copy(
        update={
            "pin_electrical_types": {
                **peer_netlist(assignments=assignments).pin_electrical_types,
                "J1.2": power_type,
                "J2.2": power_type,
            }
        }
    )
    return source


def _report(source, policy: DesignLintPolicy | None = None, *, coverage=None):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=source,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate(
        PROJECT_ID,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


def _rule_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("power_type", ("power_in", "power_out"))
def test_generic_power_partial_open_peer_pattern_is_opt_in_review(power_type: str) -> None:
    source = _source(power_type=power_type)
    report = _report(source)
    (finding,) = _rule_findings(report)

    assert report.status == "REVIEW"
    assert finding.mode == "off"
    assert finding.disposition == "RULE_OFF"
    assert finding.evidence["pin_electrical_type"] == (power_type,)
    assert finding.evidence["assignments"] == (
        "J1.2=VBUS",
        "J2.2=<unassigned>",
    )
    assert finding.evidence["open_pins"] == ("J2.2",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "individual open-pin finding already reports the open pin" in finding.message
    individual_rule = (
        "connector.unconnected_power_input"
        if power_type == "power_in"
        else "connector.unconnected_power_output"
    )
    assert any(item.rule_id == individual_rule for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_partial_open_needs_current_shared_peer_scope() -> None:
    source = _source(assignments=(("RETURN_A", "RETURN_B"), ("VBUS", None)))
    no_scope = _report(source)
    scoped = _report(source, coverage=reviewed_coverage(source))
    separate = _report(
        source,
        coverage=reviewed_coverage(source, groups=("port-a", "port-b")),
    )

    assert not _rule_findings(no_scope)
    assert len(_rule_findings(scoped)) == 1
    assert _rule_findings(scoped)[0].evidence["common_anchor_pin_numbers"] == ()
    assert _rule_findings(scoped)[0].evidence["peer_assignment_group"] == (
        "synthetic-peer-connectors",
    )
    assert not _rule_findings(separate)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_assigned_and_documented_open_contacts_are_controls() -> None:
    assigned = _report(_source(assignments=(("COMMON_RETURN", "COMMON_RETURN"), ("VBUS", "VBUS"))))
    source = _source(assignments=(("RETURN_A", "RETURN_B"), ("VBUS", None)))
    documented = _report(
        source,
        coverage=reviewed_coverage(source, unconnected_pins=("J2.2",)),
    )

    assert not _rule_findings(assigned)
    assert not _rule_findings(documented)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_power_open_policy_and_exact_ignore_are_project_configurable() -> None:
    source = _source()
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project opts into peer power-pin review.",
            ),
        )
    )
    finding = _rule_findings(_report(source, review_policy))[0]
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires disposition of peer power opens.",
                ),
            )
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            rules=review_policy.rules,
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project accepts the intentional open contact.",
                ),
            ),
        ),
    )

    assert finding.disposition == "OPEN"
    assert blocked.status == "FAIL"
    assert _rule_findings(blocked)[0].mode == "block"
    assert _rule_findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_power_peer_open_fingerprint_is_stable_under_mapping_order() -> None:
    source = _source()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    first = _rule_findings(_report(source))[0]
    second = _rule_findings(_report(reordered))[0]
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
