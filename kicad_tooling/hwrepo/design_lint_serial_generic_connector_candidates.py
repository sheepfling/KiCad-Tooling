"""Translate generic connector UART assignments into review candidates."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_serial_generic_connector_candidate_evidence import (
    SerialGenericConnectorCandidate,
    SerialGenericConnectorFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .serial_generic_connector_candidates import serial_generic_connector_pairs


def serial_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Request pinout review for generic contacts on exact native UART pairs."""
    return tuple(
        SerialGenericConnectorCandidate.from_source_evidence(
            SerialGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match UART TX/RX nets",
            message=(
                "Native assignments place generic connector contacts on the exact TX and RX "
                "nets of a recognized fitted U/IC UART endpoint. Review whether this connector "
                "belongs to that serial interface and document its exact pinout. This prompt "
                "does not infer connector purpose or signal direction from net labels, require "
                "common grounds or power, establish off-board wiring, or prove PCB copper "
                "continuity."
            ),
        )
        for pair in serial_generic_connector_pairs(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
