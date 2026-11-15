"""Focused regressions for recognized I2S signals assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i2s_endpoint_inventory import I2sEndpointInventory
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2s_signal_named_rail import i2s_signal_named_rail_netlist

RULE_ID = "bus.i2s_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-i2s-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _findings(source: NetlistContract) -> tuple:
    return tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)


@pytest.mark.parametrize(
    ("number", "rail", "function", "role"),
    (
        ("1", "GND", "I2S_BCLK", "bit_clock"),
        ("2", "+3V3", "I2S_LRCLK", "word_select"),
        ("3", "GND", "I2S_DATA", "serial_data"),
        ("4", "+3V3", "I2S_MCLK", "master_clock"),
    ),
)
def test_explicit_i2s_functions_on_named_rails_request_review(
    number: str, rail: str, function: str, role: str
) -> None:
    source = i2s_signal_named_rail_netlist(rail_pins={number: rail})
    finding = next(item for item in _findings(source) if item.subject.startswith(f"U1.{number}:"))

    assert (
        finding.subject
        == f"U1.{number}: {function} on {'return-like' if rail == 'GND' else 'supply-like'} net {rail}"
    )
    assert finding.evidence == {
        "pin": (f"U1.{number}",),
        "pin_function": (function,),
        "i2s_role": (role,),
        "i2s_identity_basis": ("explicit I2S pin-function metadata",),
        "assigned_net": (rail,),
        "net_label_role_clue": ("return-like" if rail == "GND" else "supply-like",),
        "component_pin_inventory": ("1", "2", "3", "4"),
    }
    assert finding.mode == "review"
    assert "do not prove I2S use, electrical potential" in finding.message


def test_complete_generic_connector_uses_clock_frame_context_for_data_and_master_clock() -> None:
    source = i2s_signal_named_rail_netlist(
        reference="J1",
        functions=("BCLK", "LRCLK", "SDOUT", "MCLK"),
        rail_pins={"3": "GND"},
    )

    assert tuple(item.subject for item in _findings(source)) == (
        "J1.3: SDOUT on return-like net GND",
    )
    role_pins = I2sEndpointInventory.from_netlist(source).named_rail_signal_pins("J1")
    assert tuple((item.pin, item.role) for item in role_pins) == (
        ("J1.1", "bit_clock"),
        ("J1.2", "word_select"),
        ("J1.3", "serial_data"),
        ("J1.4", "master_clock"),
    )
    assert all(
        item.identity_basis == "unique native bit-clock and word-select pair" for item in role_pins
    )


def test_generic_clock_aliases_need_a_complete_assigned_i2s_pair() -> None:
    isolated_bclk = i2s_signal_named_rail_netlist(
        functions=("BCLK", "MCLK", "DIN", "DOUT"),
        rail_pins={"1": "GND", "2": "+3V3"},
    )
    open_word_select = i2s_signal_named_rail_netlist(
        reference="J1",
        functions=("BCLK", "LRCLK", "SDOUT", "MCLK"),
        rail_pins={"1": "GND"},
    ).model_copy(update={"nets": {"GND": ("J1.1",), "SDOUT_BUS": ("J1.3",), "MCLK": ("J1.4",)}})
    generic_serial = i2s_signal_named_rail_netlist(
        functions=("SCK", "MOSI", "MISO", "CS"),
        rail_pins={"1": "GND", "2": "+3V3"},
    )

    assert not _findings(isolated_bclk)
    assert not _findings(open_word_select)
    assert not _findings(generic_serial)


def test_neutral_labels_and_irregular_source_evidence_are_controls() -> None:
    source = i2s_signal_named_rail_netlist()
    connector = i2s_signal_named_rail_netlist(reference="J1", rail_pins={"1": "GND"})
    controls = (
        i2s_signal_named_rail_netlist(rail_pins={"1": "I2S_BCLK", "3": "I2S_DATA"}),
        i2s_signal_named_rail_netlist(dnp=True, rail_pins={"1": "GND"}),
        i2s_signal_named_rail_netlist(inventory=("1", "2", "3"), rail_pins={"1": "GND"}),
        i2s_signal_named_rail_netlist(omit_function_pins=frozenset({"2"}), rail_pins={"1": "GND"}),
        source.model_copy(update={"nets": {**source.nets, "+3V3": ("U1.1",)}}),
        connector.model_copy(
            update={
                "nets": {
                    "GND": ("J1.1",),
                    "ALT": ("J1.1",),
                    **{k: v for k, v in connector.nets.items() if k != "GND"},
                }
            }
        ),
        source.model_copy(update={"pin_functions": {**source.pin_functions, "u1.1": "I2S_BCLK"}}),
        i2s_signal_named_rail_netlist(
            functions=("I2S_BCLK_LRCLK", "I2S_DATA", "I2S_MCLK", "I2S_DOUT"),
            rail_pins={"1": "GND"},
        ),
    )
    for index, control in enumerate(controls):
        assert not _findings(control), f"control {index} unexpectedly produced an I2S review"


def test_policy_can_block_disable_or_exactly_ignore_named_rail_review() -> None:
    source = i2s_signal_named_rail_netlist(rail_pins={"1": "GND"})
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
                    reason="intentional I2S return bond",
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


def test_reordered_mappings_are_stable_and_repair_clears_findings() -> None:
    fault = i2s_signal_named_rail_netlist(rail_pins={"1": "GND", "3": "+3V3"})
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    repaired = i2s_signal_named_rail_netlist()

    assert tuple(item.model_dump() for item in _findings(fault)) == tuple(
        item.model_dump() for item in _findings(reordered)
    )
    assert not _findings(repaired)
