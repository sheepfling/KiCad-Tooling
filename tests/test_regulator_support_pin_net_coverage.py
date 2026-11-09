"""Coverage prompts for project-mapped active regulator-support connectivity."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.regulator_support_pin_net_support import support_pin_net_map, support_pin_netlist
from tests.test_regulator_support_pin_roles import support_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_support_pin_net_map_coverage_missing"
_DEFAULT_ROLE_MAP = object()


def _report(
    *,
    role_map=_DEFAULT_ROLE_MAP,
    net_map=None,
    mode: str | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
):
    selected_role_map = support_map() if role_map is _DEFAULT_ROLE_MAP else role_map
    policy = DesignLintPolicy(
        regulator_support_pin_role_map=selected_role_map,
        regulator_support_pin_net_map=net_map,
        rules=()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic contract-coverage policy case",
            ),
        ),
        ignores=ignores,
    )
    observed = support_pin_netlist()
    return evaluate(
        "synthetic-regulator-support-net-coverage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator-support-net-coverage",
            observed=observed,
            netlist_sha256="f" * 64,
        ),
        policy,
    )


def _net_map_without_component(reference: str):
    requirements = support_pin_net_map()
    return requirements.model_copy(
        update={
            "requirements": tuple(
                topology.model_copy(
                    update={
                        "components": tuple(
                            component
                            for component in topology.components
                            if component.reference.casefold() != reference.casefold()
                        )
                    }
                )
                for topology in requirements.requirements
            )
        }
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_pin_net_map_covers_every_source_matched_role_component() -> None:
    report = _report(net_map=support_pin_net_map())

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_absent_pin_net_map_reviews_each_source_matched_role_component() -> None:
    findings = tuple(item for item in _report().findings if item.rule_id == RULE_ID)

    assert {item.subject for item in findings} == {
        "U2: active support pin-to-net map coverage is missing",
        "U3: active support pin-to-net map coverage is missing",
    }
    assert all(item.mode == "review" for item in findings)
    assert all("No expected nets are inferred" in item.message for item in findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_partial_map_reviews_only_the_omitted_support_component() -> None:
    findings = tuple(
        item
        for item in _report(net_map=_net_map_without_component("U3")).findings
        if item.rule_id == RULE_ID
    )

    assert tuple(item.subject for item in findings) == (
        "U3: active support pin-to-net map coverage is missing",
    )
    assert "U3 has no pin-to-net map entry" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_partial_pin_inventory_reviews_uncovered_role_map_pins() -> None:
    net_map = support_pin_net_map()
    topology = net_map.requirements[0]
    component = next(item for item in topology.components if item.reference == "U3")
    partial = component.model_copy(
        update={"pins": tuple(pin for pin in component.pins if pin.pin != "U3.3")}
    )
    net_map = net_map.model_copy(
        update={
            "requirements": (
                topology.model_copy(
                    update={
                        "components": tuple(
                            partial if item.reference == "U3" else item
                            for item in topology.components
                        )
                    }
                ),
            )
        }
    )
    finding = next(item for item in _report(net_map=net_map).findings if item.rule_id == RULE_ID)

    assert finding.subject == "U3: active support pin-to-net map coverage is missing"
    assert "pin-to-net map omits U3.3" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_absent_role_map_does_not_invent_support_component_coverage() -> None:
    report = _report(role_map=None, net_map=None)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("mode", "expected_mode", "expected_disposition"),
    (("review", "review", "OPEN"), ("block", "block", "OPEN"), ("off", "off", "RULE_OFF")),
)
def test_coverage_prompt_obeys_project_policy(
    mode: str,
    expected_mode: str,
    expected_disposition: str,
) -> None:
    finding = next(item for item in _report(mode=mode).findings if item.rule_id == RULE_ID)

    assert finding.mode == expected_mode
    assert finding.disposition == expected_disposition


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_ignore_applies_only_while_both_authored_maps_match() -> None:
    original = _report()
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)
    ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=finding.fingerprint,
        reason="Synthetic project has independently reviewed this support role",
    )

    ignored = _report(ignores=(ignore,))
    changed_role_map = support_map().model_copy(update={"basis": "Changed review basis"})
    stale = _report(role_map=changed_role_map, ignores=(ignore,))

    assert any(
        item.disposition == "IGNORED" for item in ignored.findings if item.rule_id == RULE_ID
    )
    assert stale.stale_ignores == (ignore,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_map_order_changes_do_not_change_coverage_fingerprint_or_evidence() -> None:
    original_role_map = support_map()
    topology = original_role_map.requirements[0]
    reordered_role_map = original_role_map.model_copy(
        update={
            "requirements": (
                topology.model_copy(
                    update={
                        "components": tuple(reversed(topology.components)),
                    }
                ),
            )
        }
    )
    # Topology components are the only ordering dimension in this role map.
    original = next(item for item in _report().findings if item.rule_id == RULE_ID)
    reordered = next(
        item for item in _report(role_map=reordered_role_map).findings if item.rule_id == RULE_ID
    )

    assert (reordered.fingerprint, reordered.evidence) == (original.fingerprint, original.evidence)
