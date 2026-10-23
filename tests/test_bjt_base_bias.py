"""Fault, control, policy, and determinism tests for BJT base-bias review."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.component_bjt_base_bias import RULE_ID
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
from tests.design_lint_fixtures.bjt_base_bias import bjt_base_bias_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

PROJECT_ID = "synthetic-bjt-base-bias"


def lint(
    netlist: NetlistContract,
    mode: Literal["review", "block", "off"] | None = "review",
    *,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    rules = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Synthetic policy"),)
    )
    return evaluate(
        PROJECT_ID,
        coach(netlist),
        DesignLintPolicy(rules=rules, ignores=ignores),
    )


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("family", ("npn", "pnp"))
def test_series_driven_bjt_without_visible_base_emitter_resistor_is_opt_in(family: str) -> None:
    fault = bjt_base_bias_netlist(family=family)
    default = lint(fault, mode=None)
    reviewed = lint(fault)

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert reviewed.status == "REVIEW"
    assert findings(reviewed)[0].evidence == {
        "component": ("Q1",),
        "symbol": (f"Transistor_BJT:Q_{family.upper()}_BCE",),
        "base_pin": ("Q1.1",),
        "base_net": ("BASE",),
        "emitter_pin": ("Q1.3",),
        "emitter_net": ("EMITTER",),
        "fitted_base_net_peers": ("R1.2",),
        "visible_base_emitter_bias_resistors": (),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_nonzero_base_emitter_resistor_is_a_control() -> None:
    report = lint(bjt_base_bias_netlist(bias_value="100k"))

    assert report.status == "PASS"
    assert not findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("bias_value", "bias_nets", "dnp"),
    (
        pytest.param("100k", ("BASE", "OTHER"), (), id="wrong-emitter-net"),
        pytest.param("100k", ("BASE", "EMITTER"), ("R2",), id="not-fitted"),
        pytest.param("0", ("BASE", "EMITTER"), (), id="zero-ohm-link"),
        pytest.param("TBD", ("BASE", "EMITTER"), (), id="unparsed-value"),
    ),
)
def test_unrelated_unfitted_or_unrecognized_resistors_do_not_clear_review(
    bias_value: str,
    bias_nets: tuple[str, str],
    dnp: tuple[str, ...],
) -> None:
    report = lint(bjt_base_bias_netlist(bias_value=bias_value, bias_nets=bias_nets, dnp=dnp))

    assert len(findings(report)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_output_drive_is_left_to_the_more_specific_rule() -> None:
    report = lint(bjt_base_bias_netlist(direct_output=True))

    assert not findings(report)
    assert any(item.rule_id == "component.bjt_base_direct_drive" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_peer_dnp_and_unsupported_bjt_cases_are_not_classified() -> None:
    cases = (
        bjt_base_bias_netlist(base_peer=False),
        bjt_base_bias_netlist(dnp=("Q1",)),
        bjt_base_bias_netlist(dnp=("R1",)),
        bjt_base_bias_netlist(symbol="Synthetic:NPN"),
        bjt_base_bias_netlist(inventory=("1", "2")),
        bjt_base_bias_netlist(inventory=()),
        bjt_base_bias_netlist(function_overrides={"Q1.1": "C"}),
        bjt_base_bias_netlist(duplicate_base_assignment=True),
    )

    for observed in cases:
        assert not findings(lint(observed))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_roles_are_resolved_independently_of_pin_numbers() -> None:
    observed = bjt_base_bias_netlist(
        family="pnp",
        symbol="Transistor_BJT:Q_PNP_ECB",
        pin_numbers={"base": "2", "collector": "1", "emitter": "3"},
    )

    finding = findings(lint(observed))[0]
    assert finding.evidence["base_pin"] == ("Q1.2",)
    assert finding.evidence["emitter_pin"] == ("Q1.3",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_the_review() -> None:
    fault = bjt_base_bias_netlist()
    fingerprint = findings(lint(fault))[0].fingerprint
    blocked = lint(fault, mode="block")
    disabled = lint(fault, mode="off")
    ignored = lint(
        fault,
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint,
                reason="Reviewed synthetic topology",
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_input_order_and_repair_preserve_stable_findings() -> None:
    observed = bjt_base_bias_netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    first, second = findings(lint(observed)), findings(lint(reordered))

    assert first == second
    repaired = lint(bjt_base_bias_netlist(bias_value="100k"))
    assert not findings(repaired)
