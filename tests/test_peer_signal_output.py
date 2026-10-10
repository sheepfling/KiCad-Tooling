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
    RULE_ID,
    SIGNAL_RULE_ID,
    lint_report,
    peer_power_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_reports_an_open_native_signal_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist(output_electrical_types=("output", "output")))
    findings = [item for item in report.findings if item.rule_id == SIGNAL_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("output",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_signal_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(
        peer_power_output_netlist(
            output_nets=output_nets,
            output_electrical_types=("output", "output"),
        )
    )

    assert SIGNAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(
            output_nets=(None, None), output_electrical_types=("output", "output")
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            dnp=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            missing_inventory=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            ambiguous_outputs=("U1",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(output_nets=("VOUT", None)),
    ),
)
def test_signal_output_prompt_skips_incomplete_or_non_signal_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert SIGNAL_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


def test_signal_output_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_power_output_netlist(output_electrical_types=("output", "output"))
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == SIGNAL_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SIGNAL_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for peer outputs",
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
                    rule_id=SIGNAL_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the signal-output prompt",
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
                    rule_id=SIGNAL_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this output as intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_signal_output_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist(output_electrical_types=("output", "output"))
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
            if item.rule_id == SIGNAL_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_signal_output_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("signal", tmp_path)
