"""Review named signal contacts left open across footprint-alias connectors."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, named_signal_all_open_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_named_signal_all_open"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_open_on_every_alias_is_reviewed_with_common_anchor() -> None:
    report = lint_report(named_signal_all_open_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 (UART_TX)"
    )
    assert finding.evidence["assignments"] == (
        "J1.2=<unassigned>",
        "J2.2=<unassigned>",
    )
    assert finding.evidence["pin_electrical_type"] == ("output",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "unused or isolated signal may be intentional" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.named_signal_all_open_peer_pin_group_count == 1
    assert alias.named_signal_all_open_finding_count == 1
    assert alias.unanchored_named_signal_all_open_peer_pin_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("electrical_type", "function"),
    (
        ("input", "UART_RX"),
        ("output", "UART_TX"),
        ("bidirectional", "DATA_IO"),
        ("tri_state", "DATA_TX"),
        ("open_collector", "IRQ_N"),
        ("open_emitter", "ALARM_N"),
    ),
)
def test_supported_named_signal_types_are_review_candidates(
    electrical_type: str, function: str
) -> None:
    report = lint_report(
        named_signal_all_open_netlist(function=function, electrical_type=electrical_type)
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["pin_electrical_type"] == (electrical_type,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_and_ineligible_contacts_do_not_become_findings() -> None:
    controls = (
        named_signal_all_open_netlist(target_assignments=("SIGNAL_A", "SIGNAL_B")),
        named_signal_all_open_netlist(anchor_assignments=("GND_A", "GND_B")),
        named_signal_all_open_netlist(function="Pin_2"),
        named_signal_all_open_netlist(function="VDD"),
        named_signal_all_open_netlist(function="GND"),
        named_signal_all_open_netlist(electrical_type="power_in"),
        named_signal_all_open_netlist(electrical_type="power_out"),
        named_signal_all_open_netlist(electrical_type="passive"),
        named_signal_all_open_netlist(electrical_type="free"),
        named_signal_all_open_netlist(electrical_type="unspecified"),
        named_signal_all_open_netlist(ambiguous_target=True),
        named_signal_all_open_netlist(incomplete_inventory=True),
        named_signal_all_open_netlist(missing_metadata_pin="J2.2"),
        named_signal_all_open_netlist(dnp=("J2",)),
        named_signal_all_open_netlist(part_id="SYNTHETIC-SIGNAL-ALL-OPEN-001"),
    )
    mismatched = named_signal_all_open_netlist()
    functions = dict(mismatched.pin_functions)
    functions["J2.2"] = "OTHER_OUTPUT"
    controls += (mismatched.model_copy(update={"pin_functions": functions}),)

    for source in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(source).findings}

    unanchored = lint_report(controls[1]).connector_peer_pin_coverage
    assert unanchored is not None
    alias = unanchored.footprint_alias_coverage
    assert alias.named_signal_all_open_peer_pin_group_count == 1
    assert alias.named_signal_all_open_finding_count == 0
    assert alias.unanchored_named_signal_all_open_peer_pin_group_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_all_open_is_stable_under_mapping_order() -> None:
    source = named_signal_all_open_netlist()
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_all_open_obeys_policy_and_exact_ignore() -> None:
    source = named_signal_all_open_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of open peer signals.",
                ),
            )
        ),
    )
    disabled = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic fixture tests a project override.",
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
                    reason="Synthetic policy records an intentionally unused signal.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "RULE_OFF" for item in disabled.findings
    )
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
