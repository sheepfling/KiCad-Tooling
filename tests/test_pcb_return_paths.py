"""Synthetic fault and valid-control coverage for PCB return-path evidence."""

from __future__ import annotations

import unittest
from typing import Literal

from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbReturnBondRequirement,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_return_paths import pcb_return_path_checks

BOARD = "a" * 64
PROBE = "b" * 64
IMAGE = "registry.example/ki:10.0.5@sha256:" + "c" * 64
VERSION = "10.0.5"
FOOTPRINT = "Synthetic:DB9"
NET_TIE = "Synthetic:NetTie"


def endpoint(pad: str, net: str = "0V_PWM") -> PcbReturnEndpointRequirement:
    return PcbReturnEndpointRequirement(pad=pad, net=net, footprint=FOOTPRINT)


def domain(
    identifier: str = "pwm-return",
    *,
    topology: Literal["direct", "bonded"] = "direct",
    endpoints: tuple[PcbReturnEndpointRequirement, ...] | None = None,
    bonds: tuple[PcbReturnBondRequirement, ...] = (),
) -> PcbReturnDomainRequirement:
    return PcbReturnDomainRequirement(
        id=identifier,
        basis="Synthetic independently stated connector return requirement",
        topology=topology,
        endpoints=endpoints or (endpoint("J1.7"), endpoint("J2.7")),
        bonds=bonds,
    )


def pad(
    reference: str,
    net: str | None = "0V_PWM",
    *,
    connected: tuple[str, ...] | None = None,
    connected_zones: tuple[PcbZoneIdentity, ...] = (),
    connected_islands: tuple[PcbZoneIslandIdentity, ...] = (),
    connected_vias: tuple[str, ...] = (),
    footprint: str = FOOTPRINT,
    dnp: bool = False,
    positions_nm: tuple[tuple[int, int], ...] = (),
) -> PcbPadConnectivityObservation:
    return PcbPadConnectivityObservation(
        pad=reference,
        net=net,
        footprint=footprint,
        dnp=dnp,
        connected_pads=connected or (reference,),
        connected_zones=connected_zones,
        connected_islands=connected_islands,
        connected_vias=connected_vias,
        positions_nm=positions_nm,
    )


def snapshot(
    pads: tuple[PcbPadConnectivityObservation, ...],
    *,
    ties: tuple[PcbNetTieObservation, ...] = (),
    board_sha256: str = BOARD,
    zones_refilled: bool = True,
    zones: tuple[PcbZoneObservation, ...] = (),
    vias: tuple[PcbViaObservation, ...] = (),
) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        board_sha256=board_sha256,
        kicad_version=VERSION,
        image=IMAGE,
        probe_sha256=PROBE,
        zones_refilled=zones_refilled,
        pads=pads,
        net_ties=ties,
        zones=zones,
        vias=vias,
    )


def checks_for(
    requirement: PcbReturnPathsAnalysis,
    evidence: PcbConnectivitySnapshot,
):
    return {
        row.id: row
        for row in pcb_return_path_checks(
            requirement,
            evidence,
            board_sha256=BOARD,
            kicad_version=VERSION,
            image=IMAGE,
            probe_sha256=PROBE,
        )
    }


