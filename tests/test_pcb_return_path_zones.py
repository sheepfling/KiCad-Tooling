"""Synthetic source-bound copper-zone return evidence checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    PcbReturnPathsAnalysis,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from tests.design_lint_fixtures.pcb_return_paths import (
    checks_for,
    domain,
    pad,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]


def test_native_evidence_must_match_the_source_and_refill_zones() -> None:
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
    assert result["pcb-return-paths/evidence/board"].status == "FAIL"
    assert result["pcb-return-paths/evidence/refilled-zones"].status == "FAIL"


def test_zone_identity_and_island_count_localize_a_same_net_split_plane() -> None:
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
    assert connected_result.status == "PASS"
    assert identity.uuid in connected_result.detail
    assert "filled islands=1" in connected_result.detail

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
    assert split_result.status == "FAIL"
    assert identity.uuid in split_result.detail
    assert "filled islands=2" in split_result.detail
    assert "connected island indexes=[0]" in split_result.detail
    assert "connected island indexes=[1]" in split_result.detail


def test_unanchored_zone_island_is_explicit_review_evidence() -> None:
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

    assert check.status == "PASS"
    assert "unanchored to pad indexes=[1]" in check.detail

    inconsistent = zone.model_copy(update={"unanchored_pad_island_indexes": ()})
    with pytest.raises(ValidationError, match="do not match the pad-to-island evidence"):
        snapshot(
            evidence.pads,
            zones=(inconsistent,),
        )


def test_pad_cannot_reference_missing_or_wrong_net_copper_zone() -> None:
    identity = PcbZoneIdentity(
        uuid="00000000-0000-0000-0000-000000000001",
        layer="F.Cu",
    )
    with pytest.raises(ValidationError, match="zone absent from the board"):
        snapshot((pad("J1.7", connected_zones=(identity,)),))

    zone = PcbZoneObservation(
        uuid=identity.uuid,
        layer=identity.layer,
        name="different net plane",
        net="OTHER",
        filled_island_count=1,
        unanchored_pad_island_indexes=(),
    )
    with pytest.raises(ValidationError, match="different nets"):
        snapshot((pad("J1.7", connected_zones=(identity,)),), zones=(zone,))


def test_connected_zone_requires_a_valid_pad_to_island_index() -> None:
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
    with pytest.raises(ValidationError, match="need exact filled-island evidence"):
        snapshot((pad("J1.7", connected_zones=(identity,)),), zones=(zone,))

    outside_island = PcbZoneIslandIdentity(
        uuid=identity.uuid,
        layer=identity.layer,
        island_index=1,
    )
    with pytest.raises(ValidationError, match="island index exceeds"):
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
