"""Project-authored board-edge probe clearance behavior."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.pcb_connectivity_edges import PcbEdgeCutObservation
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.test_access import (
    pcb_access_probe_request_set,
    pcb_probe_envelope_checks,
)
from tests.pcb_test_access_support import probe_access_requirement, probe_access_snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    ((475_000, "PASS"), (474_999, "FAIL")),
)
def test_authored_edge_clearance_uses_inclusive_nanometer_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        board_edge_clearance_mm=0.075,
    )
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="21",
        edge_obstacle_uuid="00000000-0000-0000-0000-000000000058",
        edge_obstacle_distance_nm=distance_nm,
        include_edge_inventory=True,
    )

    result = pcb_probe_envelope_checks(requirement, snapshot)[0]

    assert result.status == expected_status
    assert "native Edge.Cuts item" in result.detail


def test_board_edge_requirement_requests_source_bound_edge_inventory() -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        board_edge_clearance_mm=0.075,
    )

    request_set = pcb_access_probe_request_set(requirement)

    assert request_set is not None
    assert len(request_set.requests) == 1
    assert request_set.requests[0].include_edge_cuts is True


@pytest.mark.parametrize(
    "schema_version",
    ("20", "21", "22"),
)
def test_missing_board_edge_evidence_is_not_run(schema_version: Literal["20", "21", "22"]) -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        board_edge_clearance_mm=0.075,
    )
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version=schema_version,
    )

    result = pcb_probe_envelope_checks(requirement, snapshot)[0]

    assert result.id == "test-access/pcb-probe-envelope/edge-evidence"
    assert result.status == "NOT_RUN"


def test_edge_observation_must_match_retained_inventory() -> None:
    with pytest.raises(ValueError, match="unobserved Edge.Cuts item"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="21",
            edge_obstacle_uuid="00000000-0000-0000-0000-000000000058",
            edge_obstacle_distance_nm=475_000,
        )


def test_schema_21_requires_an_explicit_edge_inventory_field() -> None:
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="21",
    )
    data = snapshot.model_dump()
    del data["edge_cuts"]

    with pytest.raises(ValidationError, match="requires explicit Edge.Cuts inventory"):
        PcbConnectivitySnapshot.model_validate(data)


def test_exposed_probe_surface_cannot_omit_nearest_edge_measurement() -> None:
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="21",
    )
    data = snapshot.model_dump()
    data["edge_cuts"] = (
        PcbEdgeCutObservation(
            uuid="00000000-0000-0000-0000-000000000058",
            width_nm=50_000,
        ).model_dump(),
    )

    with pytest.raises(ValidationError, match="omits its nearest Edge.Cuts measurement"):
        PcbConnectivitySnapshot.model_validate(data)


def test_legacy_schema_snapshot_round_trips_with_empty_edge_default() -> None:
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="20",
    )

    reloaded = PcbConnectivitySnapshot.model_validate_json(snapshot.model_dump_json())

    assert reloaded.schema_version == "20"
    assert reloaded.edge_cuts == ()
