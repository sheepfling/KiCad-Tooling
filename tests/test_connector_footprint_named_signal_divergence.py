"""Review explicitly named signal pins assigned to different nets on connector aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_named_signal_assignment_divergence"


def _signal_divergence_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("UART_TX_A", "UART_TX_B"),
    function: str = "UART_TX",
    electrical_type: str = "output",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
):
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("GND", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
    )


def test_named_signal_pin_on_different_nets_is_reviewed_with_a_common_anchor() -> None:
    report = lint_report(_signal_divergence_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (UART_TX)"
    )
    assert finding.evidence["assignments"] == ("J1.2=UART_TX_A", "J2.2=UART_TX_B")
    assert finding.evidence["pin_electrical_type"] == ("output",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not prove the assignments are wrong" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.named_signal_different_assignment_pin_group_count == 1
    assert alias.named_signal_divergence_finding_count == 1
    assert alias.unanchored_named_signal_divergence_pin_group_count == 0


@pytest.mark.parametrize(
    "electrical_type",
    ("input", "output", "bidirectional", "tri_state", "open_collector", "open_emitter"),
)
def test_explicit_native_signal_types_are_supported(electrical_type: str) -> None:
    report = lint_report(_signal_divergence_netlist(electrical_type=electrical_type))
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert len(findings) == 1
    assert findings[0].evidence["pin_electrical_type"] == (electrical_type,)


def test_common_unanchored_or_ineligible_contacts_are_not_signal_divergence_findings() -> None:
    controls = (
        _signal_divergence_netlist(target_assignments=("UART_TX", "UART_TX")),
        _signal_divergence_netlist(anchor_assignments=("GND_A", "GND_B")),
        _signal_divergence_netlist(function="Pin_2"),
        _signal_divergence_netlist(function="VDD"),
        _signal_divergence_netlist(function="GND"),
        _signal_divergence_netlist(electrical_type="passive"),
        _signal_divergence_netlist(electrical_type="power_in"),
        _signal_divergence_netlist(electrical_type="power_out"),
        _signal_divergence_netlist(electrical_type="free"),
        _signal_divergence_netlist(electrical_type="unspecified"),
        _signal_divergence_netlist(target_assignments=("UART_TX_A", None)),
        _signal_divergence_netlist(dnp=("J2",)),
        _signal_divergence_netlist(part_id="SYNTHETIC-PART-SIGNAL-001"),
    )
    for source in controls:
        report = lint_report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    alias = unanchored.footprint_alias_coverage
    assert alias.named_signal_different_assignment_pin_group_count == 1
    assert alias.named_signal_divergence_finding_count == 0
    assert alias.unanchored_named_signal_divergence_pin_group_count == 1


def test_named_signal_divergence_is_stable_under_mapping_order() -> None:
    source = _signal_divergence_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    second = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)


def test_named_signal_divergence_obeys_policy_and_exact_ignore() -> None:
    source = _signal_divergence_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires an explicit disposition for split output peers",
                ),
            )
        ),
    )
    ignored = lint_report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review records intentionally separate output nets",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings)
