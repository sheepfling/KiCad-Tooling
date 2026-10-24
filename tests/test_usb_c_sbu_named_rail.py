"""Focused regressions for USB-C SBU controller pins on named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_signal_roles import usb_c_sbu_role
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist

RULE_ID = "bus.usb_c_sbu_signal_on_named_rail"

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
        "synthetic-usb-c-sbu-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "function", "net", "role"),
    (
        ("U1.1", "SBU1", "GND", "return-like"),
        ("U1.2", "SBU2", "+3V3", "supply-like"),
    ),
)
def test_unique_usb_c_sbu_function_on_named_rail_requests_review(
    pin: str,
    function: str,
    net: str,
    role: str,
) -> None:
    source = usb_c_sbu_named_rail_netlist(
        sbu1_net=net if pin == "U1.1" else "SBU1_BUS",
        sbu2_net=net if pin == "U1.2" else "SBU2_BUS",
    )
    report = _report(source)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {role} net {net}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "usb_c_sbu_role": (function,),
        "assigned_net": (net,),
        "net_label_role_clue": (role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "does not trace passive paths" in finding.message


def test_sbu_aliases_are_bounded_and_share_one_parser() -> None:
    assert usb_c_sbu_role("SBU-1") == "SBU1"
    assert usb_c_sbu_role("sbu_2") == "SBU2"
    assert usb_c_sbu_role("SBU") is None
    assert usb_c_sbu_role("SBU3") is None
    source = usb_c_sbu_named_rail_netlist(sbu1_function="SBU-1", sbu2_function="sbu_2")

    assert tuple(
        item.evidence["usb_c_sbu_role"]
        for item in _report(source).findings
        if item.rule_id == RULE_ID
    ) == (("SBU1",), ("SBU2",))


def test_neutral_labels_and_unrecognized_functions_are_quiet() -> None:
    controls = (
        usb_c_sbu_named_rail_netlist(sbu1_net="SBU1_BUS", sbu2_net="SBU2_BUS"),
        usb_c_sbu_named_rail_netlist(sbu1_function="AUX1", sbu2_function="AUX2"),
    )

    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_connector_and_incomplete_cases_are_skipped() -> None:
    source = usb_c_sbu_named_rail_netlist(sbu1_net="SBU1_BUS", sbu2_net="SBU2_BUS")
    controls = (
        usb_c_sbu_named_rail_netlist(dnp=True),
        source.model_copy(update={"nets": {"SBU2_BUS": ("U1.2",)}}),
        source.model_copy(
            update={
                "nets": {
                    "GND": ("U1.1",),
                    "+3V3": ("U1.1",),
                    "SBU2_BUS": ("U1.2",),
                }
            }
        ),
        source.model_copy(
            update={
                "pin_functions": {"U1.1": "SBU1", "U1.2": "SBU2", "U1.3": "SBU1"},
                "component_pin_numbers": {"U1": ("1", "2", "3")},
                "nets": {"GND": ("U1.1", "U1.3"), "SBU2_BUS": ("U1.2",)},
            }
        ),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "SBU2_BUS": ("J1.2",)},
                "component_symbols": {"J1": "Synthetic:USB_C_Controller"},
                "pin_functions": {"J1.1": "SBU1", "J1.2": "SBU2"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
    )

    for index, control in enumerate(controls):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings), index


def test_project_policy_can_block_disable_or_ignore_an_intentional_assignment() -> None:
    source = usb_c_sbu_named_rail_netlist()
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
                    reason="intentional USB-C SBU assignment",
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


def test_mapping_order_is_stable_and_corrected_assignments_clear_review() -> None:
    fault = usb_c_sbu_named_rail_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    repaired = usb_c_sbu_named_rail_netlist(sbu1_net="SBU1_BUS", sbu2_net="SBU2_BUS")
    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
