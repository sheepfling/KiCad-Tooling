"""Synthetic review cases for missing visible MOSFET gate-source bias."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from tests.design_lint_fixtures.mosfet_gate_source_bias import netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_gate_without_visible_source_bias"
PROJECT_ID = "synthetic-mosfet-gate-source-bias"


def lint(observed, *, mode: str | None = "review", ignores=()):
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Synthetic fixture policy"),
        )
    )
    return evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=observed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(rules=rules, ignores=tuple(ignores)),
    )


def bias_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_gate_peer_without_visible_source_resistor_is_opt_in_review() -> None:
    default = lint(netlist(), mode=None)
    reviewed = lint(netlist())

    assert default.status == "PASS"
    assert bias_findings(default)[0].disposition == "RULE_OFF"
    assert reviewed.status == "REVIEW"
    assert len(bias_findings(reviewed)) == 1
    assert bias_findings(reviewed)[0].evidence == {
        "component": ("Q1",),
        "symbol": ("Transistor_FET:Q_NMOS_GDS",),
        "gate_pin": ("Q1.2",),
        "gate_net": ("GATE",),
        "source_pin": ("Q1.3",),
        "source_net": ("SOURCE",),
        "fitted_gate_peers": ("U1.1",),
        "visible_source_bias_resistors": (),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fitted_nonzero_resistor_directly_between_gate_and_source_is_control() -> None:
    report = lint(netlist(resistor_value="100k"))

    assert report.status == "PASS"
    assert not bias_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("resistor_value", "resistor_nets", "dnp"),
    (
        pytest.param("100k", ("GATE", "OTHER"), (), id="wrong-source-net"),
        pytest.param("100k", ("GATE", "SOURCE"), ("R1",), id="not-fitted"),
        pytest.param("0", ("GATE", "SOURCE"), (), id="zero-ohm-link-is-not-bias"),
    ),
)
def test_unrelated_unfitted_or_zero_ohm_resistors_do_not_clear_review(
    resistor_value: str,
    resistor_nets: tuple[str, str],
    dnp: tuple[str, ...],
) -> None:
    report = lint(netlist(resistor_value=resistor_value, resistor_nets=resistor_nets, dnp=dnp))

    assert len(bias_findings(report)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_gate_peer_leaves_open_gate_to_the_existing_gate_review() -> None:
    report = lint(netlist(gate_net_members=("U1.1",), dnp=("U1",)))

    assert not bias_findings(report)
    assert any(item.rule_id == "component.mosfet_gate_without_peer" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("symbol", "inventory", "gate_function", "source_function", "dnp"),
    (
        pytest.param("Synthetic:Q_NMOS_GDS", ("1", "2", "3"), "G", "S", (), id="unknown-symbol"),
        pytest.param("Transistor_FET:Q_NMOS_GDS", ("1", "2"), "G", "S", (), id="incomplete"),
        pytest.param(
            "Transistor_FET:Q_NMOS_GDS", ("1", "2", "3"), "G1", "S", (), id="unknown-gate"
        ),
        pytest.param(
            "Transistor_FET:Q_NMOS_GDS", ("1", "2", "3"), "G", "SRC", (), id="unknown-source"
        ),
        pytest.param(
            "Transistor_FET:Q_NMOS_GDS", ("1", "2", "3"), "G", "S", ("Q1",), id="dnp-device"
        ),
    ),
)
def test_unsupported_identity_or_incomplete_native_roles_are_controls(
    symbol: str,
    inventory: tuple[str, ...],
    gate_function: str,
    source_function: str,
    dnp: tuple[str, ...],
) -> None:
    report = lint(
        netlist(
            symbol=symbol,
            inventory=inventory,
            gate_function=gate_function,
            source_function=source_function,
            dnp=dnp,
        )
    )

    assert not bias_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "nets",
    (
        pytest.param({"DRAIN": ("Q1.1",), "SOURCE": ("Q1.3", "U1.1")}, id="gate-unassigned"),
        pytest.param({"DRAIN": ("Q1.1",), "GATE": ("Q1.2", "U1.1")}, id="source-unassigned"),
        pytest.param(
            {"DRAIN": ("Q1.1",), "GATE": ("Q1.2", "U1.1"), "SOURCE": ("Q1.3",), "OTHER": ("Q1.2",)},
            id="ambiguous-gate",
        ),
        pytest.param(
            {"DRAIN": ("Q1.1",), "GATE_SOURCE": ("Q1.2", "Q1.3", "U1.1")},
            id="gate-shared-with-source",
        ),
    ),
)
def test_missing_or_ambiguous_gate_source_assignments_are_not_bias_findings(
    nets: Mapping[str, tuple[str, ...]],
) -> None:
    report = lint(netlist().model_copy(update={"nets": nets}))

    assert not bias_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_bias_review_obeys_project_policy_and_exact_ignore() -> None:
    open_finding = bias_findings(lint(netlist()))[0]
    blocked = lint(netlist(), mode="block")
    disabled = lint(netlist(), mode="off")
    ignored = lint(
        netlist(),
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=open_finding.fingerprint,
                reason="Reviewed driver guarantees the required state",
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert bias_findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert bias_findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_adding_source_bias_and_reordering_net_inventory_clear_stably() -> None:
    fault = lint(netlist())
    stable = lint(
        netlist().model_copy(update={"nets": dict(reversed(tuple(netlist().nets.items())))})
    )
    control = lint(netlist(resistor_value="100k"))

    assert (bias_findings(fault)[0].fingerprint, bias_findings(fault)[0].evidence) == (
        bias_findings(stable)[0].fingerprint,
        bias_findings(stable)[0].evidence,
    )
    assert not bias_findings(control)
