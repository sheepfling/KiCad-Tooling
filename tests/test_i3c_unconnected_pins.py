"""Focused tests for one-sided open I3C pin review."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i3c_unconnected_pins import unconnected_i3c_signal_pins
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_same_net import i3c_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]
RULE_ID = "bus.i3c_unconnected_pin"


def _fault(*, open_pin: str = "U1.1") -> NetlistContract:
    if open_pin == "U1.1":
        nets = {"I3C_SCL": ("U1.2",)}
    elif open_pin == "U1.2":
        nets = {"I3C_SDA": ("U1.1",)}
    else:
        raise ValueError(f"unsupported open-pin fixture: {open_pin}")
    return i3c_same_net_netlist().model_copy(update={"nets": nets})


def _report(
    source: NetlistContract,
    mode: Literal["review", "block", "off"] = "review",
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="synthetic I3C"),),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-i3c-open-pin", coach(source), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("open_pin", "paired_pin", "role"), [("U1.1", "U1.2", "SDA"), ("U1.2", "U1.1", "SCL")]
)
def test_one_open_member_reports_its_channel_peer(
    open_pin: str, paired_pin: str, role: str
) -> None:
    fault = _fault(open_pin=open_pin)
    default = _findings(evaluate("synthetic-i3c-open-pin", coach(fault), DesignLintPolicy()))
    finding = _findings(_report(fault))[0]

    assert len(default) == 1
    assert default[0].mode == "off"
    assert finding.subject == f"{open_pin}: {'I3C1_SDA' if role == 'SDA' else 'I3C1_SCL'}"
    assert finding.evidence["i3c_role"] == (role,)
    assert finding.evidence["paired_pin"] == (paired_pin,)
    assert finding.evidence["paired_net"] == ("I3C_SCL" if role == "SDA" else "I3C_SDA",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_all_open_and_both_assigned_pairs_are_quiet() -> None:
    fault = _fault()
    all_open = fault.model_copy(update={"nets": {}})
    both_assigned = i3c_same_net_netlist().model_copy(
        update={"nets": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)}}
    )
    assert not unconnected_i3c_signal_pins(all_open)
    assert not _findings(_report(both_assigned))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_channel_duplicates_inventory_dnp_and_ambiguous_assignments_are_quiet() -> None:
    fault = _fault()
    duplicate = fault.model_copy(
        update={
            "pin_functions": {**fault.pin_functions, "U1.3": "I3C1_SDA"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
        }
    )
    mismatched_channels = fault.model_copy(
        update={"pin_functions": {"U1.1": "I3C1_SDA", "U1.2": "I3C2_SCL"}}
    )
    stale_inventory = fault.model_copy(update={"component_pin_numbers": {"U1": ("1",)}})
    dnp = fault.model_copy(update={"dnp_components": ("U1",)})
    ambiguous = fault.model_copy(update={"nets": {"I3C_SCL": ("U1.2",), "OTHER": ("U1.2",)}})
    connector = fault.model_copy(update={"components": {"J1": fault.components["U1"]}})

    for case in (duplicate, mismatched_channels, stale_inventory, dnp, ambiguous):
        assert not _findings(_report(case))
    assert not _findings(_report(connector))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unique_channels_are_checked_independently() -> None:
    source = _fault().model_copy(
        update={
            "pin_functions": {
                "U1.1": "I3C1_SDA",
                "U1.2": "I3C1_SCL",
                "U1.3": "I3C2_SDA",
                "U1.4": "I3C2_SCL",
            },
            "component_pin_numbers": {"U1": ("1", "2", "3", "4")},
            "nets": {
                "I3C_SCL_1": ("U1.2",),
                "I3C_SDA_2": ("U1.3",),
                "I3C_SCL_2": ("U1.4",),
            },
        }
    )

    findings = _findings(_report(source))
    assert tuple(item.subject for item in findings) == ("U1.1: I3C1_SDA",)
    assert findings[0].evidence["i3c_channel"] == ("1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore() -> None:
    fault = _fault()
    finding = _findings(_report(fault))[0]
    blocked = _findings(_report(fault, "block"))[0]
    disabled = _findings(_report(fault, "off"))[0]
    ignored = _findings(
        _report(
            fault,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="intentional unused I3C line",
            ),
        )
    )[0]
    assert _report(fault, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordering_is_stable_and_connecting_open_pin_clears_prompt() -> None:
    fault = _fault()
    reversed_source = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    first, second = _findings(_report(fault))[0], _findings(_report(reversed_source))[0]
    repaired = fault.model_copy(update={"nets": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)}})
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(repaired))
