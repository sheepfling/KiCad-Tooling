"""Native-netlist fault/control probes for IC decoupling-map pin coverage."""

from __future__ import annotations

from dataclasses import dataclass

from .hwrepo.ic_decoupling_models import (
    IcDecouplingCapacitorRequirement,
    IcDecouplingMap,
    IcDecouplingRequirement,
)
from .hwrepo.netlist_contract_models import NetlistContract
from .hwrepo.power_ic_decoupling_map_coverage import (
    IcDecouplingMapCoverageIssue,
    ic_decoupling_map_coverage_issues,
)


@dataclass(frozen=True, slots=True)
class IcDecouplingMapCoverageNativeProbe:
    """Native-derived results for one complete and one omitted-pin map."""

    control_issues: tuple[IcDecouplingMapCoverageIssue, ...]
    fault_issues: tuple[IcDecouplingMapCoverageIssue, ...]


def evaluate_ic_decoupling_map_coverage_native_probe(
    observed: NetlistContract,
) -> IcDecouplingMapCoverageNativeProbe:
    """Compare the native U1.1 input against complete and deliberately wrong maps."""
    component = observed.components["U1"]
    symbol = observed.component_symbols["U1"]
    capacitors = (
        IcDecouplingCapacitorRequirement(
            reference="C1",
            expected_symbol="Device:C",
            expected_footprint="Synthetic:Capacitor",
            power_pin="C1.1",
            return_pin="C1.2",
        ),
    )

    def mapped(pin: str) -> IcDecouplingMap:
        return IcDecouplingMap(
            requirements=(
                IcDecouplingRequirement(
                    id=f"native-{pin.casefold().replace('.', '-')}-coverage",
                    basis="Tooling-owned native pin-coverage regression only",
                    ic_reference="U1",
                    expected_ic_value=component.value,
                    expected_ic_symbol=symbol,
                    expected_ic_footprint=component.footprint,
                    power_pin=pin,
                    power_net="+3V3",
                    return_net="GND",
                    minimum_total_capacitance_pf=100_000.0,
                    capacitors=capacitors,
                ),
            )
        )

    probe = IcDecouplingMapCoverageNativeProbe(
        control_issues=ic_decoupling_map_coverage_issues(observed, mapped("U1.1")),
        fault_issues=ic_decoupling_map_coverage_issues(observed, mapped("U1.2")),
    )
    if probe.control_issues:
        raise ValueError("Native complete IC decoupling map did not remain quiet")
    if len(probe.fault_issues) != 1:
        raise ValueError("Native omitted IC power-input pin did not produce one review")
    fault = probe.fault_issues[0]
    if fault.unmapped_power_input_pins != ("U1.1",) or fault.pin_inventory_disagreement_pins != (
        "U1.2",
    ):
        raise ValueError("Native IC decoupling-map coverage evidence differs from expected pins")
    return probe


def ic_decoupling_map_coverage_event_fields(
    case: str,
    probe: IcDecouplingMapCoverageNativeProbe | None,
) -> dict[str, str]:
    """Return native lane fields without claiming a result for other fixtures."""
    if case != "decoupling-map-coverage":
        return {
            "ic_decoupling_map_pin_coverage_control": "not_run",
            "ic_decoupling_map_pin_coverage_fault": "not_run",
        }
    if probe is None:
        raise ValueError("Native IC decoupling-map coverage probe is unavailable")
    return {
        "ic_decoupling_map_pin_coverage_control": "quiet",
        "ic_decoupling_map_pin_coverage_fault": ";".join(
            probe.fault_issues[0].unmapped_power_input_pins
        ),
    }
