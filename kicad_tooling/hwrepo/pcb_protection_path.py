"""Deterministic, project-mapped PCB screens for external protection paths."""

from __future__ import annotations

from math import isqrt

from .models import (
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbProtectionPathEntry,
    PcbProtectionPathMap,
)


class _PadUnion:
    """Connectivity groups derived only from native pad-component observations."""

    def __init__(self, pads: tuple[PcbPadConnectivityObservation, ...]) -> None:
        self.parent = {item.pad.casefold(): item.pad.casefold() for item in pads}
        for item in pads:
            for other in item.connected_pads:
                self.join(item.pad, other)

    def find(self, pad: str) -> str:
        key = pad.casefold()
        if key not in self.parent:
            return ""
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, first: str, second: str) -> None:
        a = first.casefold()
        b = second.casefold()
        if a not in self.parent or b not in self.parent:
            return
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def _nearest_distance_squared(
    first: PcbPadConnectivityObservation | None,
    second: PcbPadConnectivityObservation | None,
) -> int | None:
    if first is None or second is None or not first.positions_nm or not second.positions_nm:
        return None
    return min(
        (x1 - x2) ** 2 + (y1 - y2) ** 2
        for x1, y1 in first.positions_nm
        for x2, y2 in second.positions_nm
    )


def _pad_issues(
    pad: PcbPadConnectivityObservation | None,
    *,
    reference: str,
    expected_footprint: str,
    expected_net: str,
    role: str,
) -> list[str]:
    if pad is None:
        return [f"{role} pad {reference} is absent from the native PCB inventory"]
    issues: list[str] = []
    if pad.footprint != expected_footprint:
        issues.append(
            f"{role} {reference} footprint is {pad.footprint!r}; expected {expected_footprint!r}"
        )
    if pad.net != expected_net:
        issues.append(f"{role} {reference} net is {pad.net!r}; expected {expected_net!r}")
    if pad.dnp:
        issues.append(f"{role} {reference} is marked do-not-populate")
    return issues


