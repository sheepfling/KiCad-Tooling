"""Focused regressions for unassigned USB 2.0 data pins."""

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
from tests.design_lint_fixtures.usb_unconnected_data import usb_unconnected_data_netlist

RULE_ID = "bus.usb_unconnected_data_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: str | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = usb_unconnected_data_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-usb-unconnected-data",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_open_usb_data_pin_emits_exact_review_evidence_when_enabled() -> None:
    report = _report(mode="review")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == "J1.1: D+"
    assert finding.evidence == {
        "J1.1": (),
        "USB_data_side": ("D+",),
        "function": ("D+",),
        "paired_pin": ("J1.2",),
        "paired_function": ("D-",),
        "paired_net": ("USB_D-",),
    }
    assert "paired D− pin J1.2 is assigned to USB_D-" in finding.message
    assert "do not establish bus membership or PCB routing" in finding.message


def test_rule_is_opt_in_and_supports_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert default.mode == "off"
    assert default.disposition == "RULE_OFF"
    default_status = _report().status
    assert default_status == "REVIEW"  # Unrelated heuristics remain visible.
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == default_status
    assert (
        _report(
            mode="review",
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default.fingerprint,
                    reason="reviewed unused USB interface",
                ),
            ),
        ).status
        == default_status
    )


@pytest.mark.parametrize(
    ("function", "paired_function", "side", "port"),
    (
        ("DP2", "DM2", "D+", "2"),
        ("USB1D−", "USB1D+", "D−", "1"),
        ("USBDM", "USBDP", "D−", None),
    ),
)
def test_supported_function_aliases_keep_data_side_and_port_evidence(
    function: str, paired_function: str, side: str, port: str | None
) -> None:
    source = usb_unconnected_data_netlist(
        open_pins=("J1.1",),
        functions={"J1.1": function, "J1.2": paired_function},
    )
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    assert finding.evidence["USB_data_side"] == (side,)
    if port is None:
        assert "USB_data_port_index" not in finding.evidence
    else:
        assert finding.evidence["USB_data_port_index"] == (port,)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(usb_unconnected_data_netlist(open_pins=()), id="connected-control"),
        pytest.param(
            usb_unconnected_data_netlist(open_pins=("J1.1", "J1.2")),
            id="entire-pair-open",
        ),
        pytest.param(usb_unconnected_data_netlist(dnp_components=("J1",)), id="dnp-endpoint"),
        pytest.param(
            usb_unconnected_data_netlist(
                functions={"J1.1": "SSTX+", "J1.2": "SSTX-", "U1.1": "USB_DP", "U1.2": "USB_DM"}
            ),
            id="superspeed-is-out-of-scope",
        ),
        pytest.param(
            usb_unconnected_data_netlist(
                functions={"J1.1": "DATA_P", "J1.2": "DATA_N", "U1.1": "USB_DP", "U1.2": "USB_DM"}
            ),
            id="unknown-vendor-alias",
        ),
        pytest.param(
            usb_unconnected_data_netlist(
                functions={"J1.2": "CLK"},
            ),
            id="missing-recognized-pair-member",
        ),
        pytest.param(
            usb_unconnected_data_netlist().model_copy(update={"component_pin_numbers": {}}),
            id="incomplete-component-pin-inventory",
        ),
        pytest.param(
            usb_unconnected_data_netlist().model_copy(
                update={"component_pin_numbers": {"J1": ("1",), "U1": ("1", "2")}}
            ),
            id="pair-pin-missing-from-component-inventory",
        ),
        pytest.param(
            usb_unconnected_data_netlist(functions={"J1.3": "D+", "J1.4": "D-"}).model_copy(
                update={"component_pin_numbers": {"J1": ("1", "2", "3", "4"), "U1": ("1", "2")}}
            ),
            id="ambiguous-duplicate-pair-roles",
        ),
        pytest.param(
            usb_unconnected_data_netlist().model_copy(
                update={
                    "nets": {
                        **usb_unconnected_data_netlist().nets,
                        "USB_D-_ALIAS": ("J1.2",),
                    }
                }
            ),
            id="paired-pin-has-multiple-net-assignments",
        ),
    ),
)
def test_valid_or_unsupported_shapes_do_not_emit(source: NetlistContract) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_mapping_order_is_stable_and_assigning_open_pin_clears_finding() -> None:
    source = usb_unconnected_data_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "unconnected_nets": dict(reversed(tuple(source.unconnected_nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeat = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = source.model_copy(update={"nets": {**source.nets, "USB_D+_J1": ("J1.1",)}})

    assert (repeat.fingerprint, repeat.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)


@pytest.mark.parametrize("open_pin", ("J1.1", "J1.2", "U1.1", "U1.2"))
def test_either_open_side_is_reviewed_only_when_its_pair_member_is_assigned(
    open_pin: str,
) -> None:
    source = usb_unconnected_data_netlist(open_pins=(open_pin,))
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )

    assert finding.subject == f"{open_pin}: {source.pin_functions[open_pin]}"
    paired_pins = {"J1.1": "J1.2", "J1.2": "J1.1", "U1.1": "U1.2", "U1.2": "U1.1"}
    assert finding.evidence["paired_pin"] == (paired_pins[open_pin],)
