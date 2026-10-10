"""Synthetic fault and valid-control coverage for PCB return-path evidence."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbReturnBondRequirement,
    PcbReturnPathsAnalysis,
    PcbTrackObservation,
    PcbViaObservation,
)
from tests.design_lint_fixtures.pcb_return_paths import (
    BOARD,
    FOOTPRINT,
    IMAGE,
    NET_TIE,
    PROBE,
    VERSION,
    checks_for,
    domain,
    endpoint,
    pad,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]


def test_v3_requires_explicit_via_evidence_while_v2_remains_readable() -> None:
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
    with pytest.raises(ValidationError, match="requires an explicit via inventory"):
        PcbConnectivitySnapshot.model_validate(snapshot_data)

    with pytest.raises(ValidationError, match="requires explicit per-pad via evidence"):
        PcbConnectivitySnapshot.model_validate({**snapshot_data, "vias": ()})

    zone_data = {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "layer": "F.Cu",
        "name": "",
        "net": "0V_PWM",
        "filled_island_count": 0,
    }
    with pytest.raises(ValidationError, match="requires explicit zone island-anchor evidence"):
        PcbConnectivitySnapshot.model_validate(
            {
                **snapshot_data,
                "pads": ({**pad_data, "connected_vias": ()},),
                "vias": (),
                "zones": (zone_data,),
            }
        )

    legacy = PcbConnectivitySnapshot.model_validate({**snapshot_data, "schema_version": "2"})
    assert legacy.schema_version == "2"
    assert legacy.vias == ()
    assert legacy.pads[0].connected_vias == ()


def test_v8_requires_exact_native_track_endpoint_contacts() -> None:
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
    assert observed.tracks[0].start_pads == ("J1.7",)
    assert observed.tracks[0].end_pads == ("J2.7",)
    assert observed.tracks[0].start_tracks == ()
    assert observed.tracks[0].end_tracks == ()

    legacy_track = PcbTrackObservation(
        uuid=track.uuid,
        net=track.net,
        layer=track.layer,
        width_nm=track.width_nm,
        start_nm=track.start_nm,
        end_nm=track.end_nm,
    )
    with pytest.raises(ValidationError, match="requires explicit track geometry"):
        PcbConnectivitySnapshot(**{**arguments, "tracks": (legacy_track,)})

    with pytest.raises(ValidationError, match="different net"):
        PcbConnectivitySnapshot(
            **{
                **arguments,
                "tracks": (track.model_copy(update={"net": "OTHER"}),),
            }
        )

    with pytest.raises(ValidationError, match="absent track"):
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
    with pytest.raises(ValidationError, match="different net"):
        PcbConnectivitySnapshot(
            **{
                **arguments,
                "tracks": (
                    track.model_copy(update={"end_tracks": (neighbor.uuid,)}),
                    neighbor,
                ),
            }
        )


def test_direct_connector_returns_pass_only_when_native_copper_connects_exact_pads() -> None:
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
    assert result["pcb-return-paths/pwm-return/connectivity"].status == "PASS"
    assert all(row.status == "PASS" for row in result.values())

    disconnected = snapshot((pad("J1.7"), pad("J2.7")))
    failed = checks_for(requirement, disconnected)
    assert failed["pcb-return-paths/pwm-return/connectivity"].status == "FAIL"


def test_connected_return_retains_stable_via_geometry_and_layer_transition() -> None:
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

    assert check.status == "PASS"
    assert via_id in check.detail
    assert "F.Cu to B.Cu" in check.detail
    assert "center=(10, 5) mm" in check.detail
    assert "no serial route inferred" in check.detail


def test_via_inventory_requires_existing_same_net_membership() -> None:
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
    with pytest.raises(ValidationError, match="via absent from the board"):
        snapshot((pad("J1.7", connected_vias=("f" * 64,)),), vias=(via,))
    with pytest.raises(ValidationError, match="different nets"):
        snapshot(
            (pad("J1.7", connected_vias=(via_id,)),),
            vias=(via.model_copy(update={"net": "OTHER"}),),
        )


def test_open_return_reports_via_only_in_first_endpoint_component() -> None:
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

    assert check.status == "FAIL"
    assert f"J1.7: via {via_id}" in check.detail
    assert "J2.7: no component vias observed" in check.detail


def test_board_pad_net_footprint_and_population_are_exact_requirements() -> None:
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
    assert result["pcb-return-paths/pwm-return/pad/J1.7"].status == "FAIL"
    assert result["pcb-return-paths/pwm-return/pad/J2.7"].status == "FAIL"


def test_declared_net_tie_bridges_separate_return_nets() -> None:
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
    assert result["pcb-return-paths/pwm-return/bond/NT1"].status == "PASS"
    assert result["pcb-return-paths/pwm-return/connectivity"].status == "PASS"

    dnp_tie = evidence.model_copy(
        update={"net_ties": (evidence.net_ties[0].model_copy(update={"dnp": True}),)}
    )
    dnp_result = checks_for(requirement, dnp_tie)
    assert dnp_result["pcb-return-paths/pwm-return/bond/NT1"].status == "FAIL"
    assert dnp_result["pcb-return-paths/pwm-return/connectivity"].status == "FAIL"


def test_separate_domains_are_allowed_but_unintended_bridge_is_reported() -> None:
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
    assert passed["pcb-return-paths/isolation/signal-return/isolated-return"].status == "PASS"

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
    assert failed["pcb-return-paths/isolation/signal-return/isolated-return"].status == "FAIL"


def test_requirements_reject_ambiguous_direct_and_bonded_topologies() -> None:
    with pytest.raises(ValidationError, match="one common net"):
        domain(endpoints=(endpoint("J1.7", "GND_A"), endpoint("J2.7", "GND_B")))
    with pytest.raises(ValidationError, match="must declare exact net-tie groups"):
        domain(topology="bonded")
