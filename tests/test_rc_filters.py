"""Synthetic regressions for explicitly mapped first-order RC filters."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    RcFilterMap,
    RcFilterRequirement,
)


def rc_filter_map() -> RcFilterMap:
    return RcFilterMap(
        filters=(
            RcFilterRequirement(
                id="sensor-input",
                resistor_reference="R1",
                expected_resistor_symbol="Device:R",
                expected_resistor_footprint="Synthetic:0603",
                resistor_first_pin="R1.1",
                resistor_second_pin="R1.2",
                capacitor_reference="C1",
                expected_capacitor_symbol="Device:C",
                expected_capacitor_footprint="Synthetic:0603",
                capacitor_signal_pin="C1.1",
                capacitor_reference_pin="C1.2",
                input_net="FILTER_IN",
                filtered_net="FILTER_OUT",
                reference_net="GND",
                minimum_nominal_resistance_ohms=900,
                maximum_nominal_resistance_ohms=1100,
                minimum_nominal_capacitance_pf=90000,
                maximum_nominal_capacitance_pf=110000,
                minimum_target_corner_hz=1500,
                maximum_target_corner_hz=1700,
                basis="Synthetic interface timing requirement and reviewed RC topology",
            ),
        ),
    )


def rc_filter_netlist(
    *,
    resistor_value: str = "1k",
    capacitor_value: str = "100nF",
    fault: str | None = None,
) -> NetlistContract:
    components = {
        "R1": ComponentContract(value=resistor_value, footprint="Synthetic:0603"),
        "C1": ComponentContract(value=capacitor_value, footprint="Synthetic:0603"),
    }
    symbols = {"R1": "Device:R", "C1": "Device:C"}
    pin_numbers = {"R1": ("1", "2"), "C1": ("1", "2")}
    nets: dict[str, tuple[str, ...]] = {
        "FILTER_IN": ("R1.1",),
        "FILTER_OUT": ("R1.2", "C1.1"),
        "GND": ("C1.2",),
    }
    dnp: tuple[str, ...] = ()
    if fault == "wrong-capacitor-net":
        nets["FILTER_OUT"] = ("R1.2",)
        nets["OTHER_FILTER"] = ("C1.1",)
    elif fault == "disconnected-capacitor-return":
        nets.pop("GND")
    elif fault == "dnp-capacitor":
        dnp = ("C1",)
    elif fault == "missing-capacitor-component":
        components.pop("C1")
        symbols.pop("C1")
        pin_numbers.pop("C1")
    elif fault == "missing-capacitor-pin-inventory":
        pin_numbers.pop("C1")
    elif fault == "unsupported-resistor-value":
        components["R1"] = ComponentContract(value="top", footprint="Synthetic:0603")
    elif fault == "wrong-capacitor-symbol":
        symbols["C1"] = "Device:LED"
    elif fault == "wrong-resistor-footprint":
        components["R1"] = ComponentContract(value=resistor_value, footprint="Synthetic:QFN")
    elif fault == "unsupported-capacitor-value":
        components["C1"] = ComponentContract(value="filter-cap", footprint="Synthetic:0603")
    elif fault == "extra-parallel-capacitor":
        components["C2"] = ComponentContract(value="10nF", footprint="Synthetic:0603")
        symbols["C2"] = "Device:C"
        pin_numbers["C2"] = ("1", "2")
        nets["FILTER_OUT"] = (*nets["FILTER_OUT"], "C2.1")
        nets["GND"] = (*nets["GND"], "C2.2")
    elif fault == "extra-parallel-resistor":
        components["R2"] = ComponentContract(value="10k", footprint="Synthetic:0603")
        symbols["R2"] = "Device:R"
        pin_numbers["R2"] = ("1", "2")
        nets["FILTER_IN"] = (*nets["FILTER_IN"], "R2.1")
        nets["FILTER_OUT"] = (*nets["FILTER_OUT"], "R2.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def report(
    netlist: NetlistContract,
    filter_map: RcFilterMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
    netlist_sha256: str = "e" * 64,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-rc-filter",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate(
        "synthetic-rc-filter",
        coach,
        DesignLintPolicy(
            rc_filter_map=filter_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def test_explicit_network_and_calculated_corner_pass() -> None:
    result = report(rc_filter_netlist(), rc_filter_map())
    assert result.status == "PASS", result.issues
    coverage = result.rc_filter_coverage
    assert coverage.status == "COMPLETE"
    assert coverage.netlist_sha256 == "e" * 64
    assert coverage.entries[0].status == "COMPLETE"
    assert coverage.entries[0].calculated_corner_hz == pytest.approx(1591.55, abs=0.02)
    assert not any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)


@pytest.mark.parametrize(
    ("resistor_value", "capacitor_value", "expected_corner_hz"),
    (("1k", "220nF", 723.43), ("2k", "100nF", 795.77)),
)
def test_schematic_value_mutations_are_detected_with_topology_unchanged(
    resistor_value: str,
    capacitor_value: str,
    expected_corner_hz: float,
) -> None:
    original = rc_filter_netlist()
    changed = rc_filter_netlist(
        resistor_value=resistor_value,
        capacitor_value=capacitor_value,
    )
    assert original.nets == changed.nets
    assert original.component_pin_numbers == changed.component_pin_numbers

    result = report(changed, rc_filter_map())
    assert result.status == "REVIEW"
    entry = result.rc_filter_coverage.entries[0]
    assert entry.status == "OUT_OF_RANGE"
    assert entry.calculated_corner_hz == pytest.approx(expected_corner_hz, abs=0.02)
    finding = next(item for item in result.findings if item.rule_id == "filter.rc_corner_mismatch")
    assert "calculated_nominal_corner_hz" in finding.evidence
    assert "1500–1700 Hz" in finding.evidence["target_corner_hz"]
    assert "RC filter coverage: COMPLETE" in text_report(result)


def test_corner_mismatch_is_order_stable_and_corrected_value_clears_it() -> None:
    rule_id = "filter.rc_corner_mismatch"
    source = rc_filter_netlist(capacitor_value="220nF")

    def lint(netlist: NetlistContract):
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        return source_hash, report(netlist, rc_filter_map(), netlist_sha256=source_hash)

    source_hash, original = lint(source)
    assert original.rc_filter_coverage.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash, reordered = lint(reordered_source)
    assert source_hash != reordered_hash
    assert reordered.rc_filter_coverage.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    repaired_hash, repaired = lint(rc_filter_netlist())
    assert source_hash != repaired_hash
    assert rule_id not in {item.rule_id for item in repaired.findings}


@pytest.mark.parametrize(
    "fault",
    (
        "wrong-capacitor-net",
        "disconnected-capacitor-return",
        "dnp-capacitor",
        "missing-capacitor-component",
        "missing-capacitor-pin-inventory",
        "wrong-capacitor-symbol",
        "wrong-resistor-footprint",
        "unsupported-capacitor-value",
        "unsupported-resistor-value",
        "extra-parallel-capacitor",
        "extra-parallel-resistor",
    ),
)
def test_wrong_assignment_dnp_missing_inventory_and_extra_parts_need_review(fault: str) -> None:
    result = report(rc_filter_netlist(fault=fault), rc_filter_map())
    assert result.rc_filter_coverage.status == "INCOMPLETE"
    assert result.rc_filter_coverage.entries[0].status == "INCOMPLETE"
    assert result.status == "REVIEW"
    assert any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)


def test_rule_can_be_blocked_or_disabled_and_exact_ignore_is_project_owned() -> None:
    out_of_range = rc_filter_netlist(capacitor_value="220nF")
    blocked = report(
        out_of_range,
        rc_filter_map(),
        override=DesignLintRuleOverride(
            rule_id="filter.rc_corner_mismatch",
            mode="block",
            reason="This interface's filter corner is a release requirement",
        ),
    )
    assert blocked.status == "FAIL"

    candidate = next(
        item
        for item in report(out_of_range, rc_filter_map()).findings
        if item.rule_id == "filter.rc_corner_mismatch"
    )
    ignored = report(
        out_of_range,
        rc_filter_map(),
        ignore=DesignLintIgnore(
            rule_id=candidate.rule_id,
            fingerprint=candidate.fingerprint,
            reason="Reviewed against the approved input filter specification",
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "filter.rc_corner_mismatch"
    )
    assert ignored.status == "PASS"
    assert ignored_finding.disposition == "IGNORED"

    disabled = report(
        out_of_range,
        rc_filter_map(),
        override=DesignLintRuleOverride(
            rule_id="filter.rc_corner_mismatch",
            mode="off",
            reason="Not applicable to this assembly configuration",
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "filter.rc_corner_mismatch"
    )
    assert disabled.status == "PASS"
    assert disabled_finding.disposition == "RULE_OFF"


def test_unmapped_network_is_not_inferred_and_coverage_is_not_requested() -> None:
    result = report(rc_filter_netlist())
    assert result.rc_filter_coverage.status == "NOT_REQUESTED"
    assert not any(item.rule_id == "filter.rc_corner_mismatch" for item in result.findings)


@pytest.mark.parametrize(
    ("field", "value"),
    (("resistor_first_pin", "R9.1"), ("minimum_target_corner_hz", 1800)),
)
def test_invalid_component_ownership_and_ranges_are_rejected(
    field: str,
    value: str | int,
) -> None:
    data = rc_filter_map().filters[0].model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        RcFilterRequirement.model_validate(data)
