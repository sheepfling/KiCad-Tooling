"""Focused regressions for CANH/CANL pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_line_named_rail import can_line_named_rail_netlist

RULE_ID = "bus.can_line_on_named_rail"

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
        "synthetic-can-line-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "function", "rail", "role", "peer_pin", "peer_function"),
    (
        ("U1.1", "CANH", "GND", "return-like", "U1.2", "CANL"),
        ("U1.2", "CANL", "+3V3", "supply-like", "U1.1", "CANH"),
    ),
)
def test_can_bus_line_pin_assigned_to_named_rail_requests_review(
    pin: str,
    function: str,
    rail: str,
    role: str,
    peer_pin: str,
    peer_function: str,
) -> None:
    source = can_line_named_rail_netlist(
        high_net=rail if pin == "U1.1" else "CANH_BUS",
        low_net=rail if pin == "U1.2" else "CANL_BUS",
    )
    report = _report(source)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "can_line_role": (function,),
        "complementary_line_pin": (peer_pin,),
        "complementary_line_function": (peer_function,),
        "assigned_net": (rail,),
        "net_label_role_clue": (role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "does not assess PCB copper" in finding.message


def test_compacted_can_high_low_aliases_are_recognized() -> None:
    source = can_line_named_rail_netlist(
        high_net="GND",
        low_net="+3V3",
        high_function="CAN_HIGH",
        low_function="CAN_LOW",
    )
    findings = tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)

    assert tuple(item.evidence["can_line_role"] for item in findings) == (("CANH",), ("CANL",))


def test_neutral_rail_labels_and_non_line_functions_are_quiet() -> None:
    neutral = can_line_named_rail_netlist(high_net="CANH_BUS", low_net="CANL_BUS")
    unsupported = can_line_named_rail_netlist(high_function="H", low_function="L")

    for control in (neutral, unsupported):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_connector_and_incomplete_pairs_are_skipped() -> None:
    source = can_line_named_rail_netlist()
    controls = (
        can_line_named_rail_netlist(dnp=True),
        source.model_copy(update={"nets": {"CANL_BUS": ("U1.2",)}}),
        source.model_copy(update={"nets": {"GND": ("U1.1",), "CANH_BUS": ("U1.1",)}}),
        source.model_copy(
            update={
                "pin_functions": {
                    "U1.1": "CANH",
                    "U1.2": "CANL",
                    "U1.3": "CAN_HIGH",
                },
                "component_pin_numbers": {"U1": ("1", "2", "3")},
                "nets": {"GND": ("U1.1",), "CANL_BUS": ("U1.2",), "CANH_BUS": ("U1.3",)},
            }
        ),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "CANL_BUS": ("J1.2",)},
                "component_symbols": {"J1": "Synthetic:CAN_Transceiver"},
                "pin_functions": {"J1.1": "CANH", "J1.2": "CANL"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "CANH"}}),
    )

    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_an_intentional_strap() -> None:
    source = can_line_named_rail_netlist()
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
                    reason="reviewed CAN transceiver strap",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_mapping_order_is_stable_and_corrected_line_assignments_clear_review() -> None:
    fault = can_line_named_rail_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    repaired = can_line_named_rail_netlist(high_net="CANH_BUS", low_net="CANL_BUS")
    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
