"""Synthetic tests for exact, project-authored oscillator output paths."""

from __future__ import annotations

import hashlib
from typing import Literal, TypedDict

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.oscillator_output_path_models import (
    OscillatorOutputLoadRequirement,
    OscillatorOutputPathMap,
    OscillatorOutputPathRequirement,
    OscillatorOutputSeriesResistorRequirement,
)
from kicad_tooling.hwrepo.oscillator_output_paths import oscillator_output_path_mismatches

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "oscillator.output_load_path_mismatch"


class OscillatorOutputPathUpdates(TypedDict, total=False):
    """Fields varied by malformed oscillator-path input cases."""

    topology: Literal["direct", "series"]
    series_resistor: dict[str, str] | None


def oscillator_output_path_map(
    *, topology: str = "series", minimum_ohms: float = 22.0, maximum_ohms: float = 47.0
) -> OscillatorOutputPathMap:
    resistor = (
        None
        if topology == "direct"
        else OscillatorOutputSeriesResistorRequirement(
            reference="R1",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:R_0603",
            output_side_pin="R1.1",
            load_side_pin="R1.2",
            minimum_nominal_resistance_ohms=minimum_ohms,
            maximum_nominal_resistance_ohms=maximum_ohms,
        )
    )
    return OscillatorOutputPathMap(
        basis="Synthetic reviewed oscillator module output requirement",
        paths=(
            OscillatorOutputPathRequirement(
                id="module-clock-to-receivers",
                basis="The reviewed module datasheet requires the named signal path",
                oscillator_reference="X1",
                expected_oscillator_value="Synthetic clock module",
                expected_oscillator_symbol="Synthetic:ClockModule",
                expected_oscillator_footprint="Synthetic:ClockModule_4",
                output_pin="X1.1",
                topology=topology,
                load_pins=(
                    OscillatorOutputLoadRequirement(
                        reference="U2",
                        pin="U2.2",
                        expected_symbol="Synthetic:ReceiverA",
                        expected_footprint="Synthetic:SOIC8",
                    ),
                    OscillatorOutputLoadRequirement(
                        reference="U3",
                        pin="U3.3",
                        expected_symbol="Synthetic:ReceiverB",
                        expected_footprint="Synthetic:QFN16",
                    ),
                ),
                series_resistor=resistor,
            ),
        ),
    )


def oscillator_output_netlist(
    *,
    topology: str = "series",
    fault: str | None = None,
    resistor_value: str = "33R",
) -> NetlistContract:
    components = {
        "X1": ComponentContract(
            value="Synthetic clock module", footprint="Synthetic:ClockModule_4"
        ),
        "U2": ComponentContract(value="Synthetic receiver A", footprint="Synthetic:SOIC8"),
        "U3": ComponentContract(value="Synthetic receiver B", footprint="Synthetic:QFN16"),
    }
    symbols = {
        "X1": "Synthetic:ClockModule",
        "U2": "Synthetic:ReceiverA",
        "U3": "Synthetic:ReceiverB",
    }
    pin_numbers = {"X1": ("1", "2", "3", "4"), "U2": ("1", "2"), "U3": ("1", "2", "3")}
    dnp: tuple[str, ...] = ()
    if topology == "direct":
        nets = {"CLK": ("X1.1", "U2.2", "U3.3")}
    else:
        components["R1"] = ComponentContract(value=resistor_value, footprint="Synthetic:R_0603")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        nets = {
            "CLK_SOURCE": ("X1.1", "R1.1"),
            "CLK_LOAD": ("R1.2", "U2.2", "U3.3"),
        }

    if fault == "split-load":
        net = "CLK_LOAD" if topology == "series" else "CLK"
        nets[net] = tuple(pin for pin in nets[net] if pin != "U3.3")
        nets["OTHER"] = ("U3.3",)
    elif fault == "bypassed-resistor" and topology == "series":
        nets = {"CLK": ("X1.1", "R1.1", "R1.2", "U2.2", "U3.3")}
    elif fault == "wrong-resistor-side" and topology == "series":
        nets = {"CLK_SOURCE": ("X1.1", "R1.2"), "CLK_LOAD": ("R1.1", "U2.2", "U3.3")}
    elif (
        fault
        in {
            "extra-parallel-resistor",
            "zero-ohm-parallel-resistor",
            "dnp-parallel-resistor",
            "unrelated-resistor",
        }
        and topology == "series"
    ):
        extra_value = "0R" if fault == "zero-ohm-parallel-resistor" else "22R"
        components["R2"] = ComponentContract(value=extra_value, footprint="Synthetic:R_0603")
        symbols["R2"] = "Device:R"
        pin_numbers["R2"] = ("1", "2")
        if fault == "unrelated-resistor":
            nets["AUX_SOURCE"] = ("R2.1",)
            nets["AUX_LOAD"] = ("R2.2",)
        else:
            nets["CLK_SOURCE"] = (*nets["CLK_SOURCE"], "R2.1")
            nets["CLK_LOAD"] = (*nets["CLK_LOAD"], "R2.2")
        if fault == "dnp-parallel-resistor":
            dnp = ("R2",)
    elif fault == "resistor-missing" and topology == "series":
        components.pop("R1")
        symbols.pop("R1")
        pin_numbers.pop("R1")
        nets = {"CLK": ("X1.1", "U2.2", "U3.3")}
    elif fault == "wrong-oscillator-value":
        components["X1"] = ComponentContract(
            value="Different module", footprint="Synthetic:ClockModule_4"
        )
    elif fault == "dnp-resistor" and topology == "series":
        dnp = ("R1",)
    elif fault == "dnp-load":
        dnp = ("U2",)

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(
    observed: NetlistContract,
    path_map: OscillatorOutputPathMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-oscillator-output-path",
        observed=observed,
        netlist_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
    )
    return evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(
            oscillator_output_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def test_reviewed_direct_output_is_a_valid_control() -> None:
    path_map = oscillator_output_path_map(topology="direct")
    observed = oscillator_output_netlist(topology="direct")
    report = lint_report(observed, path_map)

    assert report.status == "PASS", report.issues
    assert RULE_ID not in {item.rule_id for item in report.findings}
    run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
    assert run.status == "EVALUATED"
    assert run.requirement_count == 1
    assert run.finding_count == 0
    assert run.netlist_sha256 == report.netlist_sha256
    assert run.map_sha256 == hashlib.sha256(path_map.model_dump_json().encode()).hexdigest()


@pytest.mark.parametrize("resistor_value", ("22R", "47R"))
def test_reviewed_series_output_and_inclusive_resistance_bounds_pass(
    resistor_value: str,
) -> None:
    report = lint_report(
        oscillator_output_netlist(resistor_value=resistor_value), oscillator_output_path_map()
    )
    assert report.status == "PASS", report.issues
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    ("fault", "expected_issue"),
    (
        ("split-load", "series load U3.3 is on OTHER"),
        ("bypassed-resistor", "does not separate output and load nets"),
        ("wrong-resistor-side", "R1.1 is not on oscillator output net"),
        ("resistor-missing", "R1 is absent or ambiguous"),
        ("wrong-oscillator-value", "X1 value is Different module"),
        ("dnp-resistor", "R1 is marked DNP"),
        ("dnp-load", "U2 is marked DNP"),
    ),
)
def test_mapped_topology_identity_population_and_load_faults_are_reviewed(
    fault: str, expected_issue: str
) -> None:
    report = lint_report(oscillator_output_netlist(fault=fault), oscillator_output_path_map())
    assert report.status == "REVIEW"
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert any(expected_issue in issue for issue in finding.evidence["issues"])


