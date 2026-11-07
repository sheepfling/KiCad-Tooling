"""Project-authored nominal hold-up screening over an exact capacitor map."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.capacitor_hold_up_models import (
    CapacitorHoldUpMap,
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
