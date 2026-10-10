"""Deterministic review of project-mapped PCB decoupling pins and placement."""

from __future__ import annotations

from math import isqrt

from .models import (
    PcbConnectivitySnapshot,
    PcbDecouplingMap,
    PcbPadConnectivityObservation,
    PcbViaObservation,
)
from .pcb_decoupling_models import (
    PcbDecouplingCandidateObservation,
    PcbDecouplingCoverageEntry,
)


class _PadUnion:
    """Connectivity groups derived from native pad-to-pad observations."""

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


def _nearest_centers(
    first: PcbPadConnectivityObservation | None,
    second: PcbPadConnectivityObservation | None,
) -> int | None:
    if first is None or second is None or not first.positions_nm or not second.positions_nm:
        return None
    return min(
        (
            (x1 - x2) ** 2 + (y1 - y2) ** 2,
            x1,
            y1,
            x2,
            y2,
        )
        for x1, y1 in first.positions_nm
        for x2, y2 in second.positions_nm
    )[0]


def _nearest_connected_via(
    pad: PcbPadConnectivityObservation | None,
    vias: dict[str, PcbViaObservation],
) -> tuple[int, str | None, int | None]:
    if pad is None:
        return 0, None, None
    if not pad.positions_nm:
        return len(pad.connected_vias), None, None
    measurements = [
        (
            min((x - via.x_nm) ** 2 + (y - via.y_nm) ** 2 for x, y in pad.positions_nm),
            via_id,
        )
        for via_id in pad.connected_vias
        if (via := vias.get(via_id)) is not None
    ]
    if not measurements:
        return len(pad.connected_vias), None, None
    distance_squared, via_id = min(measurements)
    return len(pad.connected_vias), via_id, distance_squared


