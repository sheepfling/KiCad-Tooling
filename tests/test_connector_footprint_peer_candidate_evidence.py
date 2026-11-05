"""Typed evidence retained by generic connector footprint-peer findings."""

from __future__ import annotations

from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinAllOpen,
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinNamedAllOpen,
    ConnectorFootprintPeerPinNamedDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScanSource,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidate_evidence import (
    ConnectorFootprintPeerPinCandidate,
    project_connector_footprint_peer_pin_evidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.evidence_lint]


def test_all_footprint_peer_scan_records_freeze_assignments() -> None:
    assignments: dict[str, tuple[str, ...]] = {"J1.2": ()}
    source = ConnectorFootprintPeerPinScanSource(
        observed=NetlistContract(components={}, nets={}),
        declared_references=(),
        peer_assignment_groups=None,
    )
    records = (
        ConnectorFootprintPeerPinDivergence(
            footprint="Synthetic:Connector_2x1",
            value="Synthetic connector",
            pin_number="2",
            pin_function="Pin_2",
            assignments=assignments,
            symbols=("Synthetic:Port",),
            common_anchor_pin_numbers=("1",),
        ),
        ConnectorFootprintPeerPinNamedDivergence(
            footprint="Synthetic:Connector_2x1",
            value="Synthetic connector",
            pin_number="2",
            pin_function="UART_RX",
            pin_electrical_type="input",
            assignments=assignments,
            symbols=("Synthetic:Port",),
            common_anchor_pin_numbers=("1",),
            source=source,
        ),
        ConnectorFootprintPeerPinOpenOutlier(
            footprint="Synthetic:Connector_2x1",
            value="Synthetic connector",
            pin_number="2",
            pin_function="Pin_2",
            pin_electrical_type="passive",
            assignments=assignments,
            open_pins=("J1.2",),
            symbols=("Synthetic:Port",),
            common_anchor_pin_numbers=("1",),
        ),
        ConnectorFootprintPeerPinAllOpen(
            footprint="Synthetic:Connector_2x1",
            value="Synthetic connector",
            pin_number="2",
            pin_function="Pin_2",
            assignments=assignments,
            symbols=("Synthetic:Port",),
            common_anchor_pin_numbers=("1",),
        ),
        ConnectorFootprintPeerPinNamedAllOpen(
            footprint="Synthetic:Connector_2x1",
            value="Synthetic connector",
            pin_number="2",
            pin_function="UART_RX",
            pin_electrical_type="input",
            assignments=assignments,
            symbols=("Synthetic:Port",),
            common_anchor_pin_numbers=("1",),
        ),
    )

    assignments["J1.2"] = ("CHANGED",)
    for record in records:
        assert record.assignments["J1.2"] == ()
        with pytest.raises(TypeError):
            cast(dict[str, tuple[str, ...]], record.assignments)["J1.2"] = ("CHANGED",)


