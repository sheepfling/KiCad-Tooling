"""Tests for matching mapped PCB pad endpoints to native observations."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbPadConnectivityObservation
from kicad_tooling.hwrepo.pcb_pad_review import pcb_pad_endpoint_issues

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_endpoint_issues_report_missing_pad_and_observed_mismatches() -> None:
    observed = PcbPadConnectivityObservation(
        pad="J1.1",
        net="WRONG_NET",
        footprint="Test:WrongFootprint",
        dnp=True,
        connected_pads=("J1.1",),
        connected_zones=(),
        connected_islands=(),
    )

    assert pcb_pad_endpoint_issues(
        None,
        reference="J2.1",
        expected_footprint="Test:Footprint",
        expected_net="SIGNAL",
        role="Connector signal",
    ) == ["Connector signal pad J2.1 is absent from the native PCB inventory"]
    assert pcb_pad_endpoint_issues(
        observed,
        reference="J1.1",
        expected_footprint="Test:Footprint",
        expected_net="SIGNAL",
        role="Connector signal",
    ) == [
        "Connector signal J1.1 footprint is 'Test:WrongFootprint'; expected 'Test:Footprint'",
        "Connector signal J1.1 net is 'WRONG_NET'; expected 'SIGNAL'",
        "Connector signal J1.1 is marked do-not-populate",
    ]
