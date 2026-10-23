"""Synthetic regressions for source-bound I2C pull-up hint resolution."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, text_report
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupResistorToleranceRequirement
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    I2cPullupAnalysis,
    NetlistContract,
)
from tests.design_lint_fixtures.i2c_arrays import (
    array_netlist,
    array_netlist_with_capacitor,
    array_requirement,
    array_requirement_with_capacitance_scope,
)
from tests.electrical_i2c_support import i2c_pullup_window_requirement

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


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


def _array_requirement_with_scoped_tolerances(
    *, wrong_scl_element: bool = False, maximum_bus_capacitance_pf: float = 50.0
) -> I2cPullupAnalysis:
    requirement = array_requirement()
    bus = requirement.buses[0]
    base_window = (
        i2c_pullup_window_requirement(maximum_bus_capacitance_pf=maximum_bus_capacitance_pf)
        .buses[0]
        .sda.electrical_window
    )
    assert base_window is not None

    def element(element_id: str) -> I2cPullupResistorToleranceRequirement:
        return I2cPullupResistorToleranceRequirement(
            element_id=element_id,
            maximum_tolerance_percent=5.0,
            basis=f"Synthetic array datasheet tolerance for {element_id}",
        )

    sda_window = base_window.model_copy(update={"resistor_tolerances": (element("RN1.sda"),)})
    scl_window = base_window.model_copy(
        update={"resistor_tolerances": (element("RN1.sda" if wrong_scl_element else "RN1.scl"),)}
    )
    updated_bus = bus.model_copy(
        update={
            "sda": bus.sda.model_copy(
                update={
                    "minimum_ohms": 4_000,
                    "maximum_ohms": 5_000,
                    "electrical_window": sda_window,
                }
            ),
            "scl": bus.scl.model_copy(
                update={
                    "minimum_ohms": 4_000,
                    "maximum_ohms": 5_000,
                    "electrical_window": scl_window,
                }
            ),
        }
    )
    return requirement.model_copy(update={"buses": (updated_bus,)})


def test_valid_mapped_array_resolves_only_its_exact_missing_path_hint() -> None:
    netlist = array_netlist()
    baseline = candidates(netlist)
    assert "bus.i2c_missing_pullup" in {item.rule_id for item in baseline}

    result = coverage(netlist, array_requirement())
    assert result.status == "COMPLETE", result.entries[0].issues
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


def test_exact_array_channel_tolerance_scope_resolves_the_i2c_prompt() -> None:
    netlist = array_netlist()
    result = coverage(netlist, _array_requirement_with_scoped_tolerances())

    assert result.status == "COMPLETE", result.entries[0].issues
    assert result.entries[0].status == "COVERED"
    assert "i2c-pullup/main/sda/electrical-window/tolerance-scope" in result.entries[0].check_ids
    assert "i2c-pullup/main/scl/electrical-window/tolerance-scope" in result.entries[0].check_ids
    assert "bus.i2c_missing_pullup" not in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_wrong_array_channel_tolerance_scope_keeps_the_i2c_prompt_open() -> None:
    netlist = array_netlist()
    result = coverage(
        netlist,
        _array_requirement_with_scoped_tolerances(wrong_scl_element=True),
    )

    assert result.status == "OPEN"
    assert any("RN1.scl" in issue for issue in result.entries[0].issues)
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_failing_electrical_window_keeps_the_i2c_prompt_open() -> None:
    netlist = array_netlist()
    result = coverage(
        netlist,
        _array_requirement_with_scoped_tolerances(maximum_bus_capacitance_pf=1_000),
    )

    assert result.status == "OPEN"
    assert any("maximum-rise-resistance" in issue for issue in result.entries[0].issues)
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_exact_array_capacitance_scope_resolves_the_i2c_prompt() -> None:
    netlist = array_netlist_with_capacitor()
    result = coverage(netlist, array_requirement_with_capacitance_scope())

    assert result.status == "COMPLETE", result.entries[0].issues
    assert "i2c-pullup/main/sda/electrical-window/capacitance-scope" in (
        result.entries[0].check_ids
    )
    assert "bus.i2c_missing_pullup" not in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_unmapped_array_capacitor_keeps_the_i2c_prompt_open() -> None:
    netlist = array_netlist_with_capacitor(extra_capacitor=True)
    result = coverage(netlist, array_requirement_with_capacitance_scope())

    assert result.status == "OPEN"
    assert any(
        "unmapped fitted capacitors on I2C_SDA: C2" in issue for issue in result.entries[0].issues
    )
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_overbudget_array_capacitance_keeps_the_i2c_prompt_open() -> None:
    netlist = array_netlist_with_capacitor()
    result = coverage(
        netlist,
        array_requirement_with_capacitance_scope(maximum_effective_capacitance_pf=30.0),
    )

    assert result.status == "OPEN"
    assert any("55.0pF" in issue for issue in result.entries[0].issues)
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


def test_changed_array_part_identity_keeps_missing_pullup_prompt_open() -> None:
    netlist = array_netlist(part_id="SYNTHETIC-ARRAY-10K")
    result = coverage(netlist, array_requirement())

    assert result.status == "OPEN"
    assert any(
        "PART_ID is SYNTHETIC-ARRAY-10K; expected SYNTHETIC-ARRAY-47K" in issue
        for issue in result.entries[0].issues
    )
    assert "bus.i2c_missing_pullup" in {
        item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=result)
    }


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
