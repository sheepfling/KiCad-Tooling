"""Strict source-bound validation for native PCB footprint placements."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import PcbConnectivitySnapshot


def snapshot_data() -> dict[str, object]:
    return {
        "schema_version": "12",
        "board_sha256": "a" * 64,
        "kicad_version": "10.0.5",
        "image": "registry.example/kicad:10.0.5@sha256:" + "b" * 64,
        "probe_sha256": "c" * 64,
        "zones_refilled": True,
        "pads": (
            {
                "pad": "U1.1",
                "net": "RF_FEED",
                "footprint": "RF_Module:Module_Antenna",
                "dnp": False,
                "connected_pads": ("U1.1",),
                "connected_zones": (),
                "connected_islands": (),
                "connected_vias": (),
                "positions_nm": ((15_000_000, 22_000_000),),
            },
        ),
        "net_ties": (),
        "zones": (),
        "vias": (),
        "access_probe_observations": (),
        "access_probe_requests_sha256": None,
        "tracks": (),
        "copper_layers": ("F.Cu", "B.Cu"),
        "rule_areas": (),
        "footprints": (
            {
                "reference": "U1",
                "footprint": "RF_Module:Module_Antenna",
                "dnp": False,
                "position_nm": (12_000_000, 20_000_000),
                "orientation_microdegrees": 90_000_000,
                "side": "F.Cu",
            },
        ),
    }


def test_schema_12_binds_pad_identity_to_one_footprint_transform() -> None:
    snapshot = PcbConnectivitySnapshot.model_validate(snapshot_data())

    assert snapshot.schema_version == "12"
    assert snapshot.footprints[0].reference == "U1"
    assert snapshot.footprints[0].position_nm == (12_000_000, 20_000_000)
    assert snapshot.footprints[0].orientation_microdegrees == 90_000_000
    assert snapshot.footprints[0].side == "F.Cu"


def test_schema_12_requires_explicit_footprint_inventory() -> None:
    data = snapshot_data()
    data.pop("footprints")

    with pytest.raises(ValidationError, match="requires explicit footprint placement evidence"):
        PcbConnectivitySnapshot.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("footprint", "RF_Module:Other", "differs from its footprint placement"),
        ("dnp", True, "differs from its footprint placement"),
    ),
)
def test_pad_and_footprint_identity_must_agree(field: str, value: object, message: str) -> None:
    data = snapshot_data()
    pad = data["pads"][0]  # type: ignore[index]
    pad[field] = value

    with pytest.raises(ValidationError, match=message):
        PcbConnectivitySnapshot.model_validate(data)


def test_schema_12_rejects_duplicate_footprints_and_non_copper_side() -> None:
    data = snapshot_data()
    data["footprints"] = (*data["footprints"], {**data["footprints"][0], "reference": "u1"})  # type: ignore[index]
    with pytest.raises(ValidationError, match="duplicate footprint references"):
        PcbConnectivitySnapshot.model_validate(data)

    data = snapshot_data()
    data["footprints"] = ({**data["footprints"][0], "side": "F.Fab"},)  # type: ignore[index]
    with pytest.raises(ValidationError, match="literal_error"):
        PcbConnectivitySnapshot.model_validate(data)


@pytest.mark.parametrize("angle", (-1, 360_000_000))
def test_footprint_angle_has_canonical_microdegree_range(angle: int) -> None:
    data = snapshot_data()
    data["footprints"] = (
        {**data["footprints"][0], "orientation_microdegrees": angle},  # type: ignore[index]
    )

    with pytest.raises(ValidationError):
        PcbConnectivitySnapshot.model_validate(data)
