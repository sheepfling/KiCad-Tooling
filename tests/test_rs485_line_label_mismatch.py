"""Focused review regressions for RS-485 A/B function and net-label conflicts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding, DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_line_label_mismatch import rs485_line_label_mismatch_netlist

RULE_ID = "bus.rs485_line_label_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-rs485-line-label-mismatch",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_explicit_rs485_line_labels_request_review_with_pin_evidence() -> None:
    report = _report(rs485_line_label_mismatch_netlist())
    findings = _findings(report)

    assert tuple(item.subject for item in findings) == (
        "U1.1: RS-485 A function on RS485_B",
        "U1.2: RS-485 B function on RS485_A",
    )
    assert findings[0].evidence["pin_role"] == ("a",)
    assert findings[0].evidence["net_role"] == ("b",)
    assert findings[0].mode == "review"
    assert report.status == "REVIEW"
    assert "do not establish the required line assignment" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_generic_numbered_and_unsupported_rs485_labels_are_controls() -> None:
    source = rs485_line_label_mismatch_netlist()
    controls = (
        rs485_line_label_mismatch_netlist(crossed=False),
        source.model_copy(update={"nets": {"A": ("U1.1",), "B": ("U1.2",)}}),
        source.model_copy(update={"nets": {"RS485_A1": ("U1.1",), "RS485_B1": ("U1.2",)}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "component_symbols": {"J1": "Connector:Conn_01x02"},
                "component_pin_numbers": {"J1": ("1", "2")},
                "pin_functions": {"J1.1": "A", "J1.2": "B"},
                "nets": {"RS485_B": ("J1.1",), "RS485_A": ("J1.2",)},
            }
        ),
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
        source.model_copy(update={"nets": {"RS485_B": ("U1.1",), "RS485_A": ("U1.2", "U1.1")}}),
    )

    assert not candidates(rs485_line_label_mismatch_netlist(crossed=False))
    for control in controls:
        assert not _findings(_report(control))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_exact_line_conflicts() -> None:
    source = rs485_line_label_mismatch_netlist()
    initial = _findings(_report(source))[0]
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=initial.fingerprint,
                    reason="Reviewed transceiver pinout",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert (
        next(
            item for item in _findings(ignored) if item.fingerprint == initial.fingerprint
        ).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_corrected_labels_clear_the_findings() -> None:
    source = rs485_line_label_mismatch_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert tuple(item.model_dump() for item in _findings(_report(source))) == tuple(
        item.model_dump() for item in _findings(_report(reordered))
    )
    assert not _findings(_report(rs485_line_label_mismatch_netlist(crossed=False)))
