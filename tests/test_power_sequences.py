"""Synthetic regressions for project-mapped power-sequence dependencies."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import ComponentContract, DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.power_sequence_models import PowerSequenceMap
from kicad_tooling.hwrepo.power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
)
from tests.power_sequence_support import (
    RULE_ID,
    lint_report,
    power_sequence_map,
    power_sequence_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def test_explicit_power_good_to_enable_map_passes_including_firmware_control() -> None:
    sequence_map = power_sequence_map(firmware_enable=True)
    report = lint_report(power_sequence_netlist(), sequence_map)
    assert report.status == "PASS", report.issues
    assert RULE_ID not in {item.rule_id for item in report.findings}
    run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "EVALUATED"
    assert run.requirement_count == len(sequence_map.stages) + len(sequence_map.dependencies)
    assert run.finding_count == 0
    assert run.netlist_sha256 == report.netlist_sha256
    assert power_sequence_mismatches(sequence_map, power_sequence_netlist()) == ()
    assert not power_sequence_graph_has_cycle(sequence_map)


@pytest.mark.parametrize(
    ("fault", "expected_issue", "expected_stage"),
    (
        pytest.param("open-enable", "U2.1 is assigned to FLOATING", "rail-b", id="open-enable"),
        pytest.param("wrong-output", "U1.2 is assigned to OTHER_RAIL", "rail-a", id="wrong-output"),
        pytest.param("wrong-symbol", "U1 symbol is Synthetic:Switch", "rail-a", id="wrong-symbol"),
        pytest.param("wrong-part-id", "U1 PART_ID is WRONG-PART", "rail-a", id="wrong-part-id"),
        pytest.param(
            "missing-pin",
            "U2.1 is absent from the native pin inventory",
            "rail-b",
            id="missing-pin",
        ),
        pytest.param("dnp", "U2 is marked DNP", "rail-b", id="dnp"),
    ),
)
def test_missing_net_identity_inventory_part_and_dnp_faults_are_reported(
    fault: str, expected_issue: str, expected_stage: str
) -> None:
    report = lint_report(power_sequence_netlist(fault=fault), power_sequence_map())
    assert report.status == "REVIEW"
    run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "EVALUATED"
    assert run.finding_count == 1
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert any(expected_issue in issue for issue in finding.evidence["issues"]), finding.evidence[
        "issues"
    ]
    assert finding.evidence["sequence_map_basis"] == (
        "Synthetic source page 4, startup dependency table",
    )
    if expected_stage == "rail-b":
        assert "enable: U2.1 on GOOD_A" in finding.evidence["expected_endpoints"]
    assert finding.evidence["dependencies"] == ("rail-a-before-rail-b: rail-a → rail-b on GOOD_A",)
    assert finding.evidence["map_sha256"]


def test_unconfigured_map_does_not_infer_requirements_from_pin_names() -> None:
    named_pins = power_sequence_netlist().model_copy(
        update={
            "pin_functions": {"U1.3": "PG", "U2.1": "EN"},
            "pin_electrical_types": {"U1.3": "output", "U2.1": "input"},
        }
    )
    report = lint_report(named_pins)
    assert RULE_ID not in {item.rule_id for item in report.findings}
    run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "NOT_CONFIGURED"
    assert run.finding_count == 0


def test_rule_supports_review_block_off_and_exact_ignore() -> None:
    faulty = power_sequence_netlist(fault="open-enable")
    sequence_map = power_sequence_map()
    blocked = lint_report(
        faulty,
        sequence_map,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic release policy requires the mapped sequence topology",
        ),
    )
    assert blocked.status == "FAIL"
    finding = next(
        item for item in lint_report(faulty, sequence_map).findings if item.rule_id == RULE_ID
    )
    ignored = lint_report(
        faulty,
        sequence_map,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic approved alternate sequence is covered elsewhere",
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
    disabled = lint_report(
        faulty,
        sequence_map,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic alternate variant has a separate sequence contract",
        ),
    )
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    disabled_run = next(item for item in disabled.mapped_check_runs if item.rule_id == RULE_ID)
    assert (disabled_run.status, disabled_run.mode) == ("EVALUATED", "off")
    assert disabled_run.finding_count == 1


def test_netlist_order_is_stable_and_repair_clears_finding() -> None:
    sequence_map = power_sequence_map()
    faulty = power_sequence_netlist(fault="open-enable")
    report = lint_report(faulty, sequence_map)
    original = next(item for item in report.findings if item.rule_id == RULE_ID)
    reordered = faulty.model_copy(
        update={
            "nets": dict(reversed(tuple(faulty.nets.items()))),
            "components": dict(reversed(tuple(faulty.components.items()))),
            "component_symbols": dict(reversed(tuple(faulty.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(faulty.component_pin_numbers.items()))),
        }
    )
    reordered_finding = next(
        item for item in lint_report(reordered, sequence_map).findings if item.rule_id == RULE_ID
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original.fingerprint,
        original.evidence,
    )

    unrelated = faulty.model_copy(
        update={
            "components": {
                **faulty.components,
                "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
            },
            "nets": {
                **faulty.nets,
                "UNRELATED_A": ("R9.1",),
                "UNRELATED_B": ("R9.2",),
            },
            "component_symbols": {**faulty.component_symbols, "R9": "Device:R"},
            "component_pin_numbers": {
                **faulty.component_pin_numbers,
                "R9": ("1", "2"),
            },
        }
    )
    unrelated_report = lint_report(unrelated, sequence_map)
    unrelated_finding = next(item for item in unrelated_report.findings if item.rule_id == RULE_ID)
    assert unrelated_report.netlist_sha256 != report.netlist_sha256
    assert (unrelated_finding.fingerprint, unrelated_finding.evidence) == (
        original.fingerprint,
        original.evidence,
    )
    original_run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    unrelated_run = next(
        item for item in unrelated_report.mapped_check_runs if item.rule_id == RULE_ID
    )
    assert unrelated_run.netlist_sha256 == unrelated_report.netlist_sha256
    assert unrelated_run.netlist_sha256 != original_run.netlist_sha256
    assert unrelated_run.map_sha256 == original_run.map_sha256

    exact_ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=original.fingerprint,
        reason="Synthetic review accepts this explicit rail-sequence exception",
    )
    for candidate in (faulty, unrelated):
        ignored_report = lint_report(candidate, sequence_map, ignore=exact_ignore)
        ignored_finding = next(item for item in ignored_report.findings if item.rule_id == RULE_ID)
        assert ignored_finding.fingerprint == original.fingerprint
        assert ignored_finding.disposition == "IGNORED"

    assert RULE_ID not in {
        item.rule_id for item in lint_report(power_sequence_netlist(), sequence_map).findings
    }


def test_map_rejects_unresolved_stage_names() -> None:
    raw = power_sequence_map().model_dump(mode="python")
    raw["dependencies"][0]["successor_stage"] = "unknown-stage"
    with pytest.raises(ValidationError, match="name declared stages"):
        PowerSequenceMap.model_validate(raw)


def test_map_requires_dependency_net_to_match_power_good_endpoint() -> None:
    raw = power_sequence_map().model_dump(mode="python")
    raw["dependencies"][0]["signal_net"] = "WRONG_NET"
    with pytest.raises(ValidationError, match="match its power-good endpoint"):
        PowerSequenceMap.model_validate(raw)


def test_map_requires_an_enable_endpoint_for_enabled_stage() -> None:
    raw = power_sequence_map().model_dump(mode="python")
    raw["stages"][1]["enable_control"] = "external"
    raw["stages"][1]["enable"] = None
    with pytest.raises(ValidationError, match="requires a mapped enable endpoint"):
        PowerSequenceMap.model_validate(raw)
