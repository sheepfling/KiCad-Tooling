"""Focused USB data pin and net-label polarity lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach, complementary_usb_netlist

RULE_ID = "bus.usb_data_polarity_label_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _polarity_findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reversed_usb_net_labels_are_flagged_without_pair_completeness_duplicate() -> None:
    observed = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    report = evaluate("synthetic-usb-polarity", coach(observed), DesignLintPolicy())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert tuple(item.subject for item in findings) == (
        "J1.1: USB_D+ on USB_DM",
        "J1.2: D− on USB_DP",
    )
    assert findings[0].evidence["pin_side"] == ("positive",)
    assert findings[0].evidence["net_side"] == ("negative",)
    assert findings[1].evidence["pin_side"] == ("negative",)
    assert findings[1].evidence["net_side"] == ("positive",)
    assert not any(item.rule_id == "bus.complementary_pair_assignment" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_connector_to_device_pair_remains_visible() -> None:
    observed = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    crossed = observed.model_copy(
        update={
            "nets": {
                "USB_DM": ("J1.1", "U1.2"),
                "USB_DP": ("J1.2", "U1.1"),
            },
            "component_symbols": {
                "J1": "Synthetic:UsbPort",
                "U1": "Synthetic:UsbPhy",
            },
            "pin_functions": {
                "J1.1": "USB_D+",
                "J1.2": "D−",
                "U1.1": "USB_DP",
                "U1.2": "USB_DM",
            },
        }
    )

    assert tuple(item.subject for item in _polarity_findings(crossed)) == (
        "J1.1: USB_D+ on USB_DM",
        "J1.2: D− on USB_DP",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_valid_neutral_and_uncertain_assignments_are_not_classified() -> None:
    reversed_labels = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    ambiguous = reversed_labels.model_copy(
        update={
            "nets": {**reversed_labels.nets, "AUX": ("J1.1",)},
            "pin_functions": {**reversed_labels.pin_functions, "J1.2": "NC"},
        }
    )
    dnp = reversed_labels.model_copy(update={"dnp_components": ("J1",)})
    indexed = complementary_usb_netlist(positive_net="USB_DM2", negative_net="USB_DP2")
    shorted = complementary_usb_netlist(positive_net="USB_DP", negative_net="USB_DP")
    cases = (
        complementary_usb_netlist(),
        complementary_usb_netlist(positive_net="DATA_P", negative_net="DATA_N"),
        complementary_usb_netlist(positive_net=None, negative_net="USB_DM"),
        ambiguous,
        dnp,
        indexed,
        shorted,
    )

    assert all(not _polarity_findings(case) for case in cases)
    assert any(item.rule_id == "bus.complementary_pair_assignment" for item in candidates(shorted))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_are_supported() -> None:
    observed = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    review = evaluate("synthetic-usb-polarity", coach(observed), DesignLintPolicy())
    review_finding = next(item for item in review.findings if item.rule_id == RULE_ID)

    blocked = evaluate(
        "synthetic-usb-polarity",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    assert blocked.status == "FAIL"
    assert all(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)

    disabled = evaluate(
        "synthetic-usb-polarity",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional map"),)
        ),
    )
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )

    ignored = evaluate(
        "synthetic-usb-polarity",
        coach(observed),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=review_finding.fingerprint,
                    reason="Reviewed connector pin map",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == review_finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_netlist_is_stable_and_corrected_labels_clear_the_finding() -> None:
    observed = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    expected = tuple(
        item.fingerprint
        for item in evaluate("synthetic-usb-polarity", coach(observed), DesignLintPolicy()).findings
        if item.rule_id == RULE_ID
    )
    actual = tuple(
        item.fingerprint
        for item in evaluate(
            "synthetic-usb-polarity", coach(reordered), DesignLintPolicy()
        ).findings
        if item.rule_id == RULE_ID
    )
    corrected = complementary_usb_netlist()

    assert actual == expected
    assert not _polarity_findings(corrected)
