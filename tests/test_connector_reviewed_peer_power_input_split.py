"""Review unclassified power-input splits across unlike reviewed connectors."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.reviewed_peer_power_input_split"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_split_generic_power_input_on_unlike_reviewed_peers_needs_review() -> None:
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)

    assert coverage.status == "COMPLETE"
    report = lint_report(observed, coverage)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "reviewed-synthetic-power-peers: POWER_INPUT (external-5v) "
        "generic power inputs use separate nets"
    )
    assert finding.evidence["assignments"] == ("J1.1=USB_5V", "J2.1=SERIAL_5V")
    assert finding.evidence["peer_assignment_group"] == ("reviewed-synthetic-power-peers",)
    assert finding.evidence["peer_assignment_basis"] == (
        "Synthetic USB and serial connector contacts were reviewed as peers",
    )
    assert "does not prove these nets should be joined" in finding.message
    assert {item.rule_id for item in report.findings} == {RULE_ID}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_domain_and_peer_identity_controls_stay_quiet_for_this_rule() -> None:
    common = power_input_netlist(power_assignments=("COMMON_5V", "COMMON_5V"))
    separated_groups = power_input_coverage(
        power_input_netlist(), peer_groups=("usb-peers", "serial-peers")
    )
    controls = (
        (common, power_input_coverage(common)),
        (
            power_input_netlist(),
            power_input_coverage(power_input_netlist(), voltage_domains=("usb-5v", "serial-5v")),
        ),
        (
            power_input_netlist(),
            power_input_coverage(
                power_input_netlist(), interface_signals=("USB_VBUS", "SERIAL_VCC")
            ),
        ),
        (power_input_netlist(), separated_groups),
        (
            power_input_netlist(
                values=("same connector", "same connector"),
                footprints=("Synthetic:Port", "Synthetic:Port"),
            ),
            power_input_coverage(
                power_input_netlist(
                    values=("same connector", "same connector"),
                    footprints=("Synthetic:Port", "Synthetic:Port"),
                )
            ),
        ),
        (
            power_input_netlist(symbols=("Synthetic:SamePort", "Synthetic:SamePort")),
            power_input_coverage(
                power_input_netlist(symbols=("Synthetic:SamePort", "Synthetic:SamePort"))
            ),
        ),
        (
            power_input_netlist(function="VBUS"),
            power_input_coverage(power_input_netlist(function="VBUS")),
        ),
        (
            power_input_netlist(electrical_type="passive"),
            power_input_coverage(power_input_netlist(electrical_type="passive")),
        ),
        (
            power_input_netlist(part_ids=("PART-A", "PART-B")),
            power_input_coverage(power_input_netlist(part_ids=("PART-A", "PART-B"))),
        ),
        (
            power_input_netlist(dnp=("J2",)),
            power_input_coverage(power_input_netlist(dnp=("J2",))),
        ),
        (
            power_input_netlist(power_assignments=("USB_5V", None)),
            power_input_coverage(power_input_netlist(power_assignments=("USB_5V", None))),
        ),
    )
    for observed, coverage in controls:
        report = lint_report(observed, coverage)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    ambiguous = power_input_netlist().model_copy(
        update={
            "nets": {
                **power_input_netlist().nets,
                "SYNTHETIC_AMBIGUOUS": ("J1.1",),
            }
        }
    )
    assert RULE_ID not in {
        item.rule_id for item in lint_report(ambiguous, power_input_coverage(ambiguous)).findings
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_and_role_classified_maps_do_not_trigger_rule() -> None:
    observed = power_input_netlist()
    current = power_input_coverage(observed)
    changed = power_input_netlist(power_assignments=("USB_5V_CHANGED", "SERIAL_5V"))
    incomplete = power_input_coverage(observed, complete_maps=False)
    unreviewed_inventory = power_input_coverage(observed, inventory_reviewed=False)
    stale = lint_report(changed, current)
    no_coverage = lint_report(observed)
    signal_role = lint_report(
        observed,
        power_input_coverage(observed, roles=("signal", "signal")),
    )
    supply_role = lint_report(
        observed,
        power_input_coverage(observed, roles=("supply", "supply")),
    )
    incomplete_report = lint_report(observed, incomplete)
    unreviewed_report = lint_report(observed, unreviewed_inventory)

    assert RULE_ID not in {item.rule_id for item in stale.findings}
    assert RULE_ID not in {item.rule_id for item in no_coverage.findings}
    assert RULE_ID not in {item.rule_id for item in signal_role.findings}
    assert RULE_ID not in {item.rule_id for item in supply_role.findings}
    assert RULE_ID not in {item.rule_id for item in incomplete_report.findings}
    assert RULE_ID not in {item.rule_id for item in unreviewed_report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reviewed_peer_power_input_split_obeys_policy_and_exact_ignore() -> None:
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)
    baseline = lint_report(observed, coverage)
    finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic quality policy requires review of mapped power inputs.",
                ),
            )
        ),
    )
    disabled = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic test covers a project-local opt-out.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review records intentionally independent sources.",
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reviewed_peer_power_input_split_is_stable_under_mapping_order() -> None:
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    first = next(
        item for item in lint_report(observed, coverage).findings if item.rule_id == RULE_ID
    )
    second_coverage = power_input_coverage(reordered)
    second = next(
        item for item in lint_report(reordered, second_coverage).findings if item.rule_id == RULE_ID
    )

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
