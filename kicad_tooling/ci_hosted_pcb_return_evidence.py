"""Theme-specific copper evidence checks for PCB return fixtures."""

from __future__ import annotations

from .ci_hosted_pcb_return_context import PcbReturnCaseEvidence
from .hwrepo import pcb_return_path_capture


def verify_pcb_return_via_evidence(case: PcbReturnCaseEvidence):
    """Check via identity, layer transitions, and endpoint membership."""
    if case.is_via_fixture:
        observed_via = case.snapshot.vias[0] if len(case.snapshot.vias) == 1 else None
        if (
            observed_via is None
            or observed_via.net != "RETURN"
            or (observed_via.x_nm, observed_via.y_nm) != (10000000, 5000000)
            or ((observed_via.start_layer, observed_via.end_layer) != ("F.Cu", "B.Cu"))
            or ((observed_via.diameter_nm, observed_via.drill_nm) != (800000, 300000))
            or (observed_via.kind != "through")
            or (observed_via.multiplicity != 1)
        ):
            case.failures.append(
                "Via fixture does not retain the exact stable geometry and layer transition"
            )
        elif (
            case.first is None
            or case.second is None
            or observed_via.id not in case.first.connected_vias
            or ((observed_via.id in case.second.connected_vias) != case.expected_connected)
        ):
            case.failures.append(
                "Via fixture component membership differs from its connected/open topology"
            )
        if observed_via is not None:
            front_tracks = tuple(
                item for item in case.snapshot.tracks if item.layer.casefold() == "f.cu"
            )
            back_tracks = tuple(
                item for item in case.snapshot.tracks if item.layer.casefold() == "b.cu"
            )
            front_contact_ok = any(
                item.geometry_kind == "segment"
                and item.start_pads == ("J1.1",)
                and (item.end_vias == (observed_via.id,))
                for item in front_tracks
            )
            back_contact_ok = any(
                item.geometry_kind == "segment"
                and item.start_vias == (observed_via.id,)
                and (item.end_pads == ("J2.1",))
                for item in back_tracks
            )
            if not front_contact_ok or back_contact_ok != case.expected_connected:
                case.failures.append(
                    "Native track endpoint contacts differ from the fixture's pad/via path"
                )
        if (
            case.connectivity_check is None
            or (observed_via is not None and observed_via.id not in case.connectivity_check.detail)
            or "F.Cu to B.Cu" not in case.connectivity_check.detail
            or ("no serial route inferred" not in case.connectivity_check.detail)
            or (
                not case.expected_connected
                and "J2.1: no component vias observed" not in case.connectivity_check.detail
            )
        ):
            case.failures.append(
                "Via fixture return report omits its component membership or layer transition"
            )
        if case.fixture_id == "alternate-layer-via":
            (repeated_command, repeated_snapshot) = (
                pcb_return_path_capture.capture_native_pcb_connectivity(
                    case.root, case.fixture_config, case.scratch / "receipt-repeat"
                )
            )
            if (
                repeated_command.returncode != 0
                or repeated_command.error is not None
                or (
                    not pcb_return_path_capture.native_pcb_command_matches(
                        repeated_command, case.fixture_config
                    )
                )
                or (repeated_snapshot is None)
            ):
                case.failures.append("Repeated native via probe did not produce valid evidence")
            else:
                first_membership = {
                    item.pad.casefold(): item.connected_vias for item in case.snapshot.pads
                }
                repeated_membership = {
                    item.pad.casefold(): item.connected_vias for item in repeated_snapshot.pads
                }
                case.via_identity_repeatable = (
                    case.snapshot.vias == repeated_snapshot.vias
                    and first_membership == repeated_membership
                )
                if not case.via_identity_repeatable:
                    case.failures.append(
                        "Via geometry identity or component membership changed across identical native loads"
                    )


