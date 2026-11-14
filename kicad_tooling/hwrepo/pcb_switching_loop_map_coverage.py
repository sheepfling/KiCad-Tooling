"""Review switching-regulator pads absent from authored PCB loop maps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from .design_lint_pcb_coverage_common import map_sha256
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .pcb_switching_loop_models import PcbSwitchingLoopMap
from .project_models import ProjectKind
from .switching_regulator_pins import is_switch_node_function

RULE_ID: DesignLintRuleId = "pcb.switching_regulator_loop_map_coverage"
_SYMBOL_LIBRARY = "regulator_switching"
_Value = TypeVar("_Value")


def _one_value_by_casefold(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [value for name, value in mapping.items() if name.casefold() == key.casefold()]
    return matches[0] if len(matches) == 1 else None


def _complete_pin_inventory(
    observed: NetlistContract,
    reference: str,
) -> tuple[tuple[str, str, str], ...] | None:
    numbers = _one_value_by_casefold(observed.component_pin_numbers, reference)
    if not isinstance(numbers, tuple) or not numbers:
        return None
    normalized_numbers = tuple(str(number).strip() for number in numbers)
    if (
        any(not number for number in normalized_numbers)
        or len({number.casefold() for number in normalized_numbers}) != len(normalized_numbers)
    ):
        return None

    pins: list[tuple[str, str, str]] = []
    for number in normalized_numbers:
        pin = f"{reference}.{number}"
        function = _one_value_by_casefold(observed.pin_functions, pin)
        electrical_type = _one_value_by_casefold(observed.pin_electrical_types, pin)
        if not isinstance(function, str) or not function.strip():
            return None
        if not isinstance(electrical_type, str) or not electrical_type.strip():
            return None
        pins.append((pin, function.strip(), electrical_type.strip().casefold()))
    return tuple(sorted(pins, key=lambda item: item[0].casefold()))


def _pin_net_index(observed: NetlistContract) -> dict[str, frozenset[str]]:
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)
    return {pin: frozenset(nets) for pin, nets in assignments.items()}


def switching_regulator_loop_map_candidates(
    observed: NetlistContract,
    project_kind: ProjectKind | None,
    loop_map: PcbSwitchingLoopMap | None,
    netlist_sha256: str | None,
) -> tuple[Candidate, ...]:
    """Prompt for loop-map review when exact fitted regulator pins are unmapped.

    Recognition requires complete native pin functions and electrical types,
    one net per recognized switch-node pin, a fitted component, and the exact
    KiCad ``Regulator_Switching`` library prefix. This reports map coverage only.
    """
    if project_kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY} or netlist_sha256 is None:
        return ()

    mapped_pads: set[str] = (
        {
            pad.pad.casefold()
            for requirement in loop_map.requirements
            for pad in requirement.loop_pads
        }
        if loop_map is not None
        else set()
    )
    map_fingerprint = map_sha256(loop_map) if loop_map is not None else "absent"
    net_assignments = _pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    candidates: list[Candidate] = []

    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        if reference.casefold() in dnp:
            continue
        library, separator, part = symbol.partition(":")
        if not separator or library.casefold() != _SYMBOL_LIBRARY or not part.strip():
            continue
        component = _one_value_by_casefold(observed.components, reference)
        if component is None or not component.footprint.strip():
            continue
        pins = _complete_pin_inventory(observed, reference)
        if pins is None:
            continue

        switch_pins = tuple(
            (pin, function, electrical_type, net_assignments.get(pin.casefold(), frozenset()))
            for pin, function, electrical_type in pins
            if is_switch_node_function(function)
        )
        if not switch_pins or any(len(nets) != 1 for _, _, _, nets in switch_pins):
            continue
        unmapped = tuple(item for item in switch_pins if item[0].casefold() not in mapped_pads)
        if not unmapped:
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference}: switching-regulator switch-node pads are absent from "
                    "the authored loop map"
                ),
                message=(
                    "Native netlist evidence identifies a fitted switching-regulator symbol and "
                    f"switch-node pads {', '.join(item[0] for item in unmapped)} not listed in "
                    "any project-authored switching-loop requirement. Review whether each pad "
                    "needs loop and return-plane coverage; this prompt does not assert a defect."
                ),
                evidence={
                    "component_reference": (reference,),
                    "component_symbol": (symbol,),
                    "footprint": (component.footprint,),
                    "switch_node_pins": tuple(item[0] for item in switch_pins),
                    "switch_node_functions": tuple(item[1] for item in switch_pins),
                    "switch_node_electrical_types": tuple(item[2] for item in switch_pins),
                    "switch_node_nets": tuple(
                        f"{pin} -> {next(iter(nets))}"
                        for pin, _, _, nets in switch_pins
                    ),
                    "mapped_switch_node_pins": tuple(
                        item[0] for item in switch_pins if item[0].casefold() in mapped_pads
                    ),
                    "unmapped_switch_node_pins": tuple(item[0] for item in unmapped),
                    "switching_loop_map_sha256": (map_fingerprint,),
                    "netlist_sha256": (netlist_sha256,),
                },
            )
        )
    return tuple(candidates)
