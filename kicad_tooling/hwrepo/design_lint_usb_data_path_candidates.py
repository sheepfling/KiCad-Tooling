"""Build source-mapped USB data-path review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .design_lint_usb_data_path_candidate_evidence import (
    UsbDataPathCandidate,
    UsbDataPathFindingEvidence,
)
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .netlist_contract_models import NetlistContract
from .usb_data_paths import usb_data_path_mismatches


def usb_data_path_candidates(
    observed: NetlistContract,
    usb_data_path: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    path_map = usb_data_path.authored_map
    if path_map is None:
        return ()
    map_sha256 = usb_data_path.map_sha256
    if map_sha256 is None:
        raise ValueError("USB data-path map must have its canonical digest")

    for mismatch in usb_data_path_mismatches(path_map, observed):
        found.append(
            UsbDataPathCandidate.from_source_evidence(
                source_evidence=UsbDataPathFindingEvidence(
                    mismatch=mismatch,
                    map_sha256=map_sha256,
                ),
                subject=(
                    f"{mismatch.interface_id}: USB protection shunt map"
                    if mismatch.line == "protection_shunt"
                    else f"{mismatch.interface_id}: USB {mismatch.line} path"
                ),
                message=(
                    "The mapped multi-pin USB protection shunt differs "
                    "from the project-authored component identity, complete pin inventory, "
                    "or pin assignments. Review its symbol, footprint, population, and pins."
                    if mismatch.line == "protection_shunt"
                    else "The connector-to-PHY USB reference pins or exact mapped bond differ "
                    "from the project-authored reference policy. Review the pins, nets, and "
                    "bond component; the map records schematic intent but does not prove "
                    "component conduction or PCB continuity."
                    if mismatch.line == "reference"
                    else "The connector-to-PHY USB data path differs from the project-authored, "
                    "PHY-specific topology. Review the exact pin assignments, fitted series "
                    "or inline component, and manufacturer basis. This check does not infer a universal "
                    "USB resistor requirement or establish PCB continuity."
                ),
            )
        )
    return tuple(found)