def verify_pcb_return_plane_evidence(case: PcbReturnCaseEvidence):
    """Check filled copper planes and plane-stitch path evidence."""
    if case.fixture_id in {"unstitched-planes", "stitched-planes"}:
        zone_by_layer = {item.layer.casefold(): item for item in case.snapshot.zones}
        if len(case.snapshot.zones) != 2 or set(zone_by_layer) != {"f.cu", "b.cu"}:
            case.failures.append(
                "Plane-stitch fixture must retain exactly one front and one back copper zone"
            )
        elif any(
            zone.net != "RETURN"
            or zone.filled_island_count != 1
            or zone.unanchored_pad_island_indexes
            for zone in zone_by_layer.values()
        ):
            case.failures.append(
                "Plane-stitch fixture zones must each be one RETURN island anchored to a pad"
            )
        if case.first is None or case.second is None:
            case.failures.append("Plane-stitch fixture is missing one reviewed endpoint pad")
        else:
            first_zone_ids = {
                (item.uuid.casefold(), item.layer.casefold()) for item in case.first.connected_zones
            }
            second_zone_ids = {
                (item.uuid.casefold(), item.layer.casefold())
                for item in case.second.connected_zones
            }
            front_zone = zone_by_layer.get("f.cu")
            back_zone = zone_by_layer.get("b.cu")
            if (
                front_zone is None
                or back_zone is None
                or first_zone_ids != {(front_zone.uuid.casefold(), "f.cu")}
                or (second_zone_ids != {(back_zone.uuid.casefold(), "b.cu")})
            ):
                case.failures.append(
                    "Plane-stitch fixture endpoint pads are not assigned to their expected copper layers"
                )
        expected_via_count = 1 if case.expected_connected else 0
        if len(case.snapshot.vias) != expected_via_count:
            case.failures.append(
                "Plane-stitch fixture via count does not match its connected/open topology"
            )
        elif case.expected_connected:
            via = case.snapshot.vias[0]
            if (
                via.net != "RETURN"
                or (via.x_nm, via.y_nm) != (10000000, 5000000)
                or (via.start_layer, via.end_layer) != ("F.Cu", "B.Cu")
                or ((via.diameter_nm, via.drill_nm) != (800000, 300000))
                or (via.kind != "through")
                or (via.multiplicity != 1)
                or (case.first is None)
                or (case.second is None)
                or (via.id not in case.first.connected_vias)
                or (via.id not in case.second.connected_vias)
            ):
                case.failures.append(
                    "Plane-stitch control does not retain the exact through-via geometry in both copper components"
                )
            else:
                (repeated_command, repeated_snapshot) = (
                    pcb_return_path_capture.capture_native_pcb_connectivity(
                        case.root, case.fixture_config, case.scratch / "receipt-repeat"
                    )
                )
                if (
                    repeated_command.returncode != 0
                    or repeated_command.error is not None
                    or (
                        not pcb_return_path_capture.native_pcb_command_matches(
                            repeated_command, case.fixture_config
                        )
                    )
                    or (repeated_snapshot is None)
                    or (case.snapshot.vias != repeated_snapshot.vias)
                    or (case.snapshot.zones != repeated_snapshot.zones)
                    or (
                        tuple(
                            (
                                item.pad,
                                item.connected_pads,
                                item.connected_vias,
                                item.connected_zones,
                                item.connected_islands,
                            )
                            for item in case.snapshot.pads
                        )
                        != tuple(
                            (
                                item.pad,
                                item.connected_pads,
                                item.connected_vias,
                                item.connected_zones,
                                item.connected_islands,
                            )
                            for item in repeated_snapshot.pads
                        )
                    )
                ):
                    case.failures.append(
                        "Plane-stitch via identity or pad/zone connectivity changed across identical native loads"
                    )
                else:
                    case.via_identity_repeatable = True
        if case.connectivity_check is None or (
            case.expected_connected and "F.Cu to B.Cu" not in case.connectivity_check.detail
        ):
            case.failures.append("Plane-stitch report omits the copper transition evidence")


def verify_pcb_return_net_tie_evidence(case: PcbReturnCaseEvidence):
    """Check exact fitted/DNP net-tie topology and bond results."""
    if case.expected_tie_dnp is not None:
        observed_ties = {item.reference.casefold(): item for item in case.snapshot.net_ties}
        tie = observed_ties.get("nt1")
        if (
            tie is None
            or tie.footprint != "Synthetic:NetTie-2"
            or tie.dnp != case.expected_tie_dnp
            or (tie.pad_groups != (("NT1.1", "NT1.2"),))
        ):
            case.failures.append(
                "Native net-tie inventory differs from the fixture's exact reference, footprint, DNP state, or pad group"
            )
        if case.first is None or case.second is None:
            case.failures.append("Net-tie fixture is missing a reviewed connector pad")
        elif (
            "nt1.1" not in {pad.casefold() for pad in case.first.connected_pads}
            or "nt1.2" not in {pad.casefold() for pad in case.second.connected_pads}
            or "j2.1" in {pad.casefold() for pad in case.first.connected_pads}
            or ("j1.1" in {pad.casefold() for pad in case.second.connected_pads})
        ):
            case.failures.append(
                "Native net-tie fixture does not retain its two separate endpoint copper groups"
            )
        if case.scenario == "bond":
            case.connectivity_check = next(
                (check for check in case.checks if check.id.endswith("/connectivity")), None
            )
            if case.connectivity_check is None or (case.connectivity_check.status == "PASS") != (
                not case.expected_tie_dnp
            ):
                case.failures.append(
                    "Bonded return result does not match the native fitted/DNP net-tie state"
                )


