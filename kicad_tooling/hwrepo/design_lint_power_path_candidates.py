"""Build mapped power-path review candidates."""

from __future__ import annotations

from .design_lint_power_path_candidate_evidence import (
    PowerPathCandidate,
    PowerPathFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .power_path_models import PowerPathMap, power_path_map_sha256
from .power_paths import power_path_mismatches


def power_path_candidates(
    observed: NetlistContract,
    power_path_map: PowerPathMap | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if power_path_map is not None:
        map_sha256 = power_path_map_sha256(power_path_map)
        for mismatch in power_path_mismatches(power_path_map, observed):
            found.append(
                PowerPathCandidate.from_source_evidence(
                    PowerPathFindingEvidence(mismatch=mismatch, map_sha256=map_sha256),
                    subject=f"{mismatch.path_id}: required power path differs",
                    message=(
                        "The mapped power path differs from the project-authored component and "
                        "pin/net assignments. Review the named endpoints and fitted series "
                        "components. This check does not establish component conduction, "
                        "electrical suitability, or PCB copper continuity."
                    ),
                )
            )
    return tuple(found)
