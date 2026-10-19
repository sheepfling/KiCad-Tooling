"""Exact mapped current-sink paths refine output-driven LED review."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
from kicad_tooling.hwrepo.power_path_models import (
    PowerPathEndpointRequirement,
    PowerPathMap,
)
from tests.design_lint_fixtures.current_sink_led import (
    current_sink_netlist,
    current_sink_path_map,
)

LED_RULE = "component.led_directly_driven_from_output"
PATH_RULE = "power.mapped_series_path_mismatch"

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.design_lint_rule(rule_id=LED_RULE),
    pytest.mark.design_lint_rule(rule_id=PATH_RULE),
]


def lint(netlist: NetlistContract, path_map: PowerPathMap | None = None):
    source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-led-current-sink",
        observed=netlist,
        netlist_sha256=source_hash,
    )
    return evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(power_path_map=path_map),
    )


def test_exact_current_sink_path_suppresses_only_the_mapped_led_prompt() -> None:
    source = current_sink_netlist()
    unmapped = lint(source)
    assert LED_RULE in {item.rule_id for item in unmapped.findings}

    reviewed = lint(source, current_sink_path_map())
    assert reviewed.status == "PASS", reviewed.issues
    assert LED_RULE not in {item.rule_id for item in reviewed.findings}
    assert PATH_RULE not in {item.rule_id for item in reviewed.findings}
    path_run = next(item for item in reviewed.mapped_check_runs if item.rule_id == PATH_RULE)
    assert (path_run.status, path_run.requirement_count, path_run.finding_count) == (
        "EVALUATED",
        1,
        0,
    )


def test_multichannel_map_only_suppresses_its_exact_led_paths() -> None:
    source = current_sink_netlist(two_channels=True)
    unmapped = lint(source)
    assert {item.subject for item in unmapped.findings if item.rule_id == LED_RULE} == {
        "D1: LED directly shares an output net and a rail",
        "D2: LED directly shares an output net and a rail",
    }

    partially_mapped = lint(source, current_sink_path_map())
    assert {item.subject for item in partially_mapped.findings if item.rule_id == LED_RULE} == {
        "D2: LED directly shares an output net and a rail"
    }
    assert PATH_RULE not in {item.rule_id for item in partially_mapped.findings}

    fully_mapped = lint(source, current_sink_path_map(two_channels=True))
    assert fully_mapped.status == "PASS", fully_mapped.issues
    assert LED_RULE not in {item.rule_id for item in fully_mapped.findings}
    assert PATH_RULE not in {item.rule_id for item in fully_mapped.findings}
    path_run = next(item for item in fully_mapped.mapped_check_runs if item.rule_id == PATH_RULE)
    assert (path_run.status, path_run.requirement_count, path_run.finding_count) == (
        "EVALUATED",
        2,
        0,
    )


@pytest.mark.parametrize(
    ("path_map", "netlist", "expected_issue"),
    (
        pytest.param(
            current_sink_path_map(part_id="different-part"),
            current_sink_netlist(),
            "PART_ID",
            id="wrong-driver-part-id",
        ),
        pytest.param(
            current_sink_path_map(pin_function="OUT1"),
            current_sink_netlist(),
            "native pin function",
            id="wrong-driver-pin-function",
        ),
        pytest.param(
            current_sink_path_map(pin_electrical_type="open_collector"),
            current_sink_netlist(),
            "native electrical type",
            id="wrong-driver-pin-type",
        ),
        pytest.param(
            current_sink_path_map(led_anode_pin="D1.2", led_cathode_pin="D1.1"),
            current_sink_netlist(),
            "LED directly shares an output net and a rail",
            id="reversed-led-polarity",
        ),
        pytest.param(
            current_sink_path_map(),
            current_sink_netlist(driver_type="input"),
            "native electrical type",
            id="source-pin-type-changed",
        ),
    ),
)
def test_stale_or_incomplete_sink_path_keeps_led_review_visible(
    path_map: PowerPathMap, netlist: NetlistContract, expected_issue: str
) -> None:
    report = lint(netlist, path_map)
    ids = {item.rule_id for item in report.findings}
    assert PATH_RULE in ids
    expected_led_prompt = expected_issue != "native electrical type" or (
        netlist.pin_electrical_types.get("U1.1", "").casefold() != "input"
    )
    assert (LED_RULE in ids) is expected_led_prompt
    path_finding = next(item for item in report.findings if item.rule_id == PATH_RULE)
    if expected_issue == "LED directly shares an output net and a rail":
        assert expected_issue in " ".join(item.subject for item in report.findings)
    else:
        assert any(expected_issue in issue for issue in path_finding.evidence["issues"])


def test_current_sink_role_requires_complete_source_bound_pin_identity() -> None:
    with pytest.raises(ValidationError, match="exact part ID, pin function"):
        PowerPathEndpointRequirement(
            reference="U1",
            pin="U1.1",
            symbol="Synthetic:CurrentSink",
            footprint="Synthetic:QFN",
            net="LED_SINK",
            role="current_controlled_sink",
        )


def test_current_sink_role_rejects_missing_native_electrical_type() -> None:
    with pytest.raises(ValidationError, match="must be supplied together"):
        PowerPathEndpointRequirement(
            reference="U1",
            pin="U1.1",
            symbol="Synthetic:CurrentSink",
            footprint="Synthetic:QFN",
            net="LED_SINK",
            role="current_controlled_sink",
            part_id="EXACT_PART",
            pin_function="LED_SINK",
        )
