"""Review generic native power contacts left open across similar connector peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.connector_footprint_peer_support import NETLIST_SHA256, peer_netlist
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_peer_pin_all_open import generic_open_peer_coverage

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_peer_generic_power_pin_all_open"
PROJECT_ID = "synthetic-footprint-peer-generic-power"


def _source(
    *,
    power_type: str = "power_in",
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("COMMON_RETURN", "COMMON_RETURN"),
        (None, None),
    ),
    functions: tuple[str, str] = ("Pin_1", "Pin_2"),
) -> NetlistContract:
    return peer_netlist(
        assignments=assignments,
        functions=functions,
        electrical_types=("passive", power_type),
    )


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
):
    source_coach = coach(source).model_copy(update={"netlist_sha256": NETLIST_SHA256})
    coverage = connector_coverage or generic_open_peer_coverage(
        source, groups=("synthetic-port-peers",) * len(source.component_symbols)
    )
    return evaluate(
        PROJECT_ID,
        source_coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


def _rule_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _existing_pin_rule_off_policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.unconnected_power_input",
                mode="off",
                reason="Synthetic test isolates peer-group context from individual-pin review.",
            ),
            DesignLintRuleOverride(
                rule_id="connector.unconnected_power_output",
                mode="off",
                reason="Synthetic test isolates peer-group context from individual-pin review.",
            ),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("power_type", ("power_in", "power_out"))
def test_generic_power_contact_open_on_all_alias_peers_is_opt_in_review(power_type: str) -> None:
    source = _source(power_type=power_type)
    default = _report(source, _existing_pin_rule_off_policy())
    (default_finding,) = _rule_findings(default)

    assert default.status == "PASS"
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert default_finding.evidence["pin_electrical_type"] == (power_type,)
    assert default_finding.evidence["assignments"] == (
        "J1.2=<unassigned>",
        "J2.2=<unassigned>",
    )
    assert default_finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not prove that the contact must connect" in default_finding.message

    policy = DesignLintPolicy(
        rules=(
            *_existing_pin_rule_off_policy().rules,
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project opts into generic connector power-pin review.",
            ),
        )
    )
    reviewed = _report(source, policy)
    assert reviewed.status == "REVIEW"
    assert _rule_findings(reviewed)[0].disposition == "OPEN"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_assigned_or_meaningfully_named_power_contacts_are_controls() -> None:
    assigned = _report(_source(assignments=(("COMMON_RETURN", "COMMON_RETURN"), ("VBUS", "VBUS"))))
    named = _report(_source(functions=("Pin_1", "VBUS")))

    assert not _rule_findings(assigned)
    assert not _rule_findings(named)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_inconsistent_pin_metadata_and_separately_scoped_peers_stay_quiet() -> None:
    source = _source()
    mismatched = source.model_copy(
        update={"pin_electrical_types": {**source.pin_electrical_types, "J2.2": "passive"}}
    )
    separate_coverage = generic_open_peer_coverage(source, groups=("port-a", "port-b"))

    assert not _rule_findings(_report(mismatched))
    assert not _rule_findings(_report(source, connector_coverage=separate_coverage))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_power_review_policy_and_exact_ignore_are_project_configurable() -> None:
    source = _source()
    baseline = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project chooses this review scope.",
            ),
        )
    )
    finding = _rule_findings(_report(source, baseline))[0]
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy exercises configurable blocking.",
                ),
            )
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            rules=baseline.rules,
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records an intentionally open contact.",
                ),
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert _rule_findings(blocked)[0].mode == "block"
    assert _rule_findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_power_review_fingerprint_is_stable_under_mapping_order() -> None:
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
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project exercises order stability.",
            ),
        )
    )

    first = _rule_findings(_report(source, policy))[0]
    second = _rule_findings(_report(reordered, policy))[0]
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