def pcb_protection_path_entries(
    spec: PcbProtectionPathMap,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbProtectionPathEntry, ...]:
    """Compare authored pad mappings with native net, copper, via, and geometry data."""
    pads = {item.pad.casefold(): item for item in snapshot.pads}
    vias = {item.id: item for item in snapshot.vias}
    connected = _PadUnion(snapshot.pads)
    entries: list[PcbProtectionPathEntry] = []
    for requirement in spec.requirements:
        connector_pad = pads.get(requirement.connector_signal_pad.casefold())
        protection_signal_pad = pads.get(requirement.protection_signal_pad.casefold())
        protection_reference_pad = pads.get(requirement.protection_reference_pad.casefold())
        issues = _pad_issues(
            connector_pad,
            reference=requirement.connector_signal_pad,
            expected_footprint=requirement.connector_footprint,
            expected_net=requirement.signal_net,
            role="Connector signal",
        )
        issues.extend(
            _pad_issues(
                protection_signal_pad,
                reference=requirement.protection_signal_pad,
                expected_footprint=requirement.protection_footprint,
                expected_net=requirement.signal_net,
                role="Protection signal",
            )
        )
        issues.extend(
            _pad_issues(
                protection_reference_pad,
                reference=requirement.protection_reference_pad,
                expected_footprint=requirement.protection_footprint,
                expected_net=requirement.reference_net,
                role="Protection reference",
            )
        )
        connected_to_entry = (
            connector_pad is not None
            and protection_signal_pad is not None
            and connected.find(connector_pad.pad) == connected.find(protection_signal_pad.pad)
        )
        if not connected_to_entry:
            issues.append(
                f"Native copper path from {requirement.connector_signal_pad} to "
                f"{requirement.protection_signal_pad} is not connected"
            )

        entry_distance_squared = _nearest_distance_squared(connector_pad, protection_signal_pad)
        if requirement.max_entry_distance_um is not None:
            if entry_distance_squared is None:
                issues.append("Native connector-to-protection pad geometry is unavailable")
            elif entry_distance_squared > (requirement.max_entry_distance_um * 1000) ** 2:
                measured_nm = isqrt(entry_distance_squared)
                issues.append(
                    f"Connector-to-protection pad distance is {measured_nm} nm; "
                    f"the project limit is {requirement.max_entry_distance_um} um"
                )

        connected_via_count = (
            0 if protection_reference_pad is None else len(protection_reference_pad.connected_vias)
        )
        nearest_via_id: str | None = None
        nearest_via_distance_squared: int | None = None
        vias_within_radius: int | None = None
        via_radius_um = requirement.reference_via_radius_um
        if requirement.minimum_reference_vias is not None:
            via_evidence_available = (
                snapshot.schema_version.isdecimal()
                and int(snapshot.schema_version) >= 3
                and protection_reference_pad is not None
                and "connected_vias" in protection_reference_pad.model_fields_set
            )
            if not via_evidence_available:
                issues.append(
                    "Native connected-via evidence for "
                    f"{requirement.protection_reference_pad} is unavailable in PCB snapshot "
                    f"schema {snapshot.schema_version}"
                )
            elif protection_reference_pad is None or not protection_reference_pad.connected_vias:
                vias_within_radius = 0
                issues.append(
                    f"Protection reference pad {requirement.protection_reference_pad} has no "
                    "native-connected via"
                )
            elif not protection_reference_pad.positions_nm:
                issues.append(
                    "Native pad geometry is unavailable for connected-via distance at "
                    f"{requirement.protection_reference_pad}"
                )
            else:
                measurements = [
                    (
                        min(
                            (x - via.x_nm) ** 2 + (y - via.y_nm) ** 2
                            for x, y in protection_reference_pad.positions_nm
                        ),
                        via_id,
                    )
                    for via_id in protection_reference_pad.connected_vias
                    if (via := vias.get(via_id)) is not None
                ]
                if measurements:
                    nearest_via_distance_squared, nearest_via_id = min(
                        measurements, key=lambda item: (item[0], item[1])
                    )
                    assert via_radius_um is not None
                    radius_squared = (via_radius_um * 1000) ** 2
                    vias_within_radius = sum(
                        distance_squared <= radius_squared for distance_squared, _ in measurements
                    )
                    if vias_within_radius < requirement.minimum_reference_vias:
                        issues.append(
                            f"Protection reference pad {requirement.protection_reference_pad} "
                            f"has {vias_within_radius} native-connected via(s) within "
                            f"{via_radius_um} um; the project minimum is "
                            f"{requirement.minimum_reference_vias}"
                        )
                else:
                    vias_within_radius = 0
                    issues.append(
                        "Native connected-via identities for "
                        f"{requirement.protection_reference_pad} are absent from the snapshot"
                    )

        entries.append(
            PcbProtectionPathEntry(
                id=requirement.id,
                status="INCOMPLETE" if issues else "COMPLETE",
                connector_signal_pad=requirement.connector_signal_pad,
                protection_signal_pad=requirement.protection_signal_pad,
                protection_reference_pad=requirement.protection_reference_pad,
                signal_net=requirement.signal_net,
                reference_net=requirement.reference_net,
                expected_connector_footprint=requirement.connector_footprint,
                observed_connector_footprint=(
                    None if connector_pad is None else connector_pad.footprint
                ),
                expected_protection_footprint=requirement.protection_footprint,
                observed_protection_signal_footprint=(
                    None if protection_signal_pad is None else protection_signal_pad.footprint
                ),
                observed_protection_reference_footprint=(
                    None if protection_reference_pad is None else protection_reference_pad.footprint
                ),
                observed_connector_signal_net=(
                    None if connector_pad is None else connector_pad.net
                ),
                observed_protection_signal_net=(
                    None if protection_signal_pad is None else protection_signal_pad.net
                ),
                observed_protection_reference_net=(
                    None if protection_reference_pad is None else protection_reference_pad.net
                ),
                connector_signal_fitted=None if connector_pad is None else not connector_pad.dnp,
                protection_signal_fitted=(
                    None if protection_signal_pad is None else not protection_signal_pad.dnp
                ),
                protection_reference_fitted=(
                    None if protection_reference_pad is None else not protection_reference_pad.dnp
                ),
                native_signal_path_connected=connected_to_entry,
                connector_to_protection_distance_nm=(
                    None if entry_distance_squared is None else isqrt(entry_distance_squared)
                ),
                connector_to_protection_distance_squared_nm2=entry_distance_squared,
                connected_reference_via_count=connected_via_count,
                reference_vias_within_radius=vias_within_radius,
                reference_via_radius_um=via_radius_um,
                nearest_reference_via_id=nearest_via_id,
                nearest_reference_via_distance_nm=(
                    None
                    if nearest_via_distance_squared is None
                    else isqrt(nearest_via_distance_squared)
                ),
                max_entry_distance_um=requirement.max_entry_distance_um,
                minimum_reference_vias=requirement.minimum_reference_vias,
                issues=tuple(issues),
            )
        )
    return tuple(entries)