class PcbReturnPathTests(unittest.TestCase):
    def test_v3_requires_explicit_via_evidence_while_v2_remains_readable(self) -> None:
        pad_data = {
            "pad": "J1.7",
            "net": "0V_PWM",
            "footprint": FOOTPRINT,
            "dnp": False,
            "connected_pads": ("J1.7",),
            "connected_zones": (),
            "connected_islands": (),
        }
        snapshot_data = {
            "board_sha256": BOARD,
            "kicad_version": VERSION,
            "image": IMAGE,
            "probe_sha256": PROBE,
            "zones_refilled": True,
            "pads": (pad_data,),
            "net_ties": (),
            "zones": (),
        }
        with self.assertRaisesRegex(ValidationError, "requires an explicit via inventory"):
            PcbConnectivitySnapshot.model_validate(snapshot_data)

        with self.assertRaisesRegex(ValidationError, "requires explicit per-pad via evidence"):
            PcbConnectivitySnapshot.model_validate({**snapshot_data, "vias": ()})

        zone_data = {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "layer": "F.Cu",
            "name": "",
            "net": "0V_PWM",
            "filled_island_count": 0,
        }
        with self.assertRaisesRegex(
            ValidationError, "requires explicit zone island-anchor evidence"
        ):
            PcbConnectivitySnapshot.model_validate(
                {
                    **snapshot_data,
                    "pads": ({**pad_data, "connected_vias": ()},),
                    "vias": (),
                    "zones": (zone_data,),
                }
            )

        legacy = PcbConnectivitySnapshot.model_validate({**snapshot_data, "schema_version": "2"})
        self.assertEqual(legacy.schema_version, "2")
        self.assertEqual(legacy.vias, ())
        self.assertEqual(legacy.pads[0].connected_vias, ())

    def test_v8_requires_exact_native_track_endpoint_contacts(self) -> None:
        first = pad("J1.7", connected=("J1.7", "J2.7"), positions_nm=((0, 0),))
        second = pad("J2.7", connected=("J1.7", "J2.7"), positions_nm=((10, 0),))
        track = PcbTrackObservation(
            uuid="00000000-0000-0000-0000-000000000010",
            net="0V_PWM",
            layer="F.Cu",
            width_nm=250_000,
            start_nm=(0, 0),
            end_nm=(10, 0),
            geometry_kind="segment",
            start_pads=("J1.7",),
            end_pads=("J2.7",),
            start_vias=(),
            end_vias=(),
            start_tracks=(),
            end_tracks=(),
        )
        arguments = {
            "schema_version": "8",
            "board_sha256": BOARD,
            "kicad_version": VERSION,
            "image": IMAGE,
            "probe_sha256": PROBE,
            "zones_refilled": True,
            "pads": (first, second),
            "net_ties": (),
            "zones": (),
            "vias": (),
            "access_probe_observations": (),
            "access_probe_requests_sha256": None,
            "tracks": (track,),
            "copper_layers": ("F.Cu", "B.Cu"),
        }
        observed = PcbConnectivitySnapshot(**arguments)
        self.assertEqual(observed.tracks[0].start_pads, ("J1.7",))
        self.assertEqual(observed.tracks[0].end_pads, ("J2.7",))
        self.assertEqual(observed.tracks[0].start_tracks, ())
        self.assertEqual(observed.tracks[0].end_tracks, ())

        legacy_track = PcbTrackObservation(
            uuid=track.uuid,
            net=track.net,
            layer=track.layer,
            width_nm=track.width_nm,
            start_nm=track.start_nm,
            end_nm=track.end_nm,
        )
        with self.assertRaisesRegex(ValidationError, "requires explicit track geometry"):
            PcbConnectivitySnapshot(**{**arguments, "tracks": (legacy_track,)})

        with self.assertRaisesRegex(ValidationError, "different net"):
            PcbConnectivitySnapshot(
                **{
                    **arguments,
                    "tracks": (track.model_copy(update={"net": "OTHER"}),),
                }
            )

        with self.assertRaisesRegex(ValidationError, "absent track"):
            PcbConnectivitySnapshot(
                **{
                    **arguments,
                    "tracks": (
                        track.model_copy(
                            update={"end_tracks": ("00000000-0000-0000-0000-000000000011",)}
                        ),
                    ),
                }
            )

        neighbor = PcbTrackObservation(
            uuid="00000000-0000-0000-0000-000000000011",
            net="OTHER",
            layer="F.Cu",
            width_nm=250_000,
            start_nm=(10, 0),
            end_nm=(20, 0),
            geometry_kind="segment",
            start_pads=(),
            end_pads=(),
            start_vias=(),
            end_vias=(),
            start_tracks=(track.uuid,),
            end_tracks=(),
        )
        with self.assertRaisesRegex(ValidationError, "different net"):
            PcbConnectivitySnapshot(
                **{
                    **arguments,
                    "tracks": (
                        track.model_copy(update={"end_tracks": (neighbor.uuid,)}),
                        neighbor,
                    ),
                }
            )

    def test_direct_connector_returns_pass_only_when_native_copper_connects_exact_pads(
        self,
    ) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic direct common-return requirement",
            domains=(domain(),),
        )
        connected = snapshot(
            (
                pad("J1.7", connected=("J1.7", "J2.7")),
                pad("J2.7", connected=("J1.7", "J2.7")),
            )
        )
        result = checks_for(requirement, connected)
        self.assertEqual(result["pcb-return-paths/pwm-return/connectivity"].status, "PASS")
        self.assertTrue(all(row.status == "PASS" for row in result.values()))

        disconnected = snapshot((pad("J1.7"), pad("J2.7")))
        failed = checks_for(requirement, disconnected)
        self.assertEqual(failed["pcb-return-paths/pwm-return/connectivity"].status, "FAIL")

    def test_connected_return_retains_stable_via_geometry_and_layer_transition(self) -> None:
        via_id = "d" * 64
        transition = PcbViaObservation(
            id=via_id,
            net="0V_PWM",
            x_nm=10_000_000,
            y_nm=5_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=800_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic common-return path across two copper layers",
            domains=(domain(),),
        )
        evidence = snapshot(
            (
                pad("J1.7", connected=("J1.7", "J2.7"), connected_vias=(via_id,)),
                pad("J2.7", connected=("J1.7", "J2.7"), connected_vias=(via_id,)),
            ),
            vias=(transition,),
        )

        check = checks_for(requirement, evidence)["pcb-return-paths/pwm-return/connectivity"]

        self.assertEqual(check.status, "PASS")
        self.assertIn(via_id, check.detail)
        self.assertIn("F.Cu to B.Cu", check.detail)
        self.assertIn("center=(10, 5) mm", check.detail)
        self.assertIn("no serial route inferred", check.detail)

    def test_via_inventory_requires_existing_same_net_membership(self) -> None:
        via_id = "e" * 64
        via = PcbViaObservation(
            id=via_id,
            net="0V_PWM",
            x_nm=10,
            y_nm=20,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=800_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        with self.assertRaisesRegex(ValidationError, "via absent from the board"):
            snapshot((pad("J1.7", connected_vias=("f" * 64,)),), vias=(via,))
        with self.assertRaisesRegex(ValidationError, "different nets"):
            snapshot(
                (pad("J1.7", connected_vias=(via_id,)),),
                vias=(via.model_copy(update={"net": "OTHER"}),),
            )

    def test_open_return_reports_via_only_in_first_endpoint_component(self) -> None:
        via_id = "a" * 64
        via = PcbViaObservation(
            id=via_id,
            net="0V_PWM",
            x_nm=10_000_000,
            y_nm=5_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=800_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic open alternate-layer return fault",
            domains=(domain(),),
        )
        evidence = snapshot(
            (pad("J1.7", connected_vias=(via_id,)), pad("J2.7")),
            vias=(via,),
        )

        check = checks_for(requirement, evidence)["pcb-return-paths/pwm-return/connectivity"]

        self.assertEqual(check.status, "FAIL")
        self.assertIn(f"J1.7: via {via_id}", check.detail)
        self.assertIn("J2.7: no component vias observed", check.detail)

    def test_board_pad_net_footprint_and_population_are_exact_requirements(self) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic connector mapping",
            domains=(domain(),),
        )
        evidence = snapshot(
            (
                pad("J1.7", net="0V_PWM_1"),
                pad("J2.7", footprint="Synthetic:WrongDB9", dnp=True),
            )
        )
        result = checks_for(requirement, evidence)
        self.assertEqual(result["pcb-return-paths/pwm-return/pad/J1.7"].status, "FAIL")
        self.assertEqual(result["pcb-return-paths/pwm-return/pad/J2.7"].status, "FAIL")

    def test_declared_net_tie_bridges_separate_return_nets(self) -> None:
        bond = PcbReturnBondRequirement(
            reference="NT1",
            footprint=NET_TIE,
            pad_groups=(("NT1.1", "NT1.2"),),
        )
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic explicit return bond",
            domains=(
                domain(
                    topology="bonded",
                    endpoints=(endpoint("J1.7", "DGND_A"), endpoint("J2.7", "DGND_B")),
                    bonds=(bond,),
                ),
            ),
        )
        evidence = snapshot(
            (
                pad("J1.7", "DGND_A", connected=("J1.7", "NT1.1")),
                pad("NT1.1", "DGND_A", footprint=NET_TIE, connected=("J1.7", "NT1.1")),
                pad("J2.7", "DGND_B", connected=("J2.7", "NT1.2")),
                pad("NT1.2", "DGND_B", footprint=NET_TIE, connected=("J2.7", "NT1.2")),
            ),
            ties=(
                PcbNetTieObservation(
                    reference="NT1",
                    footprint=NET_TIE,
                    dnp=False,
                    pad_groups=(("NT1.1", "NT1.2"),),
                ),
            ),
        )
        result = checks_for(requirement, evidence)
        self.assertEqual(result["pcb-return-paths/pwm-return/bond/NT1"].status, "PASS")
        self.assertEqual(result["pcb-return-paths/pwm-return/connectivity"].status, "PASS")

        dnp_tie = evidence.model_copy(
            update={"net_ties": (evidence.net_ties[0].model_copy(update={"dnp": True}),)}
        )
        dnp_result = checks_for(requirement, dnp_tie)
        self.assertEqual(dnp_result["pcb-return-paths/pwm-return/bond/NT1"].status, "FAIL")
        self.assertEqual(dnp_result["pcb-return-paths/pwm-return/connectivity"].status, "FAIL")

    def test_separate_domains_are_allowed_but_unintended_bridge_is_reported(self) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic intentionally isolated return domains",
            domains=(
                domain(
                    "signal-return",
                    endpoints=(endpoint("J1.7", "SIGNAL_GND"), endpoint("J3.7", "SIGNAL_GND")),
                ),
                domain(
                    "isolated-return",
                    endpoints=(endpoint("J2.7", "ISOLATED_GND"), endpoint("J4.7", "ISOLATED_GND")),
                ),
            ),
        )
        isolated = snapshot(
            (
                pad("J1.7", "SIGNAL_GND", connected=("J1.7", "J3.7")),
                pad("J3.7", "SIGNAL_GND", connected=("J1.7", "J3.7")),
                pad("J2.7", "ISOLATED_GND", connected=("J2.7", "J4.7")),
                pad("J4.7", "ISOLATED_GND", connected=("J2.7", "J4.7")),
            )
        )
        passed = checks_for(requirement, isolated)
        self.assertEqual(
            passed["pcb-return-paths/isolation/signal-return/isolated-return"].status,
            "PASS",
        )

        tied = isolated.model_copy(
            update={
                "pads": (
                    pad("J1.7", "SIGNAL_GND", connected=("J1.7", "J3.7", "NT1.1")),
                    pad("J3.7", "SIGNAL_GND", connected=("J1.7", "J3.7", "NT1.1")),
                    pad(
                        "NT1.1",
                        "SIGNAL_GND",
                        footprint=NET_TIE,
                        connected=("J1.7", "J3.7", "NT1.1"),
                    ),
                    pad("J2.7", "ISOLATED_GND", connected=("J2.7", "J4.7", "NT1.2")),
                    pad("J4.7", "ISOLATED_GND", connected=("J2.7", "J4.7", "NT1.2")),
                    pad(
                        "NT1.2",
                        "ISOLATED_GND",
                        footprint=NET_TIE,
                        connected=("J2.7", "J4.7", "NT1.2"),
                    ),
                ),
                "net_ties": (
                    PcbNetTieObservation(
                        reference="NT1",
                        footprint=NET_TIE,
                        dnp=False,
                        pad_groups=(("NT1.1", "NT1.2"),),
                    ),
                ),
            }
        )
        failed = checks_for(requirement, tied)
        self.assertEqual(
            failed["pcb-return-paths/isolation/signal-return/isolated-return"].status,
            "FAIL",
        )

    def test_native_evidence_must_match_the_source_and_refill_zones(self) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic provenance check",
            domains=(domain(),),
        )
        evidence = snapshot(
            (pad("J1.7", connected=("J1.7", "J2.7")), pad("J2.7", connected=("J1.7", "J2.7"))),
            board_sha256="d" * 64,
            zones_refilled=False,
        )
        result = checks_for(requirement, evidence)
        self.assertEqual(result["pcb-return-paths/evidence/board"].status, "FAIL")
        self.assertEqual(result["pcb-return-paths/evidence/refilled-zones"].status, "FAIL")

    def test_zone_identity_and_island_count_localize_a_same_net_split_plane(self) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic plane-connected connector return requirement",
            domains=(domain(),),
        )
        identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        island_zero = PcbZoneIslandIdentity(
            uuid=identity.uuid,
            layer=identity.layer,
            island_index=0,
        )
        connected_zone = PcbZoneObservation(
            uuid=identity.uuid,
            layer=identity.layer,
            name="",
            net="0V_PWM",
            filled_island_count=1,
            unanchored_pad_island_indexes=(),
        )
        connected = snapshot(
            (
                pad(
                    "J1.7",
                    connected=("J1.7", "J2.7"),
                    connected_zones=(identity,),
                    connected_islands=(island_zero,),
                ),
                pad(
                    "J2.7",
                    connected=("J1.7", "J2.7"),
                    connected_zones=(identity,),
                    connected_islands=(island_zero,),
                ),
            ),
            zones=(connected_zone,),
        )
        connected_result = checks_for(requirement, connected)[
            "pcb-return-paths/pwm-return/connectivity"
        ]
        self.assertEqual(connected_result.status, "PASS")
        self.assertIn(identity.uuid, connected_result.detail)
        self.assertIn("filled islands=1", connected_result.detail)

        split_zone = connected_zone.model_copy(update={"filled_island_count": 2})
        island_one = PcbZoneIslandIdentity(
            uuid=identity.uuid,
            layer=identity.layer,
            island_index=1,
        )
        split = snapshot(
            (
                pad(
                    "J1.7",
                    connected_zones=(identity,),
                    connected_islands=(island_zero,),
                ),
                pad(
                    "J2.7",
                    connected_zones=(identity,),
                    connected_islands=(island_one,),
                ),
            ),
            zones=(split_zone,),
        )
        split_result = checks_for(requirement, split)["pcb-return-paths/pwm-return/connectivity"]
        self.assertEqual(split_result.status, "FAIL")
        self.assertIn(identity.uuid, split_result.detail)
        self.assertIn("filled islands=2", split_result.detail)
        self.assertIn("connected island indexes=[0]", split_result.detail)
        self.assertIn("connected island indexes=[1]", split_result.detail)

    def test_unanchored_zone_island_is_explicit_review_evidence(self) -> None:
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic connected return with an extra unanchored-to-pad copper island",
            domains=(domain(),),
        )
        identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        anchor = PcbZoneIslandIdentity(
            uuid=identity.uuid,
            layer=identity.layer,
            island_index=0,
        )
        zone = PcbZoneObservation(
            uuid=identity.uuid,
            layer=identity.layer,
            name="return plane",
            net="0V_PWM",
            filled_island_count=2,
            unanchored_pad_island_indexes=(1,),
        )
        evidence = snapshot(
            (
                pad(
                    "J1.7",
                    connected=("J1.7", "J2.7"),
                    connected_zones=(identity,),
                    connected_islands=(anchor,),
                ),
                pad(
                    "J2.7",
                    connected=("J1.7", "J2.7"),
                    connected_zones=(identity,),
                    connected_islands=(anchor,),
                ),
            ),
            zones=(zone,),
        )

        check = checks_for(requirement, evidence)["pcb-return-paths/pwm-return/connectivity"]

        self.assertEqual(check.status, "PASS")
        self.assertIn("unanchored to pad indexes=[1]", check.detail)

        inconsistent = zone.model_copy(update={"unanchored_pad_island_indexes": ()})
        with self.assertRaisesRegex(ValidationError, "do not match the pad-to-island evidence"):
            snapshot(
                evidence.pads,
                zones=(inconsistent,),
            )

    def test_pad_cannot_reference_missing_or_wrong_net_copper_zone(self) -> None:
        identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        with self.assertRaisesRegex(ValidationError, "zone absent from the board"):
            snapshot((pad("J1.7", connected_zones=(identity,)),))

        zone = PcbZoneObservation(
            uuid=identity.uuid,
            layer=identity.layer,
            name="different net plane",
            net="OTHER",
            filled_island_count=1,
            unanchored_pad_island_indexes=(),
        )
        with self.assertRaisesRegex(ValidationError, "different nets"):
            snapshot((pad("J1.7", connected_zones=(identity,)),), zones=(zone,))

    def test_connected_zone_requires_a_valid_pad_to_island_index(self) -> None:
        identity = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        zone = PcbZoneObservation(
            uuid=identity.uuid,
            layer=identity.layer,
            name="plane",
            net="0V_PWM",
            filled_island_count=1,
            unanchored_pad_island_indexes=(),
        )
        with self.assertRaisesRegex(ValidationError, "need exact filled-island evidence"):
            snapshot((pad("J1.7", connected_zones=(identity,)),), zones=(zone,))

        outside_island = PcbZoneIslandIdentity(
            uuid=identity.uuid,
            layer=identity.layer,
            island_index=1,
        )
        with self.assertRaisesRegex(ValidationError, "island index exceeds"):
            snapshot(
                (
                    pad(
                        "J1.7",
                        connected_zones=(identity,),
                        connected_islands=(outside_island,),
                    ),
                ),
                zones=(zone,),
            )

    def test_requirements_reject_ambiguous_direct_and_bonded_topologies(self) -> None:
        with self.assertRaisesRegex(ValidationError, "one common net"):
            domain(endpoints=(endpoint("J1.7", "GND_A"), endpoint("J2.7", "GND_B")))
        with self.assertRaisesRegex(ValidationError, "must declare exact net-tie groups"):
            domain(topology="bonded")


if __name__ == "__main__":
    unittest.main()
