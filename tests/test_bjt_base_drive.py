"""Fault, control, policy, and deterministic-order tests for BJT base drive."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.bjt_base_drive import bjt_base_drive_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.bjt_base_direct_drive"
PROJECT_ID = "synthetic-bjt-base-drive"


def lint(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(PROJECT_ID, coach(netlist), policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def rule_policy(mode: str = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review direct synthetic BJT base drive",
            ),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("family", ("npn", "pnp"))
def test_bjt_base_sharing_an_output_net_is_reviewed(family: str) -> None:
    report = lint(bjt_base_drive_netlist(family=family))

    assert report.status == "REVIEW"
    finding = findings(report)[0]
    assert finding.mode == "review"
    assert finding.evidence["component"] == ("Q1",)
    assert finding.evidence["base_pin"] == ("Q1.1",)
    assert finding.evidence["base_net"] == ("BASE_DRIVE",)
    assert finding.evidence["output_pins"] == ("U1.1",)
    assert finding.evidence["output_pin_types"] == ("U1.1=output",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_functions_map_the_base_independent_of_pin_number() -> None:
    observed = bjt_base_drive_netlist(
        family="pnp",
        pin_numbers={"base": "3", "collector": "1", "emitter": "2"},
    )
    finding = findings(lint(observed))[0]

    assert finding.evidence["base_pin"] == ("Q1.3",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_power_output_pin_type_is_also_output_capable() -> None:
    finding = findings(lint(bjt_base_drive_netlist(driver_type="power_out")))[0]

    assert finding.evidence["output_pin_types"] == ("U1.1=power_out",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_series_resistor_and_incomplete_or_unsupported_cases_stay_quiet() -> None:
    direct = bjt_base_drive_netlist()
    cases = (
        bjt_base_drive_netlist(series_resistor=True),
        bjt_base_drive_netlist(driver_type="input"),
        bjt_base_drive_netlist(driver_dnp=True),
        bjt_base_drive_netlist(bjt_dnp=True),
        direct.model_copy(
            update={"component_symbols": {"Q1": "Training:BJT", "U1": "Synthetic:Output"}}
        ),
        direct.model_copy(update={"component_pin_numbers": {"Q1": ("1", "2"), "U1": ("1",)}}),
        direct.model_copy(
            update={
                "nets": {**direct.nets, "AMBIGUOUS": ("Q1.1",)},
            }
        ),
        direct.model_copy(update={"pin_functions": {**direct.pin_functions, "Q1.2": "B"}}),
    )

    assert findings(lint(direct))
    for observed in cases:
        assert findings(lint(observed)) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_the_finding() -> None:
    fault = bjt_base_drive_netlist()
    fingerprint = findings(lint(fault))[0].fingerprint
    blocked = lint(fault, rule_policy("block"))
    disabled = lint(fault, rule_policy("off"))
    ignored = lint(
        fault,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review direct synthetic BJT base drive",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint,
                    reason="Synthetic direct-drive case reviewed",
                ),
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert findings(blocked)[0].mode == "block"
    assert disabled.status == "PASS"
    assert findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_input_ordering_preserves_the_fingerprint_and_evidence() -> None:
    observed = bjt_base_drive_netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    first = findings(lint(observed))[0]
    second = findings(lint(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
