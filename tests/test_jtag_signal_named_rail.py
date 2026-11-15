"""Focused regressions for recognized JTAG signals assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.jtag_signal_inventory import JtagEndpointInventory
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_signal_named_rail import jtag_signal_named_rail_netlist

RULE_ID = "bus.jtag_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None):
    return evaluate(
        "synthetic-jtag-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _findings(source: NetlistContract) -> tuple:
    return tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)


@pytest.mark.parametrize(
    ("number", "rail", "function", "role"),
    (
        ("1", "GND", "JTAG_TCK", "test_clock"),
        ("2", "+3V3", "JTAG_TMS", "test_mode_select"),
        ("3", "GND", "JTAG_TDI", "test_data_in"),
        ("4", "+3V3", "JTAG_TDO", "test_data_out"),
        ("5", "GND", "JTAG_TRST", "test_reset"),
        ("6", "+3V3", "RTCK", "return_clock"),
    ),
)
def test_explicit_jtag_functions_on_named_rails_request_review(
    number: str, rail: str, function: str, role: str
) -> None:
    source = jtag_signal_named_rail_netlist(
        functions=("JTAG_TCK", "JTAG_TMS", "JTAG_TDI", "JTAG_TDO", "JTAG_TRST", "RTCK"),
        rail_pins={number: rail},
    )
    finding = next(item for item in _findings(source) if item.subject.startswith(f"U1.{number}:"))

    assert finding.subject == (
        f"U1.{number}: {function} on {'return-like' if rail == 'GND' else 'supply-like'} net {rail}"
    )
    assert finding.evidence == {
        "pin": (f"U1.{number}",),
        "pin_function": (function,),
        "jtag_role": (role,),
        "jtag_identity_basis": ("explicit JTAG pin-function metadata",),
        "assigned_net": (rail,),
        "net_label_role_clue": ("return-like" if rail == "GND" else "supply-like",),
        "component_pin_inventory": ("1", "2", "3", "4", "5", "6"),
    }
    assert finding.mode == "review"
    assert "do not prove an active JTAG interface" in finding.message


def test_generic_tck_tms_pair_identifies_connector_but_not_swd_or_spi() -> None:
    source = jtag_signal_named_rail_netlist(
        reference="J1",
        functions=("TCK", "TMS", "TDI", "TDO"),
        rail_pins={"3": "GND"},
    )
    finding = _findings(source)[0]
    endpoint = JtagEndpointInventory.from_netlist(source).named_rail_signal_pins("J1")

    assert finding.subject == "J1.3: TDI on return-like net GND"
    assert finding.evidence["jtag_identity_basis"] == ("unique assigned native TCK/TMS pair",)
    assert tuple((item.pin, item.role) for item in endpoint) == (
        ("J1.1", "test_clock"),
        ("J1.2", "test_mode_select"),
        ("J1.3", "test_data_in"),
        ("J1.4", "test_data_out"),
    )
    assert not _findings(
        jtag_signal_named_rail_netlist(
            functions=("JTCK", "JTMS", "SWDIO", "SWCLK"), rail_pins={"3": "GND"}
        )
    )
    assert not _findings(
        jtag_signal_named_rail_netlist(
            functions=("SCK", "MOSI", "MISO", "CS"), rail_pins={"3": "GND"}
        )
    )


def test_incomplete_ambiguous_open_and_dnp_endpoints_are_controls() -> None:
    generic = ("TCK", "TMS", "TDI", "TDO")
    explicit_duplicate = ("JTAG_TCK", "JTAG_TMS", "JTAG_TDI", "JTAG_TDI")
    generic_duplicate = ("TCK", "TMS", "TDI", "TDI")
    open_mode = jtag_signal_named_rail_netlist(
        functions=generic, rail_pins={"3": "GND"}
    ).model_copy(update={"nets": {"GND": ("U1.3",), "DEBUG_SIGNAL_1": ("U1.1",)}})
    controls = (
        jtag_signal_named_rail_netlist(rail_pins={"1": "JTAG_TCK"}),
        jtag_signal_named_rail_netlist(dnp=True, rail_pins={"1": "GND"}),
        jtag_signal_named_rail_netlist(inventory=("1", "2", "3"), rail_pins={"1": "GND"}),
        jtag_signal_named_rail_netlist(omit_function_pins=frozenset({"2"}), rail_pins={"1": "GND"}),
        jtag_signal_named_rail_netlist(
            functions=("JTAG_TCK_TMS", "JTAG_TDI", "JTAG_TDO", "RESET"),
            rail_pins={"1": "GND"},
        ),
        jtag_signal_named_rail_netlist(functions=explicit_duplicate, rail_pins={"3": "GND"}),
        jtag_signal_named_rail_netlist(functions=generic_duplicate, rail_pins={"3": "GND"}),
        open_mode,
        jtag_signal_named_rail_netlist(
            functions=generic, rail_pins={"3": "GND"}, extra_assignments={"ALT": ("U1.3",)}
        ),
    )
    for index, source in enumerate(controls):
        assert not _findings(source), f"control {index} unexpectedly produced a JTAG review"


def test_policy_can_block_disable_or_exactly_ignore_named_rail_review() -> None:
    source = jtag_signal_named_rail_netlist(rail_pins={"1": "GND"})
    finding = _findings(source)[0]
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
                    reason="intentional JTAG test strap",
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


def test_mapping_order_is_stable_and_repair_clears_findings() -> None:
    fault = jtag_signal_named_rail_netlist(rail_pins={"1": "GND", "3": "+3V3"})
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})

    assert tuple(item.model_dump() for item in _findings(fault)) == tuple(
        item.model_dump() for item in _findings(reordered)
    )
    assert not _findings(jtag_signal_named_rail_netlist())
