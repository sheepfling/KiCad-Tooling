"""Tooling-owned parsed-netlist fixture for component supply-range lint."""

from __future__ import annotations

from kicad_tooling.hwrepo.component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    ComponentSupplyVoltageRangeRequirement,
)
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.netlist_contract_models import (
    ComponentContract,
    NetlistContract,
)

SUPPLY_SYMBOL = "Regulator_Linear:L7805"
SUPPLY_FOOTPRINT = "Package_TO_SOT_THT:TO-220-3_Vertical"
SUPPLY_PART_ID = "SYNTHETIC-SUPPLY-RANGE-IC"


def supply_range_requirement(
    *,
    id: str = "u1-input",
    pin: str = "U1.1",
    minimum_voltage_v: float = 7.0,
    maximum_voltage_v: float = 35.0,
    expected_pin_function: str = "IN",
    expected_symbol: str = SUPPLY_SYMBOL,
    expected_footprint: str = SUPPLY_FOOTPRINT,
    expected_part_id: str = SUPPLY_PART_ID,
) -> ComponentSupplyVoltageRangeRequirement:
    """Return one synthetic, exact-part supply-range map entry."""
    return ComponentSupplyVoltageRangeRequirement(
        id=id,
        reference="U1",
        expected_symbol=expected_symbol,
        expected_footprint=expected_footprint,
        expected_part_id=expected_part_id,
        pin=pin,
        expected_pin_function=expected_pin_function,
        minimum_voltage_v=minimum_voltage_v,
        maximum_voltage_v=maximum_voltage_v,
        range_source="Synthetic test basis only",
        range_conditions="Synthetic nominal-label boundary; not a device specification",
    )


def supply_range_map(
    *requirements: ComponentSupplyVoltageRangeRequirement,
) -> ComponentSupplyVoltageRangeMap:
    """Build the nonempty project map used by source-bound lint tests."""
    return ComponentSupplyVoltageRangeMap(
        basis="Synthetic tooling regression only",
        requirements=requirements or (supply_range_requirement(),),
    )


def supply_range_review_policy() -> DesignLintPolicy:
    """Return a policy that opts into the exact synthetic supply-range map."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="power.component_supply_voltage_outside_range",
                mode="review",
                reason="Synthetic test explicitly enables its mapped range review",
            ),
        ),
        component_supply_voltage_range_map=supply_range_map(),
    )


def supply_range_pin_coverage_review_policy() -> DesignLintPolicy:
    """Opt into mapped supply pin coverage with one deliberately omitted pin."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="power.component_supply_range_pin_coverage",
                mode="review",
                reason="Synthetic test explicitly enables mapped supply pin coverage",
            ),
        ),
        component_supply_voltage_range_map=supply_range_map(),
    )


def supply_range_netlist(
    *,
    input_net: str | None = "3V3",
    symbol: str = SUPPLY_SYMBOL,
    footprint: str = SUPPLY_FOOTPRINT,
    part_id: str | None = SUPPLY_PART_ID,
    pin_function: str = "IN",
    pin_electrical_type: str = "power_in",
    dnp: bool = False,
) -> NetlistContract:
    """Return a minimal native-netlist contract with one mapped supply pin."""
    nets = {"GND": ("U1.2",), "5V": ("U1.3",)}
    if input_net is not None:
        nets[input_net] = ("U1.1",)
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="L7805",
                footprint=footprint,
                part_id=part_id,
            )
        },
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions={"U1.1": pin_function, "U1.2": "GND", "U1.3": "OUT"},
        pin_electrical_types={
            "U1.1": pin_electrical_type,
            "U1.2": "power_in",
            "U1.3": "power_out",
        },
        component_pin_numbers={"U1": ("1", "2", "3")},
    )
