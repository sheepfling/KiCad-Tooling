"""Focused regressions for return-like label groups without pin-role evidence."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.return_path_lint]

UNINDEXED_RETURN_RULE = "net.return_labels_without_pin_roles"
NUMBERED_RETURN_RULE = "net.numbered_returns"


def _finding(report: DesignLintReport, rule_id: str):
    return next(item for item in report.findings if item.rule_id == rule_id)


def _unindexed_returns() -> NetlistContract:
    return NetlistContract(
        components={},
        nets={"USB_GND": ("J1.7",), "SERIAL_RETURN": ("J2.7",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.7": "7"},
    )


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_disposition"),
    [
        pytest.param("review", "REVIEW", "OPEN", id="review"),
        pytest.param("block", "FAIL", "OPEN", id="block"),
        pytest.param("off", "PASS", "RULE_OFF", id="off"),
    ],
)
def test_unindexed_return_labels_follow_project_rule_mode(
    mode: str,
    expected_status: str,
    expected_disposition: str,
) -> None:
    report = evaluate(
        "synthetic-return-labels",
        coach(_unindexed_returns()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=UNINDEXED_RETURN_RULE,
                    mode=mode,
                    reason="Synthetic return-domain policy disposition",
                ),
            )
        ),
    )

    assert report.status == expected_status
    assert _finding(report, UNINDEXED_RETURN_RULE).disposition == expected_disposition


def test_unindexed_return_labels_include_exact_evidence_and_review_question() -> None:
    report = evaluate("synthetic-return-labels", coach(_unindexed_returns()), DesignLintPolicy())
    finding = _finding(report, UNINDEXED_RETURN_RULE)

    assert report.status == "REVIEW"
    assert finding.evidence == {"SERIAL_RETURN": ("J2.7",), "USB_GND": ("J1.7",)}
    assert "labels alone do not establish" in finding.message


def test_unindexed_return_ignore_is_exact_and_becomes_stale_after_source_change() -> None:
    source = _unindexed_returns()
    finding = _finding(
        evaluate("synthetic-return-labels", coach(source), DesignLintPolicy()),
        UNINDEXED_RETURN_RULE,
    )
    ignore_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=UNINDEXED_RETURN_RULE,
                fingerprint=finding.fingerprint,
                reason="Synthetic isolated returns have independent reviewed references",
            ),
        )
    )

    ignored = evaluate("synthetic-return-labels", coach(source), ignore_policy)
    assert ignored.status == "PASS"
    assert _finding(ignored, UNINDEXED_RETURN_RULE).disposition == "IGNORED"

    changed = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "SERIAL_RTN": source.nets["SERIAL_RETURN"],
                "SERIAL_RETURN": (),
            }
        }
    )
    changed_report = evaluate("synthetic-return-labels", coach(changed), ignore_policy)

    assert _finding(changed_report, UNINDEXED_RETURN_RULE).disposition == "OPEN"
    assert changed_report.stale_ignores == ignore_policy.ignores


def test_native_return_pin_roles_suppress_unroled_label_hint() -> None:
    observed = NetlistContract(
        components={},
        nets={"USB_RETURN": ("J1.7",), "SERIAL_GND": ("J2.7",)},
        component_symbols={"J1": "Synthetic:USB", "J2": "Synthetic:Serial"},
        pin_functions={"J1.7": "GND", "J2.7": "RTN"},
    )

    report = evaluate("synthetic-return-labels", coach(observed), DesignLintPolicy())

    assert UNINDEXED_RETURN_RULE not in {item.rule_id for item in report.findings}


def test_numbered_return_labels_use_numbered_rule_without_unroled_hint() -> None:
    observed = NetlistContract(
        components={},
        nets={"RETURN_PORT_1": ("J1.7",), "RETURN_PORT_2": ("J2.7",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.7": "7"},
    )

    report = evaluate("synthetic-numbered-returns", coach(observed), DesignLintPolicy())
    rules = {item.rule_id for item in report.findings}

    assert NUMBERED_RETURN_RULE in rules
    assert UNINDEXED_RETURN_RULE not in rules


def test_mixed_numbered_and_unindexed_return_groups_keep_both_hints() -> None:
    numbered = NetlistContract(
        components={},
        nets={"RETURN_PORT_1": ("J1.7",), "RETURN_PORT_2": ("J2.7",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.7": "7"},
    )
    mixed = numbered.model_copy(
        update={
            "nets": {
                **numbered.nets,
                "USB_GND": ("J3.7",),
                "SERIAL_RETURN": ("J4.7",),
            },
            "component_symbols": {
                **numbered.component_symbols,
                "J3": "Synthetic:USB",
                "J4": "Synthetic:Serial",
            },
            "pin_functions": {**numbered.pin_functions, "J3.7": "7", "J4.7": "7"},
        }
    )

    report = evaluate("synthetic-mixed-return-patterns", coach(mixed), DesignLintPolicy())
    rules = {item.rule_id for item in report.findings}

    assert NUMBERED_RETURN_RULE in rules
    assert UNINDEXED_RETURN_RULE in rules
    assert _finding(report, UNINDEXED_RETURN_RULE).evidence == {
        "SERIAL_RETURN": ("J4.7",),
        "USB_GND": ("J3.7",),
    }


def test_one_unindexed_return_label_is_not_a_group_hint() -> None:
    observed = NetlistContract(
        components={},
        nets={"USB_GND": ("J1.7",), "DATA": ("J2.1",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.1": "1"},
    )

    report = evaluate("synthetic-single-return", coach(observed), DesignLintPolicy())

    assert UNINDEXED_RETURN_RULE not in {item.rule_id for item in report.findings}


def test_unindexed_return_label_order_does_not_change_finding() -> None:
    source = _unindexed_returns()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    original = _finding(
        evaluate("synthetic-return-labels", coach(source), DesignLintPolicy()),
        UNINDEXED_RETURN_RULE,
    )
    reordered_finding = _finding(
        evaluate("synthetic-return-labels", coach(reordered), DesignLintPolicy()),
        UNINDEXED_RETURN_RULE,
    )

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original.fingerprint,
        original.evidence,
    )


def test_relabeling_one_return_clears_unindexed_group_hint() -> None:
    source = _unindexed_returns()
    one_label = source.model_copy(
        update={
            "nets": {
                "USB_GND": source.nets["USB_GND"],
                "SERIAL_SIGNAL": source.nets["SERIAL_RETURN"],
            }
        }
    )

    report = evaluate("synthetic-one-return-label", coach(one_label), DesignLintPolicy())

    assert UNINDEXED_RETURN_RULE not in {item.rule_id for item in report.findings}
