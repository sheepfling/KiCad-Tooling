"""Focused regressions for I3C signal pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_signal_roles import i3c_signal_identity
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_signal_named_rail import i3c_signal_named_rail_netlist

RULE_ID = "bus.i3c_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-i3c-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "function", "net", "role"),
    (
        ("U1.1", "I3C1_SDA", "GND", "return-like"),
        ("U1.2", "I3C1_SCL", "+3V3", "supply-like"),
    ),
)
def test_explicit_i3c_pin_on_named_rail_requests_review(
    pin: str, function: str, net: str, role: str
) -> None:
    report = _report(i3c_signal_named_rail_netlist())
    finding = next(
        item
        for item in report.findings
        if item.rule_id == RULE_ID and item.subject.startswith(f"{pin}:")
    )

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: I3C {function.rsplit('_', 1)[1]} on {role} net {net}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "i3c_role": (function.rsplit("_", 1)[1],),
        "i3c_channel": ("1",),
        "assigned_net": (net,),
        "net_label_role_clue": (role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of I3C use" in finding.message
    assert "passive paths and PCB copper are not traced" in finding.message


def test_i3c_function_aliases_are_bounded_and_channel_aware() -> None:
    unindexed = i3c_signal_identity("I3C_SDA")
    zero_indexed = i3c_signal_identity("I3C0_SDA")
    indexed_clock = i3c_signal_identity("i3c1-scl")
    compact_data = i3c_signal_identity("I3C2SDA")
    assert unindexed is not None and unindexed.channel is None
    assert zero_indexed is not None and zero_indexed.channel == "0"
    assert indexed_clock is not None and indexed_clock.role == "SCL"
    assert compact_data is not None and compact_data.channel == "2"
    assert i3c_signal_identity("I2C1_SDA") is None
    assert i3c_signal_identity("I3C_SDA/I3C_SCL") is None
    assert i3c_signal_identity("I3C3_SDAT") is None

    source = i3c_signal_named_rail_netlist(
        sda_function="SDA/I3C1_SDA", scl_function="I2C1_SCL/I3C1_SCL"
    )
    findings = tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)
    assert len(findings) == 2


def test_neutral_labels_mismatched_channels_and_unsupported_functions_are_controls() -> None:
    source = i3c_signal_named_rail_netlist()
    controls = (
        i3c_signal_named_rail_netlist(sda_net="I3C_SDA_BUS", scl_net="I3C_SCL_BUS"),
        i3c_signal_named_rail_netlist(sda_function="I3C1_SDA", scl_function="I3C2_SCL"),
        i3c_signal_named_rail_netlist(sda_function="SDA", scl_function="SCL"),
        i3c_signal_named_rail_netlist(dnp=True),
        source.model_copy(update={"nets": {"I3C1_SCL_BUS": ("U1.2",)}}),
        source.model_copy(update={"nets": {"GND": ("U1.1", "U1.2"), "+3V3": ("U1.1", "U1.2")}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "+3V3": ("J1.2",)},
                "component_symbols": {"J1": "Connector_Generic:Conn_01x02"},
                "pin_functions": {"J1.1": "I3C1_SDA", "J1.2": "I3C1_SCL"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
    )

    for index, control in enumerate(controls):
        findings = tuple(
            item.subject for item in _report(control).findings if item.rule_id == RULE_ID
        )
        assert not findings, f"control {index} unexpectedly produced {findings}"

    partial_i3c = source.model_copy(update={"nets": {"+3V3": ("U1.2",)}})
    assert tuple(
        item.subject for item in _report(partial_i3c).findings if item.rule_id == RULE_ID
    ) == ("U1.2: I3C SCL on supply-like net +3V3",)


def test_project_policy_can_block_disable_or_ignore_a_review() -> None:
    source = i3c_signal_named_rail_netlist()
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="intentional I3C rail assignment",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )
    assert next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == (
        "IGNORED"
    )


def test_mapping_order_is_stable_and_correcting_both_nets_clears_review() -> None:
    fault = i3c_signal_named_rail_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    repaired = i3c_signal_named_rail_netlist(sda_net="I3C_SDA_BUS", scl_net="I3C_SCL_BUS")
    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)

    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