def test_divergence_candidate_retains_frozen_source_and_existing_evidence_fields() -> None:
    assignments = {"J1.2": ("SIGNAL_A",), "J2.2": ("SIGNAL_B",)}
    source = ConnectorFootprintPeerPinDivergence(
        footprint="Synthetic:Connector_2x1",
        value="Synthetic connector",
        pin_number="2",
        pin_function="Pin_2",
        assignments=assignments,
        symbols=("Synthetic:Port", "Synthetic:PortAlias"),
        common_anchor_pin_numbers=("1",),
        peer_assignment_group="console-port",
        peer_assignment_basis=("approved-interface-map",),
    )
    assignments["J1.2"] = ("MUTATED",)
    candidate = ConnectorFootprintPeerPinCandidate.from_source_evidence(
        source,
        subject="Synthetic connector [Synthetic:Connector_2x1] pin 2",
        message="Review the approved pinout.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "connector.footprint_peer_pin_assignment_divergence"
    assert candidate.evidence == {
        "value": ("Synthetic connector",),
        "footprint": ("Synthetic:Connector_2x1",),
        "pin_number": ("2",),
        "pin_function": ("Pin_2",),
        "assignments": ("J1.2=SIGNAL_A", "J2.2=SIGNAL_B"),
        "symbols": ("Synthetic:Port", "Synthetic:PortAlias"),
        "common_anchor_pin_numbers": ("1",),
        "peer_assignment_group": ("console-port",),
        "peer_assignment_basis": ("approved-interface-map",),
    }
    with pytest.raises(TypeError):
        source.assignments["J1.2"] = ("MUTATED",)  # type: ignore[index]


@pytest.mark.parametrize(
    ("source", "rule_id", "expected_assignments", "expected_open_pins"),
    [
        (
            ConnectorFootprintPeerPinOpenOutlier(
                footprint="Synthetic:Connector_2x1",
                value="Synthetic connector",
                pin_number="2",
                pin_function="Pin_2",
                pin_electrical_type="passive",
                assignments={"J1.2": ("SIGNAL_A",), "J2.2": ()},
                open_pins=("J2.2",),
                symbols=("Synthetic:Port", "Synthetic:PortAlias"),
                common_anchor_pin_numbers=("1",),
            ),
            "connector.footprint_peer_pin_open_outlier",
            ("J1.2=SIGNAL_A", "J2.2=<unassigned>"),
            ("J2.2",),
        ),
        (
            ConnectorFootprintPeerPinAllOpen(
                footprint="Synthetic:Connector_2x1",
                value="Synthetic connector",
                pin_number="2",
                pin_function="Pin_2",
                assignments={"J1.2": (), "J2.2": ()},
                symbols=("Synthetic:Port", "Synthetic:PortAlias"),
                common_anchor_pin_numbers=("1",),
            ),
            "connector.footprint_peer_pin_all_open",
            ("J1.2=<unassigned>", "J2.2=<unassigned>"),
            ("J1.2", "J2.2"),
        ),
    ],
)
def test_open_candidates_keep_their_rule_specific_projection(
    source: ConnectorFootprintPeerPinOpenOutlier | ConnectorFootprintPeerPinAllOpen,
    rule_id: str,
    expected_assignments: tuple[str, ...],
    expected_open_pins: tuple[str, ...],
) -> None:
    projection = project_connector_footprint_peer_pin_evidence(source)

    assert projection.rule_id == rule_id
    assert projection.evidence["assignments"] == expected_assignments
    assert projection.evidence["open_pins"] == expected_open_pins
    assert projection.evidence["symbols"] == ("Synthetic:Port", "Synthetic:PortAlias")
    assert projection.evidence["common_anchor_pin_numbers"] == ("1",)


def test_projection_rejects_source_records_that_do_not_support_the_rule() -> None:
    source = ConnectorFootprintPeerPinOpenOutlier(
        footprint="Synthetic:Connector_2x1",
        value="Synthetic connector",
        pin_number="2",
        pin_function="UART_RX",
        pin_electrical_type="input",
        assignments={"J1.2": ("RX_A",), "J2.2": ()},
        open_pins=("J2.2",),
        symbols=("Synthetic:Port", "Synthetic:PortAlias"),
        common_anchor_pin_numbers=("1",),
    )

    with pytest.raises(ValueError, match="generic pin function"):
        project_connector_footprint_peer_pin_evidence(source)


def test_candidate_rejects_evidence_that_does_not_match_its_source() -> None:
    source = ConnectorFootprintPeerPinAllOpen(
        footprint="Synthetic:Connector_2x1",
        value="Synthetic connector",
        pin_number="2",
        pin_function="Pin_2",
        assignments={"J1.2": (), "J2.2": ()},
        symbols=("Synthetic:Port", "Synthetic:PortAlias"),
        common_anchor_pin_numbers=("1",),
    )

    with pytest.raises(ValueError, match="typed projection"):
        ConnectorFootprintPeerPinCandidate(
            rule_id="connector.footprint_peer_pin_all_open",
            subject="Synthetic connector pin 2",
            message="Review the approved pinout.",
            evidence={},
            source_evidence=source,
        )