def _endpoint_issues(
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


def pcb_decoupling_entries(
    spec: PcbDecouplingMap, snapshot: PcbConnectivitySnapshot
) -> tuple[PcbDecouplingCoverageEntry, ...]:
    """Compare exact project pin mappings with native net, copper, DNP, and geometry data."""
    pads = {item.pad.casefold(): item for item in snapshot.pads}
    vias = {item.id: item for item in snapshot.vias}
    connected = _PadUnion(snapshot.pads)
    results: list[PcbDecouplingCoverageEntry] = []
    for requirement in spec.requirements:
        ic_supply = pads.get(requirement.supply_pad.casefold())
        ic_return = pads.get(requirement.return_pad.casefold())
        common_issues = _endpoint_issues(
            ic_supply,
            reference=requirement.supply_pad,
            expected_footprint=requirement.ic_footprint,
            expected_net=requirement.supply_net,
            role="IC supply",
        )
        common_issues.extend(
            _endpoint_issues(
                ic_return,
                reference=requirement.return_pad,
                expected_footprint=requirement.ic_footprint,
                expected_net=requirement.return_net,
                role="IC return",
            )
        )
        observations: list[PcbDecouplingCandidateObservation] = []
        eligible_distances: list[tuple[int, str]] = []
        threshold_nm = (
            None if requirement.max_distance_um is None else requirement.max_distance_um * 1000
        )
        return_via_threshold_nm = (
            None
            if requirement.max_return_via_distance_um is None
            else requirement.max_return_via_distance_um * 1000
        )
        for candidate in requirement.capacitors:
            cap_supply = pads.get(candidate.supply_pad.casefold())
            cap_return = pads.get(candidate.return_pad.casefold())
            issues: list[str] = []
            supply_pad_issues = _endpoint_issues(
                cap_supply,
                reference=candidate.supply_pad,
                expected_footprint=candidate.footprint,
                expected_net=requirement.supply_net,
                role="Capacitor supply",
            )
            return_pad_issues = _endpoint_issues(
                cap_return,
                reference=candidate.return_pad,
                expected_footprint=candidate.footprint,
                expected_net=requirement.return_net,
                role="Capacitor return",
            )
            issues.extend(supply_pad_issues)
            issues.extend(return_pad_issues)
            if ic_supply is None or cap_supply is None:
                supply_connected = False
            else:
                supply_connected = connected.find(ic_supply.pad) == connected.find(cap_supply.pad)
            if ic_return is None or cap_return is None:
                return_connected = False
            else:
                return_connected = connected.find(ic_return.pad) == connected.find(cap_return.pad)
            if not supply_connected:
                issues.append(
                    f"Supply path {requirement.supply_pad} to {candidate.supply_pad} is not connected"
                )
            if not return_connected:
                issues.append(
                    f"Return path {requirement.return_pad} to {candidate.return_pad} is not connected"
                )
            measured = _nearest_centers(ic_supply, cap_supply)
            distance_squared = measured
            distance_nm = None if distance_squared is None else isqrt(distance_squared)
            connected_via_count, nearest_via_id, return_via_distance_squared = (
                _nearest_connected_via(cap_return, vias)
            )
            return_via_distance_nm = (
                None if return_via_distance_squared is None else isqrt(return_via_distance_squared)
            )
            if return_via_threshold_nm is not None:
                return_via_evidence_available = (
                    snapshot.schema_version.isdecimal()
                    and int(snapshot.schema_version) >= 3
                    and cap_return is not None
                    and "connected_vias" in cap_return.model_fields_set
                )
                if not return_via_evidence_available:
                    issues.append(
                        f"Native connected-via evidence for {candidate.return_pad} is unavailable "
                        f"in PCB snapshot schema {snapshot.schema_version}"
                    )
                elif connected_via_count == 0:
                    issues.append(f"Return pad {candidate.return_pad} has no native-connected via")
                elif return_via_distance_squared is None:
                    issues.append(
                        f"Return-via distance for {candidate.return_pad} cannot be measured from native pad geometry"
                    )
                elif return_via_distance_squared > return_via_threshold_nm**2:
                    assert return_via_distance_nm is not None
                    issues.append(
                        f"Nearest native-connected return via for {candidate.return_pad} is "
                        f"{return_via_distance_nm // 1000}.{return_via_distance_nm % 1000:03d} um "
                        f"away; the project limit is {requirement.max_return_via_distance_um} um"
                    )
            identity_matches = (
                cap_supply is not None
                and cap_return is not None
                and cap_supply.footprint == candidate.footprint
                and cap_return.footprint == candidate.footprint
            )
            fitted = (
                cap_supply is not None
                and cap_return is not None
                and not cap_supply.dnp
                and not cap_return.dnp
            )
            electrically_mapped = (
                not common_issues
                and not supply_pad_issues
                and not return_pad_issues
                and supply_connected
                and return_connected
            )
            geometrically_mapped = distance_squared is not None
            eligible = electrically_mapped and geometrically_mapped
            if eligible:
                assert distance_squared is not None
                eligible_distances.append((distance_squared, candidate.reference))
            observations.append(
                PcbDecouplingCandidateObservation(
                    reference=candidate.reference,
                    expected_footprint=candidate.footprint,
                    observed_footprint=(
                        cap_supply.footprint
                        if cap_supply is not None
                        and cap_return is not None
                        and cap_supply.footprint == cap_return.footprint
                        else None
                    ),
                    supply_pad=candidate.supply_pad,
                    return_pad=candidate.return_pad,
                    observed_supply_net=None if cap_supply is None else cap_supply.net,
                    observed_return_net=None if cap_return is None else cap_return.net,
                    fitted=fitted,
                    identity_matches=identity_matches,
                    supply_connected=supply_connected,
                    return_connected=return_connected,
                    distance_nm=distance_nm,
                    distance_squared_nm2=distance_squared,
                    connected_return_via_count=connected_via_count,
                    nearest_return_via_id=nearest_via_id,
                    return_via_distance_nm=return_via_distance_nm,
                    return_via_distance_squared_nm2=return_via_distance_squared,
                    eligible=eligible,
                    issues=tuple(issues),
                )
            )

        acceptable: dict[str, bool] = {}
        for candidate in observations:
            within_supply_distance = threshold_nm is None or (
                candidate.distance_squared_nm2 is not None
                and candidate.distance_squared_nm2 <= threshold_nm**2
            )
            within_return_via_distance = return_via_threshold_nm is None or (
                candidate.return_via_distance_squared_nm2 is not None
                and candidate.return_via_distance_squared_nm2 <= return_via_threshold_nm**2
            )
            acceptable[candidate.reference.casefold()] = (
                candidate.eligible and within_supply_distance and within_return_via_distance
            )
        eligible_within_limit = [
            (distance_squared, reference)
            for distance_squared, reference in eligible_distances
            if acceptable[reference.casefold()]
        ]
        if requirement.selection == "any":
            selected = (min(eligible_within_limit)[1],) if eligible_within_limit else ()
        else:
            selected = tuple(
                candidate.reference
                for candidate in observations
                if acceptable[candidate.reference.casefold()]
            )
        if requirement.selection == "any":
            capacitors_satisfied = bool(selected)
        else:
            capacitors_satisfied = len(selected) == len(requirement.capacitors)
        issues = list(common_issues)
        if not capacitors_satisfied:
            if not eligible_distances:
                issues.append("No mapped capacitor has matching fitted pads and both copper paths")
            elif threshold_nm is not None and not any(
                candidate.eligible
                and candidate.distance_squared_nm2 is not None
                and candidate.distance_squared_nm2 <= threshold_nm**2
                for candidate in observations
            ):
                issues.append(
                    f"No acceptable capacitor selection meets the {requirement.max_distance_um} um center-distance limit"
                )
            elif return_via_threshold_nm is not None and not any(
                candidate.eligible
                and (
                    threshold_nm is None
                    or (
                        candidate.distance_squared_nm2 is not None
                        and candidate.distance_squared_nm2 <= threshold_nm**2
                    )
                )
                and candidate.return_via_distance_squared_nm2 is not None
                and candidate.return_via_distance_squared_nm2 <= return_via_threshold_nm**2
                for candidate in observations
            ):
                issues.append(
                    "No acceptable capacitor selection has a native-connected return via "
                    f"within {requirement.max_return_via_distance_um} um"
                )
            else:
                issues.append("The required capacitor selection is incomplete")
        if threshold_nm is None:
            issues.append(
                "No project IC-to-cap distance threshold is configured; measured placement needs review"
            )
        entry_status = "COMPLETE" if capacitors_satisfied and not common_issues else "INCOMPLETE"
        results.append(
            PcbDecouplingCoverageEntry(
                id=requirement.id,
                status=entry_status,
                ic_supply_pad=requirement.supply_pad,
                ic_return_pad=requirement.return_pad,
                ic_supply_net=requirement.supply_net,
                ic_return_net=requirement.return_net,
                max_distance_um=requirement.max_distance_um,
                max_return_via_distance_um=requirement.max_return_via_distance_um,
                selection=requirement.selection,
                candidates=tuple(observations),
                selected_capacitors=tuple(selected),
                issues=tuple(issues),
            )
        )
    return tuple(results)
