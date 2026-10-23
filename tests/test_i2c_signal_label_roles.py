"""Focused I2C SDA/SCL pin-function and net-label regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.i2c_signal_label import i2c_signal_label_role_candidates
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist

RULE_ID = "bus.i2c_signal_label_role_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_i2c_line_labels_are_reviewed_while_both_pins_stay_assigned() -> None:
    source = i2c_signal_label_netlist(reversed_labels=True)

    findings = _findings(source)

    assert tuple(item.subject for item in findings) == (
        "U1.1: SDA on I2C_SCL",
        "U1.2: SCL on I2C_SDA",
    )
    assert findings[0].evidence["pin_role"] == ("SDA",)
    assert findings[0].evidence["net_role"] == ("SCL",)
    assert (
        evaluate("synthetic-i2c-signal-label", coach(source), DesignLintPolicy()).status == "REVIEW"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_aliases_and_neutral_or_indexed_labels_stay_unclassified() -> None:
    source = i2c_signal_label_netlist()
    prefixed = source.model_copy(update={"nets": {"I2C_SDA": ("U1.1",), "SCL": ("U1.2",)}})
    neutral = source.model_copy(update={"nets": {"DATA_A": ("U1.1",), "CLOCK_A": ("U1.2",)}})
    indexed = source.model_copy(update={"nets": {"I2C1_SCL": ("U1.1",), "I2C1_SDA": ("U1.2",)}})
    punctuated = source.model_copy(
        update={
            "nets": {"i2c-sda": ("U1.1",), "s.c.l": ("U1.2",)},
            "pin_functions": {"U1.1": "s.d.a", "U1.2": "i2c-scl"},
        }
    )
    indexed_functions = i2c_signal_label_netlist(reversed_labels=True).model_copy(
        update={"pin_functions": {"U1.1": "I2C1_SDA", "U1.2": "I2C1_SCL"}}
    )
    vendor_aliases = i2c_signal_label_netlist(reversed_labels=True).model_copy(
        update={"pin_functions": {"U1.1": "TWI_DATA", "U1.2": "TWI_CLOCK"}}
    )

    assert not _findings(source)
    assert not _findings(prefixed)
    assert not _findings(neutral)
    assert not _findings(indexed)
    assert not _findings(punctuated)
    assert not _findings(indexed_functions)
    assert not _findings(vendor_aliases)
    assert not i2c_signal_label_role_candidates(source)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_and_multiply_assigned_pins_are_not_classified() -> None:
    source = i2c_signal_label_netlist(reversed_labels=True)
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"I2C_SCL": ("U1.2",)}})
    multiply_assigned = source.model_copy(
        update={
            "nets": {
                "I2C_SCL": ("U1.1", "U1.2"),
                "I2C_SDA": ("U1.1", "U1.2"),
            }
        }
    )

    assert not _findings(dnp)
    assert not _findings(open_pin)
    assert not _findings(multiply_assigned)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_modes_and_exact_fingerprint_ignore_are_supported() -> None:
    source = i2c_signal_label_netlist(reversed_labels=True)
    reviewed = evaluate("synthetic-i2c-signal-label", coach(source), DesignLintPolicy())
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    blocked = evaluate(
        "synthetic-i2c-signal-label",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    disabled = evaluate(
        "synthetic-i2c-signal-label",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional map"),)
        ),
    )
    ignored = evaluate(
        "synthetic-i2c-signal-label",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=finding.fingerprint, reason="Reviewed"
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert all(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        ).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_correcting_labels_clears_the_candidate() -> None:
    fault = i2c_signal_label_netlist(reversed_labels=True)
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )

    assert _findings(reordered) == _findings(fault)
    assert not _findings(i2c_signal_label_netlist())
