"""Review source power-pin nets omitted from authored PCB width scopes."""

from __future__ import annotations

from collections import Counter

from .casefold_mapping_lookup import lookup_unique_casefold
from .design_lint_pcb_coverage_common import map_sha256
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .pcb_track_width_models import PcbTrackWidthMap
from .project_models import ProjectKind

RULE_ID: DesignLintRuleId = "pcb.power_pin_net_track_width_map_coverage"
_POWER_PIN_TYPES = frozenset({"power_in", "power_out"})


def power_pin_net_track_width_map_candidates(
    observed: NetlistContract,
    project_kind: ProjectKind | None,
    track_width_map: PcbTrackWidthMap | None,
    netlist_sha256: str | None,
) -> tuple[Candidate, ...]:
    """Prompt when fitted native power-pin nets are absent from width review scope.

    This discovers candidate map omissions from native schematic pin types. It
    does not infer required widths, current, copper capacity, or board routing.
    """
    if project_kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY} or netlist_sha256 is None:
        return ()

    mapped_nets: set[str] = (
        {item.net.casefold() for item in track_width_map.requirements}
        if track_width_map is not None
        else set()
    )
    if "*" in mapped_nets:
        return ()

    net_name_counts = Counter(net.casefold() for net in observed.nets)
    pin_assignments = netlist_pin_net_index(observed)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    map_fingerprint = map_sha256(track_width_map) if track_width_map is not None else "absent"
    candidates: list[Candidate] = []

    for net, pins in sorted(observed.nets.items(), key=lambda item: (item[0].casefold(), item[0])):
        net_key = net.casefold()
        if net_key in mapped_nets or net_name_counts[net_key] != 1:
            continue

        power_pins: list[tuple[str, str, str, str]] = []
        for pin in pins:
            reference, separator, number = pin.rpartition(".")
            if (
                not separator
                or not reference
                or not number
                or reference.casefold() in dnp_references
            ):
                continue
            component = lookup_unique_casefold(observed.components, reference)
            inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
            electrical_type = lookup_unique_casefold(observed.pin_electrical_types, pin)
            if (
                component is None
                or not component.footprint.strip()
                or inventory is None
                or not any(str(item).casefold() == number.casefold() for item in inventory)
                or electrical_type is None
                or electrical_type.casefold() not in _POWER_PIN_TYPES
                or len(pin_assignments.get(pin.casefold(), ())) != 1
            ):
                continue
            function = lookup_unique_casefold(observed.pin_functions, pin)
            power_pins.append(
                (
                    pin,
                    function.strip() if function is not None else "<unreported>",
                    electrical_type.casefold(),
                    component.footprint,
                )
            )

        if not power_pins:
            continue
        pins_evidence = tuple(
            f"{pin}: function={function}; type={electrical_type}; footprint={footprint}"
            for pin, function, electrical_type, footprint in sorted(
                set(power_pins), key=lambda item: (item[0].casefold(), item[0])
            )
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{net}: native power-pin net is absent from track-width review scope",
                message=(
                    f"The native schematic netlist assigns fitted footprint pins with KiCad "
                    f"power_in/power_out types to {net!r}, but this net is not listed in "
                    "pcb_track_width_map. Review whether the project should author a width "
                    "screen for it. This prompt does not estimate current, copper capacity, "
                    "temperature, PCB connectivity, or a required width."
                ),
                evidence={
                    "net": (net,),
                    "power_pin_assignments": pins_evidence,
                    "netlist_sha256": (netlist_sha256,),
                    "track_width_map_sha256": (map_fingerprint,),
                },
            )
        )
    return tuple(candidates)
