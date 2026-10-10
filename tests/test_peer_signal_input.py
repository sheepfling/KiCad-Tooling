"""Focused component peer-pin regression cases."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.component_peer_pin_native_support import _run_native_peer_pin_assignment_lane
from tests.component_peer_pin_support import (
    INPUT_RULE_ID,
    lint_report,
    peer_signal_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_reports_an_open_native_signal_input_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_signal_input_netlist())
    findings = [item for item in report.findings if item.rule_id == INPUT_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:SignalInputModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("input",)
    assert finding.evidence["pin_function"] == ("IN",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("SIGNAL_A",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert "control.unconnected_control_input" not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    "input_nets",
    (("SIGNAL", "SIGNAL"), ("SIGNAL_A", "SIGNAL_B")),
)
def test_assigned_signal_peer_inputs_are_valid_same_or_separate_net_controls(
    input_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_signal_input_netlist(input_nets=input_nets))

    assert INPUT_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_signal_input_netlist(input_nets=(None, None)),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), dnp=("U2",)),
        peer_signal_input_netlist(
            input_nets=("SIGNAL", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
        ),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), missing_inventory=("U2",)),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), ambiguous_inputs=("U1",)),
        peer_signal_input_netlist(input_electrical_types=("input", "output")),
        peer_signal_input_netlist(input_functions=("DATA_IN", "DATA_OUT")),
        peer_signal_input_netlist(input_functions=(None, None)),
        peer_signal_input_netlist(input_functions=("IN", None)),
        peer_signal_input_netlist(input_electrical_types=("passive", "passive")),
        peer_signal_input_netlist(references=("J1", "J2")),
    ),
)
def test_signal_input_prompt_skips_open_or_incomplete_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert INPUT_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


def test_active_low_input_is_eligible_for_peer_review() -> None:
    report = lint_report(
        peer_signal_input_netlist(input_electrical_types=("input_low", "input_low"))
    )

    finding = next(item for item in report.findings if item.rule_id == INPUT_RULE_ID)
    assert finding.evidence["pin_electrical_type"] == ("input_low",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)


@pytest.mark.parametrize(
    ("input_function", "specific_rule"),
    (
        ("VDD", "component.unconnected_supply_pin"),
        ("GND", "component.unconnected_return_pin"),
        ("RESET_B", "control.unconnected_control_input"),
    ),
)
def test_specific_supply_return_and_control_inputs_keep_their_own_findings(
    input_function: str, specific_rule: str
) -> None:
    report = lint_report(peer_signal_input_netlist(input_function=input_function))
    findings = {item.rule_id: item for item in report.findings}

    assert INPUT_RULE_ID not in findings
    assert specific_rule in findings


def test_signal_input_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_signal_input_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == INPUT_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=INPUT_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for peer inputs",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=INPUT_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the signal-input prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=INPUT_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this input as intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_signal_input_finding_is_stable_under_map_order_changes() -> None:
    source = peer_signal_input_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)

    def get_findings(report: DesignLintReport) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == INPUT_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_signal_input_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("signal-input", tmp_path)