@pytest.mark.parametrize(
    ("fault", "expected_reference"),
    (("extra-parallel-resistor", "R2"), ("zero-ohm-parallel-resistor", "R2")),
)
def test_unmapped_fitted_resistor_across_series_path_is_reviewed(
    fault: str, expected_reference: str
) -> None:
    report = lint_report(oscillator_output_netlist(fault=fault), oscillator_output_path_map())

    assert report.status == "REVIEW"
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert any(
        f"unmapped fitted resistor {expected_reference} also bridges" in issue
        for issue in finding.evidence["issues"]
    )


@pytest.mark.parametrize("fault", ("dnp-parallel-resistor", "unrelated-resistor"))
def test_unmapped_resistor_outside_fitted_mapped_bridge_is_a_control(fault: str) -> None:
    report = lint_report(oscillator_output_netlist(fault=fault), oscillator_output_path_map())

    assert report.status == "PASS", report.issues
    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_wrong_resistor_value_is_the_distinct_cohort_gap() -> None:
    observed = oscillator_output_netlist(resistor_value="1k")
    mismatches = oscillator_output_path_mismatches(oscillator_output_path_map(), observed)

    assert len(mismatches) == 1
    assert any("nominal resistance is 1000 ohms" in issue for issue in mismatches[0].issues)
    finding = next(
        item
        for item in lint_report(observed, oscillator_output_path_map()).findings
        if item.rule_id == RULE_ID
    )
    assert finding.evidence["expected_topology"] == ("series",)
    assert finding.evidence["load_pins"] == ("U2.2", "U3.3")
    assert "does not assert that every clock output needs a resistor" in finding.message


def test_rule_uses_review_block_off_and_exact_ignore_lifecycle() -> None:
    observed = oscillator_output_netlist(resistor_value="1k")
    path_map = oscillator_output_path_map()
    reviewed = lint_report(observed, path_map)
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
    blocked = lint_report(
        observed,
        path_map,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic release policy requires the reviewed signal path",
        ),
    )
    assert blocked.status == "FAIL"
    disabled = lint_report(
        observed,
        path_map,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic project has no release requirement for this path",
        ),
    )
    off_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert off_finding.disposition == "RULE_OFF"
    ignored = lint_report(
        observed,
        path_map,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic test records a reviewed alternate value",
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_netlist_record_order_does_not_change_the_path_finding() -> None:
    observed = oscillator_output_netlist(resistor_value="1k")
    reversed_observed = observed.model_copy(
        update={"nets": dict(reversed(tuple(observed.nets.items())))}
    )
    first = next(
        item
        for item in lint_report(observed, oscillator_output_path_map()).findings
        if item.rule_id == RULE_ID
    )
    second = next(
        item
        for item in lint_report(reversed_observed, oscillator_output_path_map()).findings
        if item.rule_id == RULE_ID
    )

    assert first.fingerprint == second.fingerprint


@pytest.mark.parametrize(
    "values",
    (
        {"topology": "direct", "series_resistor": {"reference": "R1"}},
        {"topology": "series", "series_resistor": None},
    ),
)
def test_topology_and_resistor_contract_must_agree(values: OscillatorOutputPathUpdates) -> None:
    base = oscillator_output_path_map().paths[0].model_dump(mode="python")
    base.update(values)
    with pytest.raises(ValidationError):
        OscillatorOutputPathRequirement.model_validate(base)


def test_reversed_series_resistor_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        oscillator_output_path_map(minimum_ohms=48.0, maximum_ohms=47.0)
