"""Capture and compare normalized connectivity from native KiCad netlists."""

from __future__ import annotations

from collections.abc import Mapping

from .design_lint_connectivity_snapshot_models import (
    DesignLintConnectivityChange,
    DesignLintConnectivitySnapshot,
    NetlistPinConnectivityState,
)
from .model_primitives import Digest, Identifier, RepositoryPath
from .models import NetlistContract


def capture_connectivity_snapshot(
    project_id: Identifier,
    observed: NetlistContract,
    source_hashes: Mapping[RepositoryPath, Digest],
    netlist_sha256: Digest,
    kicad_version: str,
    toolchain_image: str,
) -> DesignLintConnectivitySnapshot:
    """Capture per-pin net names and peer membership from one native netlist."""
    net_members: dict[str, set[str]] = {}
    pin_nets: dict[str, str] = {}
    conflicts: set[str] = set()

    for net_name, members in observed.nets.items():
        unique_members = set(members)
        net_members[net_name] = unique_members
        for pin in unique_members:
            previous = pin_nets.setdefault(pin, net_name)
            if previous != net_name:
                conflicts.add(pin)

    unconnected_pins: set[str] = set()
    for members in observed.unconnected_nets.values():
        unconnected_pins.update(members)

    conflicts.update(pin for pin in unconnected_pins if pin in pin_nets)
    component_refs = set(observed.components)
    inventory_refs = set(observed.component_pin_numbers)
    known_pins = {
        f"{reference}.{number}"
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    observed_pins = set(pin_nets) | unconnected_pins
    missing_inventories = component_refs - inventory_refs
    unexpected_inventories = inventory_refs - component_refs
    pins_outside_inventory = observed_pins - known_pins
    coverage_issues: list[str] = []
    if missing_inventories:
        coverage_issues.append("native pin inventory is missing for one or more components")
    if unexpected_inventories:
        coverage_issues.append("native pin inventory contains an unknown component")
    if pins_outside_inventory:
        coverage_issues.append("native connectivity includes pins outside the declared inventories")
    if not known_pins:
        coverage_issues.append("native pin inventories contain no pins")
    if conflicts:
        coverage_issues.append("native netlist assigns one or more pins ambiguously")

    if conflicts:
        pin_states: dict[str, NetlistPinConnectivityState] = {}
    else:
        all_pins = known_pins | observed_pins
        pin_states = {}
        for pin in sorted(all_pins):
            net_name = pin_nets.get(pin)
            peers = tuple(sorted(net_members[net_name] - {pin})) if net_name is not None else ()
            pin_states[pin] = NetlistPinConnectivityState(net=net_name, peers=peers)

    return DesignLintConnectivitySnapshot(
        project_id=project_id,
        source_hashes=dict(sorted(source_hashes.items())),
        netlist_sha256=netlist_sha256,
        kicad_version=kicad_version,
        toolchain_image=toolchain_image,
        coverage="PARTIAL" if coverage_issues else "COMPLETE",
        pin_states=pin_states,
        issue="; ".join(coverage_issues) if coverage_issues else None,
    )


def compare_connectivity_snapshots(
    baseline: DesignLintConnectivitySnapshot,
    current: DesignLintConnectivitySnapshot,
) -> tuple[DesignLintConnectivityChange, ...]:
    """Return stable pin-level differences; a shared net rename remains visible."""
    changes: list[DesignLintConnectivityChange] = []
    for pin in sorted(baseline.pin_states.keys() | current.pin_states.keys()):
        before = baseline.pin_states.get(pin)
        after = current.pin_states.get(pin)
        if before is None:
            if baseline.coverage != "COMPLETE":
                continue
            kind = "PIN_ADDED"
        elif after is None:
            if current.coverage != "COMPLETE":
                continue
            kind = "PIN_REMOVED"
        elif before != after:
            kind = "ASSIGNMENT_CHANGED"
        else:
            continue
        changes.append(
            DesignLintConnectivityChange(
                pin=pin,
                kind=kind,
                baseline=before,
                current=after,
            )
        )
    return tuple(changes)
