"""Exact mapped current-sink paths refine output-driven LED review."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.power_path_models import (
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
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


def current_sink_netlist(*, driver_type: str = "output") -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic current sink",
                footprint="Synthetic:QFN",
                part_id="synthetic-cc-sink",
            ),
            "D1": ComponentContract(value="Synthetic LED", footprint="Synthetic:LED"),
            "U2": ComponentContract(value="Synthetic rail source", footprint="Synthetic:Source"),
        },
        nets={
            "+5V": ("U2.1", "D1.1"),
            "LED_SINK": ("D1.2", "U1.1"),
        },
        component_symbols={
            "U1": "Synthetic:CurrentSink",
            "D1": "Device:LED",
            "U2": "Synthetic:RailSource",
        },
        pin_functions={"U1.1": "OUT0", "D1.1": "A", "D1.2": "K", "U2.1": "VOUT"},
        pin_electrical_types={
            "U1.1": driver_type,
            "D1.1": "passive",
            "D1.2": "passive",
            "U2.1": "power_out",
        },
        component_pin_numbers={"U1": ("1",), "D1": ("1", "2"), "U2": ("1",)},
    )


def current_sink_path_map(
    *,
    part_id: str = "synthetic-cc-sink",
    pin_function: str = "OUT0",
    pin_electrical_type: str = "output",
    led_anode_pin: str = "D1.1",
    led_cathode_pin: str = "D1.2",
) -> PowerPathMap:
    return PowerPathMap(
        basis="Synthetic project-approved current-controlled LED output path",
        paths=(
            PowerPathRequirement(
                id="led-channel-0",
                basis="Synthetic reviewed source identifies U1.1 as a current sink output",
                start=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:RailSource",
                    footprint="Synthetic:Source",
                    net="+5V",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:CurrentSink",
                    footprint="Synthetic:QFN",
                    net="LED_SINK",
                    role="current_controlled_sink",
                    part_id=part_id,
                    pin_function=pin_function,
                    pin_electrical_type=pin_electrical_type,
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="D1",
                        symbol="Device:LED",
                        footprint="Synthetic:LED",
                        side_a_pin=led_anode_pin,
                        side_b_pin=led_cathode_pin,
                        side_a_net="+5V",
                        side_b_net="LED_SINK",
                    ),
                ),
            ),
        ),
    )


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