def verify_pcb_return_isolation_evidence(case: PcbReturnCaseEvidence):
    """Check separate return-domain copper components."""
    if case.scenario == "isolation":
        by_pad = {item.pad.casefold(): item for item in case.snapshot.pads}
        isolation_pads = {
            name: by_pad.get(f"{name}.1".casefold()) for name in ("J1", "J2", "J3", "J4")
        }
        group_a = (
            isolation_pads["J1"] is not None
            and isolation_pads["J3"] is not None
            and ("j3.1" in {pad.casefold() for pad in isolation_pads["J1"].connected_pads})
            and ("j1.1" in {pad.casefold() for pad in isolation_pads["J3"].connected_pads})
        )
        group_b = (
            isolation_pads["J2"] is not None
            and isolation_pads["J4"] is not None
            and ("j4.1" in {pad.casefold() for pad in isolation_pads["J2"].connected_pads})
            and ("j2.1" in {pad.casefold() for pad in isolation_pads["J4"].connected_pads})
        )
        crosses_groups = any(
            pad is not None
            and any(
                other.casefold() in {member.casefold() for member in pad.connected_pads}
                for other in opposite
            )
            for (pad, opposite) in (
                (isolation_pads["J1"], ("J2.1", "J4.1")),
                (isolation_pads["J3"], ("J2.1", "J4.1")),
                (isolation_pads["J2"], ("J1.1", "J3.1")),
                (isolation_pads["J4"], ("J1.1", "J3.1")),
            )
        )
        if not group_a or not group_b or crosses_groups:
            case.failures.append(
                "Native isolation fixture does not retain two complete, separate same-net copper groups"
            )
        isolation_check = next(
            (
                check
                for check in case.checks
                if check.id == "pcb-return-paths/isolation/isolation-a/isolation-b"
            ),
            None,
        )
        if isolation_check is None or (isolation_check.status == "PASS") != bool(
            case.expected_isolated
        ):
            case.failures.append(
                "Native isolation result differs from the fixture's declared separation state"
            )


def verify_pcb_return_zone_island_evidence(case: PcbReturnCaseEvidence):
    """Check filled-island count and pad anchoring evidence."""
    if case.expected_islands is not None:
        if len(case.snapshot.zones) != 1:
            case.failures.append(
                f"Expected one native zone observation, found {len(case.snapshot.zones)}"
            )
        elif case.snapshot.zones[0].filled_island_count != case.expected_islands:
            case.failures.append(
                f"Native filled-island count differs from the fixture: expected {case.expected_islands}, found {case.snapshot.zones[0].filled_island_count}"
            )
        elif case.fixture_id == "zone-unanchored-island":
            zone = case.snapshot.zones[0]
            first_indexes: set[int] = set()
            second_indexes: set[int] = set()
            if case.first is not None:
                first_indexes = {
                    island.island_index
                    for island in case.first.connected_islands
                    if (island.uuid.casefold(), island.layer.casefold())
                    == (zone.uuid.casefold(), zone.layer.casefold())
                }
            if case.second is not None:
                second_indexes = {
                    island.island_index
                    for island in case.second.connected_islands
                    if (island.uuid.casefold(), island.layer.casefold())
                    == (zone.uuid.casefold(), zone.layer.casefold())
                }
            if (
                len(zone.unanchored_pad_island_indexes) != 1
                or len(first_indexes) != 1
                or first_indexes != second_indexes
                or first_indexes & set(zone.unanchored_pad_island_indexes)
            ):
                case.failures.append(
                    "Native zone fixture must retain one separate island without a pad anchor"
                )
        elif case.snapshot.zones[0].unanchored_pad_island_indexes:
            case.failures.append(
                "Native zone fixture unexpectedly has an island without a pad anchor"
            )
        if case.first is None or case.second is None:
            case.failures.append("Zone fixture is missing a reviewed connector pad")
        elif (
            len(case.first.connected_zones) != 1
            or len(case.second.connected_zones) != 1
            or case.first.connected_zones != case.second.connected_zones
        ):
            case.failures.append(
                "Zone fixture pads do not retain their shared native zone identity"
            )
        if case.expected_island_indices is not None:
            observed_indices = (
                tuple(item.island_index for item in case.first.connected_islands)
                if case.first is not None
                else (),
                tuple(item.island_index for item in case.second.connected_islands)
                if case.second is not None
                else (),
            )
            expected_indices = (
                (case.expected_island_indices[0],),
                (case.expected_island_indices[1],),
            )
            if observed_indices != expected_indices:
                case.failures.append(
                    f"Native pad-to-island mapping differs from the fixture: expected {expected_indices}, found {observed_indices}"
                )
        if case.connectivity_check is None or (
            case.snapshot.zones
            and (
                case.snapshot.zones[0].uuid not in case.connectivity_check.detail
                or f"filled islands={case.expected_islands}" not in case.connectivity_check.detail
                or (
                    case.fixture_id == "zone-unanchored-island"
                    and case.snapshot.zones
                    and (
                        f"unanchored to pad indexes={list(case.snapshot.zones[0].unanchored_pad_island_indexes)}"
                        not in case.connectivity_check.detail
                    )
                )
                or (
                    case.expected_island_indices is not None
                    and any(
                        f"connected island indexes=[{index}]" not in case.connectivity_check.detail
                        for index in case.expected_island_indices
                    )
                )
            )
        ):
            case.failures.append(
                "Native return-path finding omits the zone identity or island-count evidence"
            )
        if (
            not case.expected_connected
            and case.first is not None
            and (case.second is not None)
            and set(case.first.connected_pads) & set(case.second.connected_pads)
        ):
            case.failures.append(
                "Split-plane fixture pads unexpectedly share native copper connectivity"
            )
