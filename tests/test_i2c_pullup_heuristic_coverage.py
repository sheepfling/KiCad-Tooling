"""Synthetic regressions for source-bound I2C pull-up hint resolution."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    NetlistContract,
)


def array_netlist(
    *,
    symbol: str = "Synthetic:ResistorArray",
    dnp: tuple[str, ...] = (),
    swapped_sda_channel: bool = False,
    wrong_sda_net: bool = False,
) -> NetlistContract:
    sda_assignments = ("RN1.2", "RN1.1") if swapped_sda_channel else ("RN1.1", "RN1.2")
    return NetlistContract(
        components={"RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4")},
        nets={
            "I2C_SDA": ("U1.1",) if wrong_sda_net else ("U1.1", sda_assignments[0]),
            "I2C_SCL": ("U1.2", "RN1.3", sda_assignments[0])
            if wrong_sda_net
            else ("U1.2", "RN1.3"),
            "+3V3": (sda_assignments[1], "RN1.4"),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            "RN1": symbol,
        },
        pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        component_pin_numbers={"U1": ("1", "2"), "RN1": ("1", "2", "3", "4")},
    )


def array_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic datasheet pin map and bus resistance requirement",
        buses=(
            I2cPullupBusRequirement(
                id="main",
                basis="Synthetic two-wire interface requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic array datasheet and pin map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 1 map",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 2 map",
                    ),
                ),
            ),
        ),
    )


def coverage(
    netlist: NetlistContract,
    spec: I2cPullupAnalysis | None = None,
    *,
    state: str = "required",
):
    return i2c_pullup_heuristic_coverage(
        netlist,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state=state,
        spec=spec,
    )


def test_valid_mapped_array_resolves_only_its_exact_missing_path_hint() -> None:
    netlist = array_netlist()
    baseline = candidates(netlist)
    assert "bus.i2c_missing_pullup" in {item.rule_id for item in baseline}

    result = coverage(netlist, array_requirement())
    assert result.status == "COMPLETE"
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.status == "COVERED"
    assert entry.missing_lines == ("SDA", "SCL")
    assert entry.bus_id == "main"
    assert entry.check_ids == ("i2c-pullup/main/sda", "i2c-pullup/main/scl")
    resolved = candidates(netlist, i2c_pullup_heuristic_coverage=result)
    assert "bus.i2c_missing_pullup" not in {item.rule_id for item in resolved}

    report = evaluate(
        "synthetic-i2c-array",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-i2c-array",
            observed=netlist,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=result,
    )
    assert report.i2c_pullup_heuristic_coverage == result
    assert "bus.i2c_missing_pullup" not in {item.rule_id for item in report.findings}
    rendered = text_report(report)
    assert "I2C pull-up heuristic coverage: COMPLETE (1/1 candidate pairs covered)" in rendered
    assert "projects/synthetic/electrical.json" in rendered
    assert "b" * 64 in rendered
    assert "Native netlist SHA-256: " + "a" * 64 in rendered


@pytest.mark.parametrize(
    ("spec", "state", "observed"),
    (
        pytest.param(None, "not_configured", array_netlist(), id="not-configured"),
        pytest.param(
            array_requirement(),
            "required",
            array_netlist(symbol="Synthetic:Unknown"),
            id="wrong-symbol",
        ),
        pytest.param(array_requirement(), "required", array_netlist(dnp=("RN1",)), id="not-fitted"),
        pytest.param(
            array_requirement(), "required", array_netlist(wrong_sda_net=True), id="wrong-net"
        ),
    ),
)
def test_missing_or_failing_exact_requirement_keeps_the_review_prompt_open(
    spec: I2cPullupAnalysis | None,
    state: str,
    observed: NetlistContract,
) -> None:
    result = coverage(observed, spec, state=state)
    assert result.entries[0].status == "OPEN"
    assert result.entries[0].issues
    found = candidates(observed, i2c_pullup_heuristic_coverage=result)
    assert "bus.i2c_missing_pullup" in {item.rule_id for item in found}


def test_symmetric_array_pin_orientation_is_a_valid_control() -> None:
    result = coverage(array_netlist(swapped_sda_channel=True), array_requirement())
    assert result.entries[0].status == "COVERED"


def test_stale_native_netlist_hash_blocks_coverage_instead_of_suppressing() -> None:
    netlist = array_netlist()
    stale = coverage(netlist, array_requirement()).model_copy(update={"netlist_sha256": "c" * 64})
    report = evaluate(
        "synthetic-i2c-array",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-i2c-array",
            observed=netlist,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=stale,
    )
    assert report.status == "BLOCKED"
    assert report.i2c_pullup_heuristic_coverage.status == "BLOCKED"
    assert report.i2c_pullup_heuristic_coverage.entries == ()
    assert "different or unavailable native netlist hash" in report.issues[0]


def test_requirement_for_a_different_ordered_bus_does_not_resolve_hint() -> None:
    requirement = array_requirement()
    wrong_bus = requirement.model_copy(
        update={
            "buses": (
                requirement.buses[0].model_copy(
                    update={"sda": requirement.buses[0].sda.model_copy(update={"net": "OTHER_SDA"})}
                ),
            )
        }
    )
    netlist = array_netlist()
    result = coverage(netlist, wrong_bus)
    assert result.entries[0].status == "OPEN"
    assert "exact ordered SDA/SCL" in result.entries[0].issues[0]
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


@pytest.mark.parametrize(
    ("state", "expected_status"),
    (("pending", "PENDING"), ("not_applicable", "NOT_APPLICABLE")),
)
def test_pending_and_not_applicable_contracts_do_not_assume_external_pullups(
    state: str,
    expected_status: str,
) -> None:
    netlist = array_netlist()
    result = coverage(netlist, state=state)
    assert result.status == expected_status
    assert result.entries[0].status == "OPEN"
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }
