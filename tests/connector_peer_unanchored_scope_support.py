"""Shared reviewed-map fixture for unanchored connector peer-scope tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)
from tests.connector_footprint_peer_support import NETLIST_SHA256

PEER_GROUP = "synthetic-peer-connectors"
PEER_BASIS = "Synthetic connector pinouts were reviewed as one peer set"


def reviewed_coverage(
    observed: NetlistContract,
    groups: tuple[str | None, str | None] = (PEER_GROUP, PEER_GROUP),
    *,
    inventory_reviewed: bool = True,
    pin_maps_complete: bool = True,
) -> ConnectorCoverageReport:
    """Build a complete source-matched two-pin map with configurable peer scope."""
    interface = InterfaceRecord(
        id="synthetic-generic-port",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"contact-{number}",
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating="synthetic peer",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number in (1, 2)
        ),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis="Synthetic exact pin mapping",
            interface_id="synthetic-generic-port",
            pin_map=({"1": "1", "2": "2"} if pin_maps_complete else {"1": "1"}),
            peer_assignment_group=group,
            peer_assignment_basis=None if group is None else PEER_BASIS,
        )
        for reference, group in zip(("J1", "J2"), groups, strict=True)
    )
    return evaluate_connector_coverage(
        observed,
        ("synthetic-generic-port",),
        reviews,
        interfaces={"synthetic-generic-port": interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=(
            ConnectorInventoryReview(basis="Synthetic connector inventory was reviewed")
            if inventory_reviewed
            else None
        ),
    )


def lint_report(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Run the common typed lint service against a synthetic connector netlist."""
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-unanchored-assignment",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate_design_lint(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )
