"""Build mapped power-path review candidates."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .models import NetlistContract, PowerPathMap
from .power_paths import power_path_mismatches


def power_path_candidates(
    observed: NetlistContract,
    power_path_map: PowerPathMap | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if power_path_map is not None:
        map_sha256 = hashlib.sha256(power_path_map.model_dump_json().encode("utf-8")).hexdigest()
        for mismatch in power_path_mismatches(power_path_map, observed):
            found.append(
                Candidate(
                    rule_id="power.mapped_series_path_mismatch",
                    subject=f"{mismatch.path_id}: required power path differs",
                    message=(
                        "The mapped power path differs from the project-authored component and "
                        "pin/net assignments. Review the named endpoints and fitted series "
                        "components. This check does not establish component conduction, "
                        "electrical suitability, or PCB copper continuity."
                    ),
                    evidence={
                        "path": (mismatch.path_id,),
                        "basis": (mismatch.basis,),
                        "start_endpoint": (f"{mismatch.start_pin} on {mismatch.start_net}",),
                        "end_endpoint": (f"{mismatch.end_pin} on {mismatch.end_net}",),
                        "mapped_elements": mismatch.elements,
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
    return tuple(found)
