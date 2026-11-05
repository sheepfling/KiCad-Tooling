"""Typed source and report projections for connector peer-pin findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_peer_candidate_evidence import (
    ConnectorPeerPinAssignmentCandidate,
    RepeatedConnectorPinCandidate,
    RepeatedConnectorPinFindingEvidence,
    project_connector_peer_pin_assignment_evidence,
    project_repeated_connector_pin_evidence,
)
from kicad_tooling.hwrepo.connector_peer_pin_models import SimilarConnectorPinGroup
from kicad_tooling.hwrepo.connector_peer_pin_scan import (
    ConnectorPeerPinAssignmentDivergence,
    ConnectorPeerPinAssignmentOutlier,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.evidence_lint]


def test_repeated_pin_candidate_retains_scan_and_reviewed_role_context() -> None:
    group = SimilarConnectorPinGroup(
        symbol="Synthetic:TwoPort",
        function="VDD",
        pins={"J1.1": ("+5V",), "J2.1": ("VDD_AUX",)},
        reviewed_role="supply",
        reviewed_voltage_domain="SYSTEM",
        supply_comparison_group="main_rails",
        supply_comparison_basis=("Project-reviewed supply comparison",),
    )
    observed = NetlistContract(
        components={},
        nets={},
        pin_functions={"J1.1": "VDD", "J2.1": "VDD"},
    )
    source = RepeatedConnectorPinFindingEvidence(
        group=group,
        observed=observed,
        reviewed_connector_pins={},
    )

    candidate = RepeatedConnectorPinCandidate.from_source_evidence(
        source,
        subject="Synthetic:TwoPort: VDD",
        message="Review the intended supply topology.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "connector.repeated_pin_function"
    assert candidate.evidence == {
        "J1.1": ("+5V",),
        "J2.1": ("VDD_AUX",),
        "supply_comparison_group": ("main_rails",),
        "supply_comparison_basis": ("Project-reviewed supply comparison",),
        "role_classification_sources": (
            (
                "J1.1: project interface catalog role=supply; voltage_domain=SYSTEM; "
                "native symbol function=VDD"
            ),
            (
                "J2.1: project interface catalog role=supply; voltage_domain=SYSTEM; "
                "native symbol function=VDD"
            ),
        ),
        "reviewed_voltage_domain": ("SYSTEM",),
    }
    with pytest.raises(TypeError):
        source.pin_assignments["J1.1"] = ("CHANGED",)  # type: ignore[index]
    assert project_repeated_connector_pin_evidence(source).evidence == candidate.evidence


def test_repeated_pin_candidate_explains_compound_supply_category_match() -> None:
    group = SimilarConnectorPinGroup(
        symbol="multiple connector symbols",
        function="USB_VBUS",
        pins={"J1.1": ("USB_SUPPLY",), "J2.1": ("SERIAL_SUPPLY",)},
    )
    observed = NetlistContract(
        components={},
        nets={"USB_SUPPLY": ("J1.1",), "SERIAL_SUPPLY": ("J2.1",)},
        pin_functions={"J1.1": "USB_VBUS", "J2.1": "SERIAL_VBUS"},
    )
    source = RepeatedConnectorPinFindingEvidence(
        group=group,
        observed=observed,
        reviewed_connector_pins={},
    )

    candidate = RepeatedConnectorPinCandidate.from_source_evidence(
        source,
        subject="multiple connector symbols: USB_VBUS",
        message="Review the intended supply topology.",
    )

    assert candidate.evidence["normalized_supply_category"] == ("vbus",)
    assert candidate.evidence["normalized_supply_category_sources"] == (
        "J1.1: native symbol function=USB_VBUS; normalized supply category=vbus",
        "J2.1: native symbol function=SERIAL_VBUS; normalized supply category=vbus",
    )


def test_peer_outlier_candidate_retains_immutable_part_identity_and_scope() -> None:
    assignments = {"J1.1": ("NET_A",), "J2.1": (), "J3.1": ("NET_A",)}
    source = ConnectorPeerPinAssignmentOutlier(
        symbol="multiple connector symbols",
        pin_number="1",
        assignments=assignments,
        outlier_pins=("J2.1",),
        peer_assignment_group="front_panel_ports",
        peer_assignment_basis=("Project-reviewed peer set",),
        peer_identity_basis="part_id",
        peer_identity="PORT-3P",
        peer_symbols=("Vendor:PortA", "Vendor:PortB"),
    )
    assignments["J2.1"] = ("MUTATED",)

    candidate = ConnectorPeerPinAssignmentCandidate.from_source_evidence(
        source,
        subject="PART_ID PORT-3P pin 1",
        message="Review the open peer contact.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "connector.peer_pin_assignment_outlier"
    assert candidate.evidence == {
        "J1.1": ("NET_A",),
        "J2.1": (),
        "J3.1": ("NET_A",),
        "symbol": ("Vendor:PortA", "Vendor:PortB"),
        "pin_number": ("1",),
        "outlier_pins": ("J2.1",),
        "peer_identity_basis": ("part_id",),
        "peer_identity": ("PORT-3P",),
        "peer_symbols": ("Vendor:PortA", "Vendor:PortB"),
        "peer_assignment_group": ("front_panel_ports",),
        "peer_assignment_basis": ("Project-reviewed peer set",),
    }
    with pytest.raises(TypeError):
        source.assignments["J2.1"] = ("MUTATED",)  # type: ignore[index]


def test_peer_divergence_candidate_preserves_missing_function_assignments() -> None:
    source = ConnectorPeerPinAssignmentDivergence(
        symbol="Synthetic:GenericPort",
        pin_number="2",
        assignments={"J1.2": ("SIGNAL_A",), "J2.2": ("SIGNAL_B",)},
        missing_function_pins=("J1.2",),
    )

    candidate = ConnectorPeerPinAssignmentCandidate.from_source_evidence(
        source,
        subject="Synthetic:GenericPort pin 2",
        message="Review the connector pin assignment.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "connector.peer_pin_assignment_divergence"
    assert candidate.evidence == {
        "J1.2": ("SIGNAL_A",),
        "J2.2": ("SIGNAL_B",),
        "symbol": ("Synthetic:GenericPort",),
        "pin_number": ("2",),
        "missing_pin_function_pins": ("J1.2",),
    }
    assert project_connector_peer_pin_assignment_evidence(source).evidence == candidate.evidence
