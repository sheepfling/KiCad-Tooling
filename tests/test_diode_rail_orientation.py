"""Fault, control, policy, and deterministic-order tests for diode rail lint."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from tests.design_lint_fixtures.diode_rail_orientation import netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.diode_anode_below_cathode_on_named_rails"
PROJECT_ID = "synthetic-diode-rail-orientation"


def lint(observed, *, mode: str | None = None, ignores=()):
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic diode orientation policy",
            ),
        )
    )
    return evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=observed,
            netlist_sha256="b" * 64,
        ),
        DesignLintPolicy(rules=rules, ignores=tuple(ignores)),
    )


def diode_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("symbol", ("Device:D", "Device:D_Schottky"))
def test_supported_diode_with_anode_below_cathode_is_reviewed(symbol: str) -> None:
    report = lint(netlist(symbol=symbol))

    assert report.status == "REVIEW"
    assert len(diode_findings(report)) == 1
    finding = diode_findings(report)[0]
    assert finding.subject == "D1: diode anode is below its cathode on named rails"
    assert finding.evidence["anode_pin"] == ("D1.2",)
    assert finding.evidence["anode_net"] == ("+3V3",)
    assert finding.evidence["anode_label_value_volts"] == ("3.3",)
    assert finding.evidence["cathode_pin"] == ("D1.1",)
    assert finding.evidence["cathode_net"] == ("+5V",)
    assert finding.evidence["cathode_label_value_volts"] == ("5",)
    assert "Reverse-biased clamp and isolation uses can be valid" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("anode_net", "cathode_net"),
    (
        pytest.param("-5V", "-3V3", id="negative-rails"),
        pytest.param("-5V", "+5V", id="cross-zero-rails"),
    ),
)
def test_signed_rail_values_define_polarity_order(anode_net: str, cathode_net: str) -> None:
    finding = diode_findings(lint(netlist(anode_net=anode_net, cathode_net=cathode_net)))[0]

    assert finding.evidence["anode_net"] == (anode_net,)
    assert finding.evidence["cathode_net"] == (cathode_net,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("anode_net", "cathode_net"),
    (
        pytest.param("+5V", "+3V3", id="forward-ordered-positive-rails"),
        pytest.param("-3V3", "-5V", id="forward-ordered-negative-rails"),
        pytest.param("+5V", "5V", id="equal-value-aliases"),
        pytest.param("VCC", "+5V", id="unknown-anode-label"),
        pytest.param("+3V3", "GND", id="return-label-is-not-numeric-rail"),
    ),
)
def test_forward_equal_unknown_and_return_controls_are_quiet(
    anode_net: str,
    cathode_net: str,
) -> None:
    assert not diode_findings(lint(netlist(anode_net=anode_net, cathode_net=cathode_net)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_functions_define_anode_and_cathode_not_pin_numbers() -> None:
    source = netlist(
        pin_functions={"D1.1": "A", "D1.2": "K"},
        nets={"+3V3": ("D1.1",), "+5V": ("D1.2",)},
    )

    finding = diode_findings(lint(source))[0]

    assert finding.evidence["anode_pin"] == ("D1.1",)
    assert finding.evidence["cathode_pin"] == ("D1.2",)
    assert finding.evidence["anode_net"] == ("+3V3",)
    assert finding.evidence["cathode_net"] == ("+5V",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("symbol", "pin_numbers", "pin_functions", "dnp"),
    (
        pytest.param("Device:D_Zener", ("1", "2"), {"D1.1": "K", "D1.2": "A"}, (), id="zener"),
        pytest.param("Device:D_TVS", ("1", "2"), {"D1.1": "K", "D1.2": "A"}, (), id="tvs"),
        pytest.param(
            "Synthetic:Diode", ("1", "2"), {"D1.1": "K", "D1.2": "A"}, (), id="custom-symbol"
        ),
        pytest.param("Device:D", ("1",), {"D1.1": "K"}, (), id="incomplete-inventory"),
        pytest.param("Device:D", ("1", "1"), {"D1.1": "K"}, (), id="duplicate-inventory"),
        pytest.param("Device:D", ("1", "2"), {"D1.1": "K", "D1.2": "~"}, (), id="missing-role"),
        pytest.param(
            "Device:D", ("1", "2"), {"D1.1": "K", "D1.2": "A", "D2.1": "A"}, ("D1",), id="dnp"
        ),
    ),
)
def test_unsupported_or_incomplete_diodes_are_not_classified(
    symbol: str,
    pin_numbers: tuple[str, ...],
    pin_functions: dict[str, str],
    dnp: tuple[str, ...],
) -> None:
    assert not diode_findings(
        lint(
            netlist(
                symbol=symbol,
                pin_numbers=pin_numbers,
                pin_functions=pin_functions,
                dnp=dnp,
            )
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_ambiguous_and_same_net_assignments_are_not_classified() -> None:
    incomplete = netlist(nets={"+5V": ("D1.1",)})
    ambiguous = netlist(nets={"+3V3": ("D1.2",), "+5V": ("D1.1", "D1.2")})
    same_net = netlist(nets={"+3V3": ("D1.1", "D1.2")})

    assert not diode_findings(lint(incomplete))
    assert not diode_findings(lint(ambiguous))
    assert not diode_findings(lint(same_net))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_supports_review_block_off_and_exact_ignore() -> None:
    source = netlist()
    finding = diode_findings(lint(source))[0]
    blocked = lint(source, mode="block")
    disabled = lint(source, mode="off")
    ignored = lint(
        source,
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic project documents the reverse-biased clamp topology",
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert diode_findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert diode_findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rail_correction_and_input_reordering_are_deterministic() -> None:
    fault = netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    corrected = netlist(anode_net="+5V", cathode_net="+3V3")
    finding = diode_findings(lint(fault))[0]
    reordered_finding = diode_findings(lint(reordered))[0]

    assert (finding.fingerprint, finding.evidence) == (
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )
    assert not diode_findings(lint(corrected))
