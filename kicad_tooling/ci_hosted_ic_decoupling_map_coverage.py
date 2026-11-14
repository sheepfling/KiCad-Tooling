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
    """Native-derived results for pin and whole-component map coverage."""

    control_issues: tuple[IcDecouplingMapCoverageIssue, ...]
    fault_issues: tuple[IcDecouplingMapCoverageIssue, ...]
    component_control_issues: tuple[IcDecouplingMapCoverageIssue, ...]
    component_fault_issues: tuple[IcDecouplingMapCoverageIssue, ...]


def evaluate_ic_decoupling_map_coverage_native_probe(
    observed: NetlistContract,
) -> IcDecouplingMapCoverageNativeProbe:
    """Check mapped U1, plus an entirely omitted native U3 power input."""

    def mapped(pins: tuple[tuple[str, str], ...]) -> IcDecouplingMap:
        requirements: list[IcDecouplingRequirement] = []
        for reference, pin in pins:
            component = observed.components[reference]
            capacitor_reference = "C1" if reference == "U1" else "C2"
            capacitor = IcDecouplingCapacitorRequirement(
                reference=capacitor_reference,
                expected_symbol="Device:C",
                expected_footprint="Synthetic:Capacitor",
                power_pin=f"{capacitor_reference}.1",
                return_pin=f"{capacitor_reference}.2",
            )
            requirements.append(
                IcDecouplingRequirement(
                    id=f"native-{pin.casefold().replace('.', '-')}-coverage",
                    basis="Tooling-owned native pin-coverage regression only",
                    ic_reference=reference,
                    expected_ic_value=component.value,
                    expected_ic_symbol=observed.component_symbols[reference],
                    expected_ic_footprint=component.footprint,
                    power_pin=pin,
                    power_net="+3V3",
                    return_net="GND",
                    minimum_total_capacitance_pf=100_000.0,
                    capacitors=(capacitor,),
                )
            )
        return IcDecouplingMap(requirements=tuple(requirements))

    probe = IcDecouplingMapCoverageNativeProbe(
        control_issues=ic_decoupling_map_coverage_issues(
            observed, mapped((("U1", "U1.1"), ("U3", "U3.1")))
        ),
        fault_issues=ic_decoupling_map_coverage_issues(
            observed, mapped((("U1", "U1.2"), ("U3", "U3.1")))
        ),
        component_control_issues=ic_decoupling_map_coverage_issues(
            observed, mapped((("U1", "U1.1"), ("U3", "U3.1")))
        ),
        component_fault_issues=ic_decoupling_map_coverage_issues(
            observed, mapped((("U1", "U1.1"),))
        ),
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
    if probe.component_control_issues:
        raise ValueError("Native complete IC decoupling component map did not remain quiet")
    if len(probe.component_fault_issues) != 1:
        raise ValueError("Native omitted IC decoupling-map component did not produce one review")
    component_fault = probe.component_fault_issues[0]
    if (
        component_fault.reference != "U3"
        or component_fault.native_power_input_pins != ("U3.1",)
        or not component_fault.component_unmapped_from_map
    ):
        raise ValueError("Native omitted-component coverage evidence differs from expected U3")
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
            "ic_decoupling_map_component_coverage_control": "not_run",
            "ic_decoupling_map_component_coverage_fault": "not_run",
        }
    if probe is None:
        raise ValueError("Native IC decoupling-map coverage probe is unavailable")
    return {
        "ic_decoupling_map_pin_coverage_control": "quiet",
        "ic_decoupling_map_pin_coverage_fault": ";".join(
            probe.fault_issues[0].unmapped_power_input_pins
        ),
        "ic_decoupling_map_component_coverage_control": (
            "quiet" if not probe.component_control_issues else "unexpected_review"
        ),
        "ic_decoupling_map_component_coverage_fault": ";".join(
            probe.component_fault_issues[0].native_power_input_pins
        ),
    }
