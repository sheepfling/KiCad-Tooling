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
    BIDIRECTIONAL_RULE_ID,
    lint_report,
    peer_bidirectional_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_reports_an_open_native_bidirectional_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(
        peer_bidirectional_netlist(
            references=("U1", "U2", "U3"), pin_nets=("DATA_IO", "DATA_IO", None)
        )
    )
    findings = [item for item in report.findings if item.rule_id == BIDIRECTIONAL_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:BidirectionalModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("bidirectional",)
    assert finding.evidence["pin_function"] == ("DATA_IO",)
    assert finding.evidence["unassigned_pins"] == ("U3.2",)
    assert finding.evidence["U1.2"] == ("DATA_IO",)
    assert finding.evidence["U2.2"] == ("DATA_IO",)
    assert finding.evidence["U3.2"] == ()
    assert "do not require peer pins to share a net" in finding.message


@pytest.mark.parametrize(
    "pin_nets",
    (("DATA_IO", "DATA_IO"), ("DATA_IO_A", "DATA_IO_B")),
)
def test_assigned_bidirectional_peers_are_valid_same_or_separate_net_controls(
    pin_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_bidirectional_netlist(pin_nets=pin_nets))

    assert BIDIRECTIONAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_bidirectional_netlist(pin_nets=(None, None)),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), dnp=("U2",)),
        peer_bidirectional_netlist(
            pin_nets=("DATA_IO", None),
            symbols={"U1": "Synthetic:PeripheralA", "U2": "Synthetic:PeripheralB"},
        ),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), missing_inventory=("U2",)),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), ambiguous_pins=("U1",)),
        peer_bidirectional_netlist(electrical_types=("bidirectional", "input")),
        peer_bidirectional_netlist(electrical_types=("tri_state", "tri_state")),
        peer_bidirectional_netlist(pin_functions=(None, None)),
        peer_bidirectional_netlist(pin_functions=("DATA_IO", None)),
        peer_bidirectional_netlist(pin_functions=("DATA_IN", "DATA_OUT")),
        peer_bidirectional_netlist(references=("J1", "J2")),
    ),
)
def test_bidirectional_prompt_skips_open_or_incomplete_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert BIDIRECTIONAL_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


def test_bidirectional_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_bidirectional_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == BIDIRECTIONAL_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of open bidirectional peers",
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
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the peer bidirectional prompt",
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
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this peripheral pin as unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_bidirectional_finding_is_stable_under_map_order_changes() -> None:
    source = peer_bidirectional_netlist()
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
            if item.rule_id == BIDIRECTIONAL_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_bidirectional_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("bidirectional", tmp_path)
