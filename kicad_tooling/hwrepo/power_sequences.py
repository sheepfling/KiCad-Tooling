"""Project-authored power-sequence topology checks against native netlists."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar

from .models import NetlistContract, PowerSequenceMap, PowerSequenceStageRequirement

_Value = TypeVar("_Value")


@dataclass(frozen=True)
class PowerSequenceMismatch:
    stage_id: str
    stage_basis: str
    enable_control: str
    expected_endpoints: tuple[str, ...]
    output_pin: str
    output_net: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class PowerSequenceObservedCycle:
    """A cycle observed between exactly mapped stage outputs and enable pins."""

    stage_ids: tuple[str, ...]
    edges: tuple[str, ...]


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _pin_nets(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            net
            for net, pins in observed.nets.items()
            if any(candidate.casefold() == pin.casefold() for candidate in pins)
        )
    )


def _endpoint_issues(
    stage: PowerSequenceStageRequirement, observed: NetlistContract
) -> tuple[str, ...]:
    issues: list[str] = []
    endpoints = tuple(
        item for item in (stage.output, stage.power_good, stage.enable) if item is not None
    )
    component = _lookup(observed.components, stage.output.reference)
    if component is None:
        issues.append(f"{stage.output.reference} is absent or ambiguous in the native netlist")
    else:
        if component.footprint != stage.output.footprint:
            issues.append(
                f"{stage.output.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {stage.output.footprint}"
            )
        if stage.output.part_id is not None:
            actual_part_id = component.part_id
            if (
                actual_part_id is None
                or actual_part_id.casefold() != stage.output.part_id.casefold()
            ):
                issues.append(
                    f"{stage.output.reference} PART_ID is {actual_part_id or '<unknown>'}; "
                    f"expected {stage.output.part_id}"
                )

    symbol = _lookup(observed.component_symbols, stage.output.reference)
    if symbol != stage.output.symbol:
        issues.append(
            f"{stage.output.reference} symbol is {symbol or '<unknown>'}; "
            f"expected {stage.output.symbol}"
        )
    if stage.output.reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{stage.output.reference} is marked DNP but is required by the map")

    pin_numbers = _lookup(observed.component_pin_numbers, stage.output.reference)
    if pin_numbers is None:
        issues.append(f"{stage.output.reference} native pin inventory is unavailable or ambiguous")
    else:
        native_numbers = {str(number).casefold() for number in pin_numbers}
        for endpoint in endpoints:
            number = endpoint.pin.rsplit(".", 1)[1]
            if number.casefold() not in native_numbers:
                issues.append(f"{endpoint.pin} is absent from the native pin inventory")
                continue
            actual_nets = _pin_nets(observed, endpoint.pin)
            if actual_nets != (endpoint.net,):
                assigned = ", ".join(actual_nets) if actual_nets else "unconnected"
                issues.append(f"{endpoint.pin} is assigned to {assigned}; expected {endpoint.net}")
    return tuple(issues)


def _declared_graph_has_cycle(sequence_map: PowerSequenceMap) -> bool:
    adjacency: dict[str, set[str]] = {stage.id.casefold(): set() for stage in sequence_map.stages}
    indegree = {stage.id.casefold(): 0 for stage in sequence_map.stages}
    for dependency in sequence_map.dependencies:
        predecessor = dependency.predecessor_stage.casefold()
        successor = dependency.successor_stage.casefold()
        if successor not in adjacency[predecessor]:
            adjacency[predecessor].add(successor)
            indegree[successor] += 1

    ready = sorted(stage_id for stage_id, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for successor in sorted(adjacency[current]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort()
    return visited != len(indegree)


def power_sequence_observed_enable_cycles(
    sequence_map: PowerSequenceMap, observed: NetlistContract
) -> tuple[PowerSequenceObservedCycle, ...]:
    """Find cycles in exact mapped output-to-enable net assignments.

    This deliberately requires every participating stage's full mapped endpoint
    inventory and identity to match the source-bound netlist. It does not infer
    regulator roles, control polarity, or sequencing requirements from names.
    """
    stages = {stage.id.casefold(): stage for stage in sequence_map.stages}
    adjacency: dict[str, set[str]] = {stage_id: set() for stage_id in stages}
    edge_nets: dict[tuple[str, str], str] = {}
    valid_stages = {
        stage_id: stage
        for stage_id, stage in stages.items()
        if stage.enable is not None and not _endpoint_issues(stage, observed)
    }
    for predecessor_id, predecessor in valid_stages.items():
        output_nets = _pin_nets(observed, predecessor.output.pin)
        if len(output_nets) != 1:
            continue
        output_net = output_nets[0]
        for successor_id, successor in valid_stages.items():
            successor_enable = successor.enable
            if successor_enable is None:
                continue
            enable_nets = _pin_nets(observed, successor_enable.pin)
            if len(enable_nets) != 1 or output_net.casefold() != enable_nets[0].casefold():
                continue
            adjacency[predecessor_id].add(successor_id)
            edge_nets[(predecessor_id, successor_id)] = output_net

    next_index = 0
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal next_index
        indices[node] = next_index
        low_links[node] = next_index
        next_index += 1
        stack.append(node)
        on_stack.add(node)

        for successor in sorted(adjacency[node]):
            if successor not in indices:
                visit(successor)
                low_links[node] = min(low_links[node], low_links[successor])
            elif successor in on_stack:
                low_links[node] = min(low_links[node], indices[successor])

        if low_links[node] != indices[node]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(tuple(sorted(component)))

    for stage_id in sorted(adjacency):
        if stage_id not in indices:
            visit(stage_id)

    cycles: list[PowerSequenceObservedCycle] = []
    for component in components:
        members = set(component)
        if len(component) == 1 and component[0] not in adjacency[component[0]]:
            continue
        edge_evidence: list[str] = []
        for source in component:
            for target in sorted(adjacency[source] & members):
                target_enable = stages[target].enable
                if target_enable is None:
                    continue
                edge_evidence.append(
                    f"{stages[source].id} output {stages[source].output.pin} on "
                    f"{edge_nets[(source, target)]} → {stages[target].id} enable "
                    f"{target_enable.pin}"
                )
        edges = tuple(edge_evidence)
        cycles.append(
            PowerSequenceObservedCycle(
                stage_ids=tuple(stages[stage_id].id for stage_id in component),
                edges=edges,
            )
        )
    return tuple(
        sorted(cycles, key=lambda item: tuple(stage.casefold() for stage in item.stage_ids))
    )


def power_sequence_mismatches(
    sequence_map: PowerSequenceMap, observed: NetlistContract
) -> tuple[PowerSequenceMismatch, ...]:
    """Compare explicitly mapped rail and control endpoints with native netlist data."""
    mismatches = [
        PowerSequenceMismatch(
            stage_id=stage.id,
            stage_basis=stage.basis,
            enable_control=stage.enable_control,
            expected_endpoints=tuple(
                f"{role}: {endpoint.pin} on {endpoint.net}"
                for role, endpoint in (
                    ("output", stage.output),
                    ("power_good", stage.power_good),
                    ("enable", stage.enable),
                )
                if endpoint is not None
            ),
            output_pin=stage.output.pin,
            output_net=stage.output.net,
            issues=_endpoint_issues(stage, observed),
        )
        for stage in sequence_map.stages
    ]
    return tuple(item for item in mismatches if item.issues)


def power_sequence_graph_has_cycle(sequence_map: PowerSequenceMap) -> bool:
    """Return whether the project-authored required dependency graph is cyclic."""
    return _declared_graph_has_cycle(sequence_map)
