"""Project-authored nominal hold-up screening over an exact capacitor map."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.capacitor_hold_up_models import (
    CapacitorHoldUpMap,
    CapacitorHoldUpMember,
    CapacitorHoldUpRequirement,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_power_capacitor_hold_up import (
    capacitor_hold_up_candidates,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.capacitor_hold_up_below_project_minimum"


def hold_up_map(*, minimum_ms: float = 2000.0, value: str = "1F") -> CapacitorHoldUpMap:
    return CapacitorHoldUpMap(
        basis="Synthetic reviewed storage discharge requirement",
        requirements=(
            CapacitorHoldUpRequirement(
                id="backup-rail",
                basis="Synthetic constant-current operating window",
                capacitor_reference="C1",
                expected_value=value,
                expected_symbol="Device:C",
                expected_footprint="Synthetic:EDLC",
                expected_part_id="EDLC-1F",
                positive_pin="C1.1",
                return_pin="C1.2",
                positive_net="BACKUP_V",
                return_net="RETURN",
                starting_voltage_v=5.0,
                minimum_load_voltage_v=3.0,
                maximum_load_current_ma=1000.0,
                minimum_hold_up_ms=minimum_ms,
            ),
        ),
    )


def hold_up_netlist(
    *,
    value: str = "1F",
    part_id: str | None = "EDLC-1F",
    positive_net: str = "BACKUP_V",
    return_net: str = "RETURN",
    dnp: bool = False,
) -> NetlistContract:
    return NetlistContract(
        components={
            "C1": ComponentContract(
                value=value,
                footprint="Synthetic:EDLC",
                part_id=part_id,
            ),
        },
        nets={positive_net: ("C1.1",), return_net: ("C1.2",)},
        dnp_components=("C1",) if dnp else (),
        component_symbols={"C1": "Device:C"},
        component_pin_numbers={"C1": ("1", "2")},
    )


def parallel_bank_map(*, minimum_ms: float = 2000.0) -> CapacitorHoldUpMap:
    requirement_data = hold_up_map(minimum_ms=minimum_ms).requirements[0].model_dump()
    requirement_data.update(
        expected_value="0.5F",
        expected_part_id="EDLC-0.5F",
        parallel_capacitors=(
            CapacitorHoldUpMember(
                capacitor_reference="C2",
                expected_value="0.5F",
                expected_symbol="Device:C",
                expected_footprint="Synthetic:EDLC",
                expected_part_id="EDLC-0.5F",
                positive_pin="C2.1",
                return_pin="C2.2",
            ),
        ),
    )
    requirement = CapacitorHoldUpRequirement.model_validate(requirement_data)
    return CapacitorHoldUpMap(
        basis="Synthetic reviewed parallel storage bank",
        requirements=(requirement,),
    )


def parallel_bank_netlist(
    *,
    second_positive_net: str = "BACKUP_V",
    second_return_net: str = "RETURN",
    second_value: str = "0.5F",
    second_part_id: str | None = "EDLC-0.5F",
    second_dnp: bool = False,
    omit_second: bool = False,
) -> NetlistContract:
    components = {
        "C1": ComponentContract(
            value="0.5F",
            footprint="Synthetic:EDLC",
            part_id="EDLC-0.5F",
        ),
    }
    nets = {"BACKUP_V": ("C1.1",), "RETURN": ("C1.2",)}
    symbols = {"C1": "Device:C"}
    pin_numbers = {"C1": ("1", "2")}
    if not omit_second:
        components["C2"] = ComponentContract(
            value=second_value,
            footprint="Synthetic:EDLC",
            part_id=second_part_id,
        )
        nets[second_positive_net] = (*nets.get(second_positive_net, ()), "C2.1")
        nets[second_return_net] = (*nets.get(second_return_net, ()), "C2.2")
        symbols["C2"] = "Device:C"
        pin_numbers["C2"] = ("1", "2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=("C2",) if second_dnp and not omit_second else (),
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint(source: NetlistContract, *, minimum_ms: float = 2000.0, mode: str | None = None):
    policy = DesignLintPolicy(
        capacitor_hold_up_map=hold_up_map(minimum_ms=minimum_ms),
        rules=()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic project hold-up policy",
            ),
        ),
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-storage",
        observed=source,
        netlist_sha256="a" * 64,
    )
    return evaluate("synthetic-storage", coach, policy)


def catalog_reachable_rule_ids() -> set[str]:
    candidates = capacitor_hold_up_candidates(hold_up_netlist(), hold_up_map(minimum_ms=2001.0))
    return {item.rule_id for item in candidates}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_nominal_hold_up_below_authored_requirement_is_reviewed() -> None:
    report = lint(hold_up_netlist(), minimum_ms=2001.0)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert "2000" in finding.message
    assert "2001" in finding.message
    assert "constant-current load" in finding.message
    assert finding.evidence["estimated_hold_up_ms"] == ("2000.000000",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_threshold_is_a_valid_control() -> None:
    report = lint(hold_up_netlist())
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        hold_up_netlist(value="0.5F"),
        hold_up_netlist(part_id="EDLC-0.5F"),
        hold_up_netlist(positive_net="OTHER_V"),
        hold_up_netlist(dnp=True),
    ),
)
def test_replaced_disconnected_or_dnp_storage_part_is_reviewed(source: NetlistContract) -> None:
    report = lint(source)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.evidence["issues"]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_promote_the_source_mismatch_to_block() -> None:
    report = lint(hold_up_netlist(value="0.5F"), mode="block")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "block"
    assert report.status == "FAIL"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_output_is_order_stable() -> None:
    first = capacitor_hold_up_candidates(hold_up_netlist(), hold_up_map(minimum_ms=2001.0))
    second = capacitor_hold_up_candidates(hold_up_netlist(), hold_up_map(minimum_ms=2001.0))
    assert first == second


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_authored_hold_up_inputs_reject_reversed_voltage_window() -> None:
    invalid = hold_up_map().requirements[0].model_dump()
    invalid.update(starting_voltage_v=2.0, minimum_load_voltage_v=3.0)
    with pytest.raises(ValueError, match="Starting voltage must exceed"):
        CapacitorHoldUpRequirement.model_validate(invalid)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mapped_parallel_bank_sums_member_capacitance() -> None:
    report = evaluate(
        "synthetic-storage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-storage",
            observed=parallel_bank_netlist(),
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(capacitor_hold_up_map=parallel_bank_map()),
    )
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_parallel_bank_below_limit_reports_total_and_each_mapped_member() -> None:
    report = evaluate(
        "synthetic-storage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-storage",
            observed=parallel_bank_netlist(),
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(capacitor_hold_up_map=parallel_bank_map(minimum_ms=2001.0)),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.subject == "backup-rail: C1 + C2 hold-up review"
    assert finding.evidence["nominal_capacitance_pf"] == ("1000000000000.0",)
    assert finding.evidence["estimated_hold_up_ms"] == ("2000.0000000",)
    assert finding.evidence["parallel_capacitors"] == ("C2",)
    assert finding.evidence["bank_members"] == (
        "C1: PART_ID=EDLC-0.5F; value=0.5F; positive=C1.1=BACKUP_V; return=C1.2=RETURN",
        "C2: PART_ID=EDLC-0.5F; value=0.5F; positive=C2.1=BACKUP_V; return=C2.2=RETURN",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        parallel_bank_netlist(second_positive_net="OTHER_V"),
        parallel_bank_netlist(second_dnp=True),
        parallel_bank_netlist(second_value="0.25F", second_part_id="EDLC-0.25F"),
        parallel_bank_netlist(omit_second=True),
    ),
)
def test_parallel_bank_member_assignment_fit_or_value_regression_is_reviewed(
    source: NetlistContract,
) -> None:
    report = evaluate(
        "synthetic-storage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-storage",
            observed=source,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(capacitor_hold_up_map=parallel_bank_map()),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["issues"]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_parallel_member_is_not_counted_in_the_numeric_estimate() -> None:
    report = evaluate(
        "synthetic-storage",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-storage",
            observed=parallel_bank_netlist(second_dnp=True),
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(capacitor_hold_up_map=parallel_bank_map()),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert "C2 is marked DNP" in finding.evidence["issues"]
    assert finding.evidence["nominal_capacitance_pf"] == ()
    assert finding.evidence["estimated_hold_up_ms"] == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_parallel_bank_finding_is_stable_when_native_maps_are_reordered() -> None:
    source = parallel_bank_netlist(second_value="0.25F", second_part_id="EDLC-0.25F")
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    requirements = parallel_bank_map(minimum_ms=2001.0)
    first = capacitor_hold_up_candidates(source, requirements)
    second = capacitor_hold_up_candidates(reordered, requirements)
    assert first == second


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_parallel_bank_map_rejects_duplicate_member_reference() -> None:
    requirement = hold_up_map().requirements[0].model_dump()
    requirement["parallel_capacitors"] = (
        {
            "capacitor_reference": "C1",
            "expected_value": "0.5F",
            "expected_symbol": "Device:C",
            "expected_footprint": "Synthetic:EDLC",
            "expected_part_id": "EDLC-0.5F",
            "positive_pin": "C1.1",
            "return_pin": "C1.2",
        },
    )
    with pytest.raises(ValueError, match="A capacitor can appear only once"):
        CapacitorHoldUpRequirement.model_validate(requirement)
