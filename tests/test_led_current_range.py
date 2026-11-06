"""Project-mapped LED current-window regressions and policy lifecycle."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_led_current_candidate_evidence import (
    LedCurrentRangeCandidate,
)
from kicad_tooling.hwrepo.design_lint_led_current_candidates import led_current_range_candidates
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.led_current_models import LedCurrentMap
from kicad_tooling.hwrepo.led_current_range import led_current_map_sha256
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.led_current import led_current_map, led_current_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID: DesignLintRuleId = "component.mapped_led_current_range_mismatch"


def _report(
    netlist: NetlistContract,
    requirement_map: LedCurrentMap | None,
    *,
    netlist_sha256: str | None = None,
    include_netlist_digest: bool = True,
    rules: tuple[DesignLintRuleOverride, ...] = (),
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    digest = (
        netlist_sha256
        if netlist_sha256 is not None
        else hashlib.sha256(netlist.model_dump_json().encode()).hexdigest()
    )
    if not include_netlist_digest:
        digest = None
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-led-current-window",
        observed=netlist,
        netlist_sha256=digest,
    )
    return evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(led_current_map=requirement_map, rules=rules, ignores=ignores),
    )


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_authored_led_and_resistor_current_envelope_is_a_valid_control() -> None:
    report = _report(led_current_netlist(), led_current_map())

    assert report.status == "PASS"
    run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "EVALUATED"
    assert run.requirement_count == 1
    assert run.finding_count == 0
    assert run.netlist_sha256 == report.netlist_sha256
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_wrong_resistor_value_exceeds_authored_current_window() -> None:
    report = _report(
        led_current_netlist(resistor_value="100R"),
        led_current_map(),
    )

    finding = _finding(report)
    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.evidence["resistor_nominal_ohms"] == ("100",)
    assert finding.evidence["calculated_current_ma"] == ("10.4762–15.7895",)
    assert finding.evidence["target_current_basis"] == (
        "Synthetic project-selected indicator-current range",
    )
    assert finding.evidence["netlist_sha256"] == (report.netlist_sha256,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_retains_copied_map_and_netlist_sources() -> None:
    netlist = led_current_netlist(resistor_value="100R")
    requirement_map = led_current_map()
    digest = hashlib.sha256(netlist.model_dump_json().encode()).hexdigest()
    (candidate,) = led_current_range_candidates(netlist, requirement_map, digest)

    assert isinstance(candidate, LedCurrentRangeCandidate)
    assert candidate.source_evidence.led_map == requirement_map
    assert candidate.source_evidence.observed == netlist
    assert candidate.source_evidence.led_map is not requirement_map
    assert candidate.source_evidence.observed is not netlist
    assert candidate.source_evidence.observed.nets is not netlist.nets
    assert candidate.source_evidence.netlist_sha256 == digest
    assert candidate.source_evidence.entry.status == "OUT_OF_RANGE"

    altered_entry = candidate.source_evidence.entry.model_copy(update={"source_net": "+5V"})
    with pytest.raises(ValueError, match="result must match its retained map and netlist"):
        replace(candidate.source_evidence, entry=altered_entry)
    with pytest.raises(ValueError, match="must match its retained source projection"):
        replace(candidate, evidence={"forged": ("value",)})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_tolerance_corners_catch_a_window_failure_hidden_by_nominal_current() -> None:
    report = _report(
        led_current_netlist(),
        led_current_map(minimum_current_ma=2.3, maximum_current_ma=3.25),
    )

    finding = _finding(report)
    assert finding.evidence["resistor_nominal_ohms"] == ("470",)
    assert finding.evidence["calculated_current_ma"] == ("2.22898–3.35946",)
    assert any("outside the authored target" in issue for issue in finding.evidence["issues"])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_side_series_resistor_matches_the_same_authored_current_window() -> None:
    report = _report(
        led_current_netlist(resistor_leg="cathode"),
        led_current_map(resistor_leg="cathode"),
    )

    assert report.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("netlist", "expected_issue"),
    (
        (led_current_netlist(dnp=("R1",)), "is not fitted"),
        (led_current_netlist(extra_resistor=True), "Unmapped fitted resistors"),
        (
            led_current_netlist().model_copy(
                update={
                    "nets": {
                        "+3V3": ("R1.1",),
                        "LED_A": ("R1.2",),
                        "LED_WRONG": ("D1.1",),
                        "GND": ("D1.2",),
                    }
                }
            ),
            "LED anode",
        ),
        (
            led_current_netlist().model_copy(update={"component_pin_numbers": {"D1": ("1", "2")}}),
            "no complete native pin-number inventory",
        ),
    ),
)
def test_incomplete_population_or_topology_requests_review(
    netlist: NetlistContract, expected_issue: str
) -> None:
    report = _report(netlist, led_current_map())

    finding = _finding(report)
    assert report.status == "REVIEW"
    assert any(expected_issue in issue for issue in finding.evidence["issues"])


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_source_digest_is_incomplete_and_unmapped_leds_are_not_inferred() -> None:
    netlist = led_current_netlist()

    missing_source = _report(netlist, led_current_map(), include_netlist_digest=False)
    no_map = _report(netlist, None)

    assert missing_source.status == "BLOCKED"
    assert _finding(missing_source).evidence["netlist_sha256"] == ("unavailable",)
    run = next(item for item in missing_source.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "BLOCKED"
    assert any(
        "Source-bound native netlist SHA-256 is unavailable" in issue
        for issue in _finding(missing_source).evidence["issues"]
    )
    assert no_map.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in no_map.findings)
    assert next(item for item in no_map.mapped_check_runs if item.rule_id == RULE_ID).status == (
        "NOT_CONFIGURED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_are_project_configurable() -> None:
    netlist = led_current_netlist(resistor_value="100R")
    requirement_map = led_current_map()
    default = _report(netlist, requirement_map)
    finding = _finding(default)
    blocked = _report(
        netlist,
        requirement_map,
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Synthetic release policy requires the mapped LED window",
            ),
        ),
    )
    disabled = _report(
        netlist,
        requirement_map,
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic board does not require this indicator",
            ),
        ),
    )
    ignored = _report(
        netlist,
        requirement_map,
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic fixture records an approved alternate current window",
            ),
        ),
    )

    assert default.status == "REVIEW"
    assert blocked.status == "FAIL"
    assert _finding(blocked).mode == "block"
    assert disabled.status == "PASS"
    assert ignored.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_requirement_rejects_reversed_ranges_and_reused_components() -> None:
    payload = led_current_map().model_dump(mode="python")
    payload["leds"][0]["minimum_source_voltage_v"] = 4.0
    with pytest.raises(ValidationError, match="source-voltage range is reversed"):
        LedCurrentMap.model_validate(payload)

    payload = led_current_map().model_dump(mode="python")
    payload["leds"] = (payload["leds"][0], payload["leds"][0])
    with pytest.raises(ValidationError, match="IDs must be unique"):
        LedCurrentMap.model_validate(payload)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_requirement_hash_is_stable_when_led_entry_order_changes() -> None:
    first = led_current_map().leds[0]
    second = first.model_copy(
        update={
            "id": "auxiliary-indicator",
            "led_reference": "D2",
            "anode_pin": "D2.1",
            "cathode_pin": "D2.2",
            "led_side_net": "LED2_A",
            "resistor": first.resistor.model_copy(
                update={
                    "reference": "R2",
                    "outer_pin": "R2.1",
                    "led_side_pin": "R2.2",
                }
            ),
        }
    )
    ordered = LedCurrentMap(basis="Two synthetic indicator requirements", leds=(first, second))
    reversed_order = ordered.model_copy(update={"leds": tuple(reversed(ordered.leds))})

    assert led_current_map_sha256(ordered) == led_current_map_sha256(reversed_order)
