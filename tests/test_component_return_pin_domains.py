"""Focused regressions for distinct return assignments on one component."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.component_return_domains import component_return_pin_domains

RULE_ID = "component.repeated_return_pin_function"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    observed = component_return_pin_domains() if source is None else source
    return evaluate(
        "synthetic-component-return-domains",
        coach(observed),
        DesignLintPolicy() if policy is None else policy,
    )


def test_split_component_return_pins_request_review_with_exact_evidence() -> None:
    report = _report()
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == "U1 (Lint:MultiReturnComponent): return pins use distinct nets"
    assert finding.evidence == {
        "U1.1": ("RETURN_A",),
        "U1.2": ("RETURN_B",),
        "component_symbol": ("Lint:MultiReturnComponent",),
        "pin_functions": ("U1.1=GND", "U1.2=AGND"),
    }
    assert "does not require those nets to be joined" in finding.message


def test_common_return_pins_are_a_quiet_control() -> None:
    report = _report(component_return_pin_domains(split=False))

    assert report.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(component_return_pin_domains(dnp=True), id="dnp"),
        pytest.param(
            component_return_pin_domains().model_copy(update={"nets": {"RETURN_A": ("U1.1",)}}),
            id="open-pin",
        ),
        pytest.param(
            component_return_pin_domains().model_copy(
                update={"nets": {"RETURN_A": ("U1.1", "U1.2"), "RETURN_B": ("U1.1",)}}
            ),
            id="ambiguous-pin",
        ),
    ],
)
def test_dnp_open_and_ambiguous_assignments_stay_outside_the_predicate(source) -> None:
    report = _report(source)

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_connector_references_remain_with_connector_return_rules() -> None:
    source = component_return_pin_domains().model_copy(
        update={
            "components": {"J1": component_return_pin_domains().components["U1"]},
            "nets": {"RETURN_A": ("J1.1",), "RETURN_B": ("J1.2",)},
            "component_symbols": {"J1": "Connector_Generic:Conn_01x02"},
            "component_pin_numbers": {"J1": ("1", "2")},
            "pin_functions": {"J1.1": "GND", "J1.2": "AGND"},
        }
    )
    report = evaluate(
        "synthetic-component-return-domains",
        coach(source),
        DesignLintPolicy(),
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_intentional_split_can_be_disabled_or_promoted_by_project_policy() -> None:
    source = component_return_pin_domains()
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID, mode="off", reason="intentional domain split"
                ),
            )
        ),
    )
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID, mode="block", reason="reviewed ground contract"
                ),
            )
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="reviewed intentional analog/digital return split",
                ),
            )
        ),
    )

    assert disabled.status == "PASS"
    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"


def test_mapping_order_is_stable_and_commoning_clears_the_finding() -> None:
    source = component_return_pin_domains()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    repeated = next(item for item in _report(reordered).findings if item.rule_id == RULE_ID)
    repaired = _report(component_return_pin_domains(split=False))

    assert repeated.evidence == original.evidence
    assert repeated.fingerprint == original.fingerprint
    assert not any(item.rule_id == RULE_ID for item in repaired.findings)
