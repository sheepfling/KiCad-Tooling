"""Regression tests for project-mapped signal divider requirements."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.signal_divider_models import (
    SignalDividerMap,
    SignalDividerRequirement,
)
from kicad_tooling.hwrepo.signal_dividers import scan_signal_divider_map
from kicad_tooling.hwrepo.voltage_divider_math import divider_tap_fraction
from tests.design_lint_fixtures.signal_divider import (
    signal_divider_map,
    signal_divider_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "interface.signal_divider_input_range_mismatch"
NETLIST_HASH = "a" * 64


def _report(
    *,
    fault: str | None = None,
    policy: DesignLintPolicy | None = None,
    observed: NetlistContract | None = None,
):
    netlist = observed if observed is not None else signal_divider_netlist(fault=fault)
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-input-divider",
        observed=netlist,
        netlist_sha256=NETLIST_HASH,
    )
    return evaluate(
        "synthetic-input-divider",
        coach,
        policy if policy is not None else DesignLintPolicy(signal_divider_map=signal_divider_map()),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_project_map_reports_valid_signal_divider_control() -> None:
    report = _report()

    assert report.status == "PASS"
    assert report.signal_divider_coverage.status == "COMPLETE"
    assert report.signal_divider_coverage.netlist_sha256 == NETLIST_HASH
    entry = report.signal_divider_coverage.entries[0]
    assert entry.status == "COMPLETE"
    assert entry.nominal_resistance_ohms == {"R1": 220_000.0, "R2": 33_000.0}
    assert entry.calculated_input_minimum_v == pytest.approx(24 * 33 / 253)
    assert entry.calculated_input_maximum_v == pytest.approx(24 * 33 / 253)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_wrong_nominal_divider_value_reports_source_bound_overrange() -> None:
    report = _report(fault="top-resistor-value")

    assert report.status == "REVIEW"
    entry = report.signal_divider_coverage.entries[0]
    assert entry.status == "OUT_OF_RANGE"
    assert entry.calculated_input_maximum_v == pytest.approx(24 * 33 / 213)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.evidence["source_voltage_range_v"] == ("24–24 V",)
    assert finding.evidence["target_input_range_v"] == ("3–3.3 V",)
    assert any("R1 is 180000 Ω" in issue for issue in finding.evidence["issues"])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "fault",
    (
        "split-tap",
        "dnp-lower-resistor",
        "wrong-symbol",
        "wrong-function",
        "wrong-electrical-type",
        "unmapped-load",
    ),
)
def test_incomplete_or_loaded_topology_is_coverage_gap(fault: str) -> None:
    report = _report(fault=fault)

    assert report.status == "REVIEW"
    assert report.signal_divider_coverage.status == "INCOMPLETE"
    entry = report.signal_divider_coverage.entries[0]
    assert entry.status == "INCOMPLETE"
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["calculated_nominal_input_range_v"] == ("unavailable",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_exact_finding() -> None:
    baseline = _report(fault="top-resistor-value")
    finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    blocked = _report(
        fault="top-resistor-value",
        policy=DesignLintPolicy(
            signal_divider_map=signal_divider_map(),
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed"),),
        ),
    )
    disabled = _report(
        fault="top-resistor-value",
        policy=DesignLintPolicy(
            signal_divider_map=signal_divider_map(),
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Not applicable"),),
        ),
    )
    ignored = _report(
        fault="top-resistor-value",
        policy=DesignLintPolicy(
            signal_divider_map=signal_divider_map(),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(finding),
                    reason="Reviewed against the receiver's approved absolute maximum",
                ),
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert disabled.status == "PASS"
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
    assert len(fingerprint(finding)) == 64


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_resistor_ordering_does_not_change_the_nominal_tap_fraction() -> None:
    assert divider_tap_fraction(220_000.0, 33_000.0) == pytest.approx(33 / 253)
    assert divider_tap_fraction(1_000.0, 1_000.0) == pytest.approx(0.5)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_fingerprint_is_stable_under_netlist_order_changes() -> None:
    original = signal_divider_netlist(fault="top-resistor-value")
    reordered_payload = original.model_dump(mode="python")
    reordered_payload["components"] = dict(reversed(tuple(original.components.items())))
    reordered_payload["component_symbols"] = dict(
        reversed(tuple(original.component_symbols.items()))
    )
    reordered_payload["pin_functions"] = dict(reversed(tuple(original.pin_functions.items())))
    reordered_payload["pin_electrical_types"] = dict(
        reversed(tuple(original.pin_electrical_types.items()))
    )
    reordered_payload["component_pin_numbers"] = dict(
        reversed(tuple(original.component_pin_numbers.items()))
    )
    reordered_payload["nets"] = {
        net: tuple(reversed(pins)) for net, pins in reversed(tuple(original.nets.items()))
    }
    reordered = NetlistContract.model_validate(reordered_payload)

    original_finding = next(
        item
        for item in _report(fault="top-resistor-value").findings
        if item.rule_id == RULE_ID
    )
    reordered_finding = next(
        item
        for item in _report(observed=reordered).findings
        if item.rule_id == RULE_ID
    )

    assert fingerprint(original_finding) == fingerprint(reordered_finding)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_map_rejects_reversed_voltage_window_and_duplicate_component_use() -> None:
    requirement = signal_divider_map().dividers[0].model_dump(mode="python")
    requirement["minimum_input_voltage_v"] = 3.4
    with pytest.raises(ValidationError, match="input voltage range is reversed"):
        SignalDividerRequirement.model_validate(requirement)

    duplicated = signal_divider_map().model_dump(mode="python")
    duplicated["dividers"] = (*duplicated["dividers"], duplicated["dividers"][0])
    with pytest.raises(ValidationError, match="IDs must be unique"):
        SignalDividerMap.model_validate(duplicated)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_no_authored_map_is_not_requested_or_inferred_from_two_resistors() -> None:
    netlist = signal_divider_netlist()
    coverage = scan_signal_divider_map(signal_divider_map(), netlist, NETLIST_HASH)
    report = _report(policy=DesignLintPolicy())

    assert coverage.status == "COMPLETE"
    assert report.signal_divider_coverage.status == "NOT_REQUESTED"
    assert not any(item.rule_id == RULE_ID for item in report.findings)
