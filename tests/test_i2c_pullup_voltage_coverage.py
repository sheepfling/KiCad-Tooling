"""Synthetic regressions for source-bound I2C input-voltage coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupAnalysis, I2cPullupLineRequirement
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.i2c_arrays import array_netlist, array_requirement
from tests.electrical_i2c_support import (
    i2c_pullup_voltage_requirement,
    i2c_series_pullup_netlist,
    i2c_series_pullup_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def coverage(netlist: NetlistContract, spec: I2cPullupAnalysis | None = None):
    return i2c_pullup_heuristic_coverage(
        netlist,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state="required",
        spec=spec,
    )


def _i2c_netlist_with_second_endpoint(*, dnp: bool = False) -> NetlistContract:
    netlist = i2c_series_pullup_netlist()
    return netlist.model_copy(
        update={
            "components": {
                **netlist.components,
                "U2": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            },
            "nets": {
                **netlist.nets,
                "I2C_SDA": (*netlist.nets["I2C_SDA"], "U2.1"),
                "I2C_SCL": (*netlist.nets["I2C_SCL"], "U2.2"),
            },
            "component_symbols": {
                **netlist.component_symbols,
                "U2": "Synthetic:I2cTarget",
            },
            "pin_functions": {
                **netlist.pin_functions,
                "U2.1": "SDA",
                "U2.2": "SCL",
            },
            "component_pin_numbers": {
                **netlist.component_pin_numbers,
                "U2": ("1", "2"),
            },
            "dnp_components": ("U2",) if dnp else (),
        }
    )


def _voltage_requirement_for_two_endpoints() -> I2cPullupAnalysis:
    requirement = i2c_pullup_voltage_requirement()
    bus = requirement.buses[0]

    def add_endpoint(line: I2cPullupLineRequirement) -> I2cPullupLineRequirement:
        voltage = line.voltage_compatibility
        assert voltage is not None
        additional = voltage.input_limits[0].model_copy(
            update={"pin": "U2.1" if line.net == "I2C_SDA" else "U2.2"}
        )
        return line.model_copy(
            update={
                "voltage_compatibility": voltage.model_copy(
                    update={"input_limits": (*voltage.input_limits, additional)}
                )
            }
        )

    return requirement.model_copy(
        update={
            "buses": (
                bus.model_copy(update={"sda": add_endpoint(bus.sda), "scl": add_endpoint(bus.scl)}),
            )
        }
    )


def _mapped_array_netlist(
    *, dnp: tuple[str, ...] = (), wrong_sda_net: bool = False
) -> NetlistContract:
    netlist = array_netlist(dnp=dnp, wrong_sda_net=wrong_sda_net)
    return netlist.model_copy(
        update={
            "components": {
                **netlist.components,
                "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            }
        }
    )


def _array_requirement_with_voltage_limits() -> I2cPullupAnalysis:
    requirement = array_requirement()
    voltage_requirement = i2c_pullup_voltage_requirement()
    bus = requirement.buses[0]
    voltage_bus = voltage_requirement.buses[0]
    sda = bus.sda.model_copy(
        update={"voltage_compatibility": voltage_bus.sda.voltage_compatibility}
    )
    scl = bus.scl.model_copy(
        update={"voltage_compatibility": voltage_bus.scl.voltage_compatibility}
    )
    return requirement.model_copy(
        update={"buses": (bus.model_copy(update={"sda": sda, "scl": scl}),)}
    )


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_visible_pullups_without_exact_input_limits_request_review() -> None:
    netlist = i2c_series_pullup_netlist()
    result = coverage(netlist, i2c_series_pullup_requirement())
    entries = result.voltage_entries

    assert [(entry.line, entry.endpoint_pins, entry.missing_input_pins) for entry in entries] == [
        ("SDA", ("U1.1",), ("U1.1",)),
        ("SCL", ("U1.2",), ("U1.2",)),
    ]
    findings = [
        item
        for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
        if item.rule_id == "bus.i2c_pullup_input_limit_coverage"
    ]
    assert len(findings) == 2
    assert findings[0].evidence["pullup_rails"] == ("+3V3",)
    assert "does not infer voltage compatibility" in findings[0].message


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_exact_input_limits_cover_all_recognized_endpoint_pins() -> None:
    netlist = _i2c_netlist_with_second_endpoint()
    result = coverage(netlist, _voltage_requirement_for_two_endpoints())

    assert result.voltage_entries
    assert all(entry.status == "COVERED" for entry in result.voltage_entries)
    assert all(not entry.missing_input_pins for entry in result.voltage_entries)
    assert "bus.i2c_pullup_input_limit_coverage" not in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_failing_authored_voltage_limit_keeps_the_review_candidate_open() -> None:
    netlist = i2c_series_pullup_netlist()
    result = coverage(
        netlist,
        i2c_pullup_voltage_requirement(maximum_rail_voltage_v=3.6, maximum_input_voltage_v=3.3),
    )

    sda = next(entry for entry in result.voltage_entries if entry.line == "SDA")
    assert sda.status == "OPEN"
    assert not sda.missing_input_pins
    assert any("voltage-compatibility check did not pass" in issue for issue in sda.issues)
    assert "bus.i2c_pullup_input_limit_coverage" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_partial_input_limit_map_names_the_uncovered_peer_and_dnp_is_excluded() -> None:
    netlist = _i2c_netlist_with_second_endpoint()
    result = coverage(netlist, i2c_pullup_voltage_requirement())

    assert [entry.missing_input_pins for entry in result.voltage_entries] == [
        ("U2.1",),
        ("U2.2",),
    ]
    dnp_result = coverage(
        _i2c_netlist_with_second_endpoint(dnp=True), i2c_pullup_voltage_requirement()
    )
    assert all(entry.status == "COVERED" for entry in dnp_result.voltage_entries)


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_no_visible_local_pullup_is_outside_this_coverage_prompt() -> None:
    netlist = NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8")
        },
        nets={"I2C_SDA": ("U1.1",), "I2C_SCL": ("U1.2",)},
        component_symbols={"U1": "Synthetic:I2cTarget"},
        pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        component_pin_numbers={"U1": ("1", "2")},
    )
    result = coverage(netlist, i2c_pullup_voltage_requirement())
    assert result.voltage_entries == ()
    assert "bus.i2c_pullup_input_limit_coverage" not in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_exact_mapped_array_channels_without_input_limits_request_review() -> None:
    netlist = _mapped_array_netlist()
    result = coverage(netlist, array_requirement())

    assert [
        (entry.line, entry.signal_net, entry.pullup_rails, entry.endpoint_pins)
        for entry in result.voltage_entries
    ] == [
        ("SDA", "I2C_SDA", ("+3V3",), ("U1.1",)),
        ("SCL", "I2C_SCL", ("+3V3",), ("U1.2",)),
    ]
    assert all(entry.status == "OPEN" for entry in result.voltage_entries)
    assert "bus.i2c_pullup_input_limit_coverage" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_exact_voltage_limits_cover_source_bound_array_channels() -> None:
    netlist = _mapped_array_netlist()
    result = coverage(netlist, _array_requirement_with_voltage_limits())

    assert [
        (entry.line, entry.status, entry.covered_input_pins) for entry in result.voltage_entries
    ] == [
        ("SDA", "COVERED", ("U1.1",)),
        ("SCL", "COVERED", ("U1.2",)),
    ]
    assert "bus.i2c_pullup_input_limit_coverage" not in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_dnp_unmapped_or_stale_arrays_are_not_guessed_as_pullups() -> None:
    dnp_result = coverage(_mapped_array_netlist(dnp=("RN1",)), array_requirement())
    unmapped_result = coverage(_mapped_array_netlist())
    netlist = _mapped_array_netlist()
    stale_netlist = netlist.model_copy(
        update={
            "components": {
                **netlist.components,
                "RN1": netlist.components["RN1"].model_copy(
                    update={"part_id": "STALE-SYNTHETIC-PART"}
                ),
            }
        }
    )
    stale_result = coverage(stale_netlist, array_requirement())

    assert dnp_result.voltage_entries == ()
    assert unmapped_result.voltage_entries == ()
    assert stale_result.voltage_entries == ()


def test_stale_voltage_only_coverage_blocks_evaluation() -> None:
    netlist = _mapped_array_netlist()
    requirement = _array_requirement_with_voltage_limits()
    current = coverage(netlist, requirement)
    assert current.entries
    assert current.voltage_entries
    assert all(entry.status == "COVERED" for entry in current.voltage_entries)

    stale = current.model_copy(update={"netlist_sha256": "c" * 64})
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i2c-voltage-coverage",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    report = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=stale,
    )

    assert report.status == "BLOCKED"
    assert report.i2c_pullup_heuristic_coverage.status == "BLOCKED"
    assert report.i2c_pullup_heuristic_coverage.entries == ()
    assert report.i2c_pullup_heuristic_coverage.voltage_entries == ()
    assert "different or unavailable native netlist hash" in report.issues[0]


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_array_channels_outside_visible_resistance_window_are_excluded() -> None:
    requirement = array_requirement()
    array = requirement.arrays[0]
    outside_window = array.model_copy(
        update={
            "channels": tuple(
                channel.model_copy(update={"resistance_ohms": value})
                for channel, value in zip(array.channels, (999.0, 100_001.0), strict=True)
            )
        }
    )
    out_of_range = requirement.model_copy(update={"arrays": (outside_window,)})

    assert coverage(_mapped_array_netlist(), out_of_range).voltage_entries == ()


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_miswired_array_channel_is_excluded_without_hiding_valid_peer_channel() -> None:
    netlist = _mapped_array_netlist(wrong_sda_net=True)
    result = coverage(netlist, array_requirement())

    assert [(entry.line, entry.endpoint_pins) for entry in result.voltage_entries] == [
        ("SCL", ("U1.2",))
    ]


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_ambiguous_multiport_endpoint_is_not_classified() -> None:
    netlist = i2c_series_pullup_netlist()
    multiport = netlist.model_copy(
        update={
            "nets": {
                **netlist.nets,
                "I2C_SDA_2": ("U1.3",),
                "I2C_SCL_2": ("U1.4",),
            },
            "pin_functions": {
                **netlist.pin_functions,
                "U1.3": "SDA",
                "U1.4": "SCL",
            },
            "component_pin_numbers": {"U1": ("1", "2", "3", "4"), **netlist.component_pin_numbers},
        }
    )
    result = coverage(multiport, i2c_pullup_voltage_requirement())
    assert result.voltage_entries == ()


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
def test_input_limit_coverage_policy_ignore_and_order_are_deterministic() -> None:
    netlist = i2c_series_pullup_netlist()
    reordered = netlist.model_copy(
        update={
            "components": dict(reversed(tuple(netlist.components.items()))),
            "nets": dict(reversed(tuple(netlist.nets.items()))),
            "pin_functions": dict(reversed(tuple(netlist.pin_functions.items()))),
        }
    )
    coverage_result = coverage(netlist, i2c_series_pullup_requirement())
    reordered_result = coverage(reordered, i2c_series_pullup_requirement())
    assert coverage_result.voltage_entries == reordered_result.voltage_entries

    array_netlist = _mapped_array_netlist()
    array_requirement_spec = array_requirement()
    reordered_array_netlist = array_netlist.model_copy(
        update={
            "components": dict(reversed(tuple(array_netlist.components.items()))),
            "nets": {
                net: tuple(reversed(pins))
                for net, pins in reversed(tuple(array_netlist.nets.items()))
            },
            "component_symbols": dict(reversed(tuple(array_netlist.component_symbols.items()))),
        }
    )
    reordered_array_requirement = array_requirement_spec.model_copy(
        update={
            "arrays": tuple(
                array.model_copy(update={"channels": tuple(reversed(array.channels))})
                for array in array_requirement_spec.arrays
            )
        }
    )
    assert (
        coverage(array_netlist, array_requirement_spec).voltage_entries
        == coverage(reordered_array_netlist, reordered_array_requirement).voltage_entries
    )

    coach_report = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i2c-voltage-coverage",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    review = evaluate(
        coach_report.project_id,
        coach_report,
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=coverage_result,
    )
    finding = next(
        item for item in review.findings if item.rule_id == "bus.i2c_pullup_input_limit_coverage"
    )
    assert finding.mode == "review"
    blocked = evaluate(
        coach_report.project_id,
        coach_report,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_pullup_input_limit_coverage",
                    mode="block",
                    reason="Every local I2C pull-up must have reviewed endpoint limits",
                ),
            )
        ),
        i2c_pullup_heuristic_coverage=coverage_result,
    )
    assert blocked.status == "FAIL"
    off = evaluate(
        coach_report.project_id,
        coach_report,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_pullup_input_limit_coverage",
                    mode="off",
                    reason="The project documents an approved external bus topology",
                ),
            )
        ),
        i2c_pullup_heuristic_coverage=coverage_result,
    )
    assert all(
        item.disposition == "RULE_OFF"
        for item in off.findings
        if item.rule_id == "bus.i2c_pullup_input_limit_coverage"
    )
    ignored = evaluate(
        coach_report.project_id,
        coach_report,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic exact test disposition",
                ),
            )
        ),
        i2c_pullup_heuristic_coverage=coverage_result,
    )
    ignored_findings = [
        item for item in ignored.findings if item.rule_id == "bus.i2c_pullup_input_limit_coverage"
    ]
    assert sum(item.disposition == "IGNORED" for item in ignored_findings) == 1
    assert sum(item.disposition == "OPEN" for item in ignored_findings) == 1
