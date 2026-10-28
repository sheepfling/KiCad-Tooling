"""Regressions for USB-C SuperSpeed lane and net-label mismatches."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_superspeed_lanes import usb_c_superspeed_lane_netlist

RULE_ID = "bus.usb_c_superspeed_lane_label_mismatch"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

_CORRECT_LABELS = MappingProxyType(
    {
        "J1.1": "USB_TX1_P",
        "J1.2": "USB_TX1_N",
        "J1.3": "USB_TX2_P",
        "J1.4": "USB_TX2_N",
        "J1.5": "USB_RX1_P",
        "J1.6": "USB_RX1_N",
        "J1.7": "USB_RX2_P",
        "J1.8": "USB_RX2_N",
    }
)


def _netlist(labels: Mapping[str, str]) -> NetlistContract:
    grouped: dict[str, list[str]] = {}
    for pin, net in labels.items():
        grouped.setdefault(net, []).append(pin)
    return usb_c_superspeed_lane_netlist().model_copy(
        update={"nets": {net: tuple(pins) for net, pins in grouped.items()}}
    )


def _findings(source: NetlistContract) -> tuple[Candidate, ...]:
    return tuple(item for item in candidates(source) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_cross_lane_labels_are_localized_against_native_connector_functions() -> None:
    source = usb_c_superspeed_lane_netlist(swap_tx_lane_labels=True)
    findings = _findings(source)

    assert tuple(item.subject for item in findings) == (
        "J1.1: StdA_SSTX1+ on USB_TX2_P",
        "J1.2: StdA_SSTX1− on USB_TX2_N",
        "J1.3: StdA_SSTX2+ on USB_TX1_P",
        "J1.4: StdA_SSTX2− on USB_TX1_N",
    )
    assert findings[0].evidence == {
        "pin": ("J1.1",),
        "pin_function": ("StdA_SSTX1+",),
        "pin_lane": ("USB SuperSpeed TX lane 1",),
        "pin_side": ("positive",),
        "net": ("USB_TX2_P",),
        "net_lane": ("USB SuperSpeed TX lane 2",),
        "net_side": ("positive",),
    }
    assert not any(
        item.rule_id == "bus.complementary_pair_assignment" for item in candidates(source)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("pin", "label", "other_pin", "other_label"),
    (
        ("J1.1", "USB_TX1_N", "J1.2", "LANE_RETURN"),
        ("J1.1", "USB_RX1_P", "J1.5", "LANE_RX1_POS"),
    ),
)
def test_explicit_polarity_or_direction_mismatch_is_reviewed(
    pin: str,
    label: str,
    other_pin: str,
    other_label: str,
) -> None:
    labels = dict(_CORRECT_LABELS)
    labels[pin] = label
    labels[other_pin] = other_label

    findings = _findings(_netlist(labels))

    assert len(findings) == 1
    assert findings[0].evidence["pin"] == (pin,)
    assert findings[0].evidence["net"] == (label,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_correct_and_neutral_or_ambiguous_labels_remain_quiet() -> None:
    correct = _findings(_netlist(_CORRECT_LABELS))
    neutral = _findings(
        _netlist({pin: f"LANE_{index:02}" for index, pin in enumerate(_CORRECT_LABELS)})
    )
    unmarked = dict(_CORRECT_LABELS)
    unmarked["J1.1"] = "TX2_P"
    unrecognized = _netlist(unmarked).model_copy(update={"pin_functions": {"J1.1": "TX1+"}})

    assert not correct
    assert not neutral
    assert not _findings(unrecognized)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_and_superspeed_label_aliases_support_both_polarity_spellings() -> None:
    labels = dict(_CORRECT_LABELS)
    labels["J1.1"] = "USB3_SSTX1+"
    labels["J1.2"] = "SSTX1-"

    assert not _findings(_netlist(labels))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_and_multiply_assigned_connector_pins_are_skipped() -> None:
    labels = dict(_CORRECT_LABELS)
    labels["J1.1"] = "USB_TX2_P"
    source = _netlist(labels)
    dnp = source.model_copy(update={"dnp_components": ("J1",)})
    open_pin = _netlist({pin: net for pin, net in labels.items() if pin != "J1.1"})
    multiple = source.model_copy(update={"nets": {**source.nets, "USB_TX1_P_ALIAS": ("J1.1",)}})

    assert not _findings(dnp)
    assert not _findings(open_pin)
    assert not _findings(multiple)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_are_supported() -> None:
    labels = dict(_CORRECT_LABELS)
    labels["J1.1"] = "USB_TX2_P"
    source = _netlist(labels)
    review = evaluate("synthetic-usb-c-lane-labels", coach(source), DesignLintPolicy())
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)

    blocked = evaluate(
        "synthetic-usb-c-lane-labels",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed"),)
        ),
    )
    disabled = evaluate(
        "synthetic-usb-c-lane-labels",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional"),)
        ),
    )
    ignored = evaluate(
        "synthetic-usb-c-lane-labels",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Reviewed lane mapping",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)
    assert review.status == "REVIEW"
    assert finding.mode == "review"
    assert any(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        ).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_netlist_is_stable_and_corrected_labels_clear_findings() -> None:
    fault_labels = dict(_CORRECT_LABELS)
    fault_labels["J1.1"] = "USB_TX2_P"
    source = _netlist(fault_labels)
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    expected = tuple((fingerprint(item), item.evidence) for item in _findings(source))
    actual = tuple((fingerprint(item), item.evidence) for item in _findings(reordered))

    assert actual == expected
    assert not _findings(_netlist(_CORRECT_LABELS))
