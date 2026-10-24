"""Focused regressions for I2C signal pins assigned to named rails."""

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
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist
from tests.design_lint_fixtures.i2c_signal_named_rail import i2c_signal_on_named_rail_netlist

RULE_ID = "bus.i2c_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-i2c-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("rail_name", "pin", "function", "role_clue"),
    (
        ("GND", "U1.1", "SDA", "return-like"),
        ("0V PWM 2", "U1.2", "SCL", "return-like"),
        ("+3V3", "U1.1", "SDA", "supply-like"),
    ),
)
def test_explicit_i2c_pin_on_named_rail_requests_review_with_exact_evidence(
    rail_name: str, pin: str, function: str, role_clue: str
) -> None:
    report = _report(i2c_signal_on_named_rail_netlist(rail_name=rail_name, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {role_clue} net {rail_name}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (function,),
        "assigned_net": (rail_name,),
        "net_label_role_clue": (role_clue,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


def test_neutral_labels_and_unsupported_pin_functions_are_controls() -> None:
    source = i2c_signal_on_named_rail_netlist(rail_name="POWER_SENSE")
    unrecognized_function = source.model_copy(
        update={"pin_functions": {"U1.1": "I2C1_SDA", "U1.2": "SCL"}}
    )
    incomplete_inventory = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})
    connector = source.model_copy(
        update={
            "components": {
                "J1": source.components["U1"],
            },
            "nets": {"POWER_SENSE": ("J1.1",), "I2C_SCL": ("J1.2",)},
            "component_symbols": {"J1": "Connector_Generic:Conn_01x02"},
            "pin_functions": {"J1.1": "SDA", "J1.2": "SCL"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    assert not any(item.rule_id == RULE_ID for item in _report(source).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(unrecognized_function).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(incomplete_inventory).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(connector).findings)


def test_dnp_open_and_ambiguous_assignments_stay_outside_the_predicate() -> None:
    source = i2c_signal_on_named_rail_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"I2C_SCL": ("U1.2",)}})
    ambiguous = source.model_copy(
        update={
            "nets": {
                "GND": ("U1.1",),
                "0V": ("U1.1",),
                "I2C_SCL": ("U1.2",),
            }
        }
    )

    for control in (dnp, open_pin, ambiguous):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_and_exact_ignore_control_the_review() -> None:
    source = i2c_signal_on_named_rail_netlist()
    default = _report(source)
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    block = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="test policy"),)
        ),
    )
    off = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="test policy"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="reviewed intentional I2C rail strap",
                ),
            )
        ),
    )

    assert finding.mode == "review"
    assert block.status == "FAIL"
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert off_finding.disposition == "RULE_OFF"
    assert ignored_finding.disposition == "IGNORED"


def test_mapping_order_is_stable_and_repairing_assignment_clears_review() -> None:
    fault = i2c_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    corrected = i2c_signal_label_netlist()

    fault_findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    assert tuple(item.model_dump() for item in fault_findings) == tuple(
        item.model_dump()
        for item in (item for item in _report(reordered).findings if item.rule_id == RULE_ID)
    )
    assert not any(item.rule_id == RULE_ID for item in _report(corrected).findings)
