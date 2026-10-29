"""Shared synthetic inputs for same-voltage split supply-input regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy, NetlistContract

RULE_ID = "component.same_voltage_power_inputs_split"


def same_voltage_power_input_netlist(
    *,
    nets: dict[str, tuple[str, ...]] | None = None,
    functions: dict[str, str] | None = None,
    electrical_types: dict[str, str] | None = None,
    pin_numbers: tuple[str, ...] = ("1", "2"),
    dnp: tuple[str, ...] = (),
    reference: str = "U1",
) -> NetlistContract:
    """Build an IC pin inventory with optional controlled fault mutations."""
    return NetlistContract(
        components={reference: ComponentContract(value="Synthetic IC", footprint="Synthetic:IC")},
        nets=({"+3V3": (f"{reference}.1",), "3.3V": (f"{reference}.2",)} if nets is None else nets),
        dnp_components=dnp,
        component_symbols={reference: "Lint:MultiSupplyIC"},
        component_pin_numbers={reference: pin_numbers},
        pin_functions=(
            {f"{reference}.1": "VDD", f"{reference}.2": "VDDIO"} if functions is None else functions
        ),
        pin_electrical_types=(
            {f"{reference}.1": "power_in", f"{reference}.2": "power_in"}
            if electrical_types is None
            else electrical_types
        ),
    )


def same_voltage_power_input_review_policy() -> DesignLintPolicy:
    """Explicitly enable the opt-in rule for synthetic fault/control cases."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic test explicitly enables this opt-in review heuristic",
            ),
        )
    )
