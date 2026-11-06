"""Project-mapped LED current-window findings from source-bound netlists."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .led_current_models import LedCurrentMap
from .led_current_range import scan_led_current_map
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "component.mapped_led_current_range_mismatch"


def led_current_range_candidates(
    observed: NetlistContract,
    led_map: LedCurrentMap | None,
    netlist_sha256: str | None,
) -> tuple[Candidate, ...]:
    """Review only explicitly mapped LED paths with incomplete or out-of-range evidence."""
    if led_map is None:
        return ()
    entries = scan_led_current_map(led_map, observed, netlist_sha256)
    return tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{entry.led_reference}: mapped LED current range",
            message=(
                "The source-bound LED path is incomplete or its tolerance-corner current estimate "
                "falls outside the project-authored window. Review the exact LED, resistor, "
                "source-voltage and forward-voltage requirements. This ideal DC estimate does "
                "not establish electrical safety, brightness, dynamic behavior, or PCB continuity."
            ),
            evidence={
                "map_id": (entry.id,),
                "map_sha256": (entry.map_sha256,),
                "netlist_sha256": (entry.netlist_sha256 or "unavailable",),
                "map_basis": (entry.map_basis,),
                "led_reference": (entry.led_reference,),
                "resistor_reference": (entry.resistor_reference,),
                "source_net": (entry.source_net,),
                "return_net": (entry.return_net,),
                "led_side_net": (entry.led_side_net,),
                "source_voltage_v": (f"{entry.source_minimum_v:g}–{entry.source_maximum_v:g}",),
                "source_voltage_basis": (entry.source_voltage_basis,),
                "forward_voltage_v": (
                    (f"{entry.forward_voltage_minimum_v:g}–{entry.forward_voltage_maximum_v:g}"),
                ),
                "forward_voltage_basis": (entry.forward_voltage_basis,),
                "target_current_ma": (
                    (f"{entry.target_current_minimum_ma:g}–{entry.target_current_maximum_ma:g}"),
                ),
                "target_current_basis": (entry.target_current_basis,),
                "resistor_nominal_ohms": (
                    "unavailable"
                    if entry.resistance_ohms is None
                    else f"{entry.resistance_ohms:g}",
                ),
                "resistor_range_ohms": (
                    (
                        f"{entry.minimum_nominal_resistance_ohms:g}–"
                        f"{entry.maximum_nominal_resistance_ohms:g}"
                    ),
                ),
                "resistor_tolerance": (
                    f"{entry.maximum_tolerance_percent:g}% ({entry.tolerance_basis})",
                ),
                "calculated_current_ma": (
                    "unavailable"
                    if entry.calculated_current_minimum_ma is None
                    or entry.calculated_current_maximum_ma is None
                    else (
                        f"{entry.calculated_current_minimum_ma:g}–"
                        f"{entry.calculated_current_maximum_ma:g}"
                    ),
                ),
                "pin_nets": tuple(
                    f"{pin}={','.join(nets) or '<unconnected>'}"
                    for pin, nets in sorted(entry.pin_nets.items())
                ),
                "issues": entry.issues,
            },
        )
        for entry in entries
        if entry.status != "MATCHED"
    )
