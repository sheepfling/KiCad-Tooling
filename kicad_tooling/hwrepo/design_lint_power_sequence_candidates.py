"""Build mapped power-sequence review candidates."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .models import NetlistContract, PowerSequenceMap
from .power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
    power_sequence_observed_enable_cycles,
)


def power_sequence_candidates(
    observed: NetlistContract,
    power_sequence_map: PowerSequenceMap | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if power_sequence_map is not None:
        map_sha256 = hashlib.sha256(
            power_sequence_map.model_dump_json().encode("utf-8")
        ).hexdigest()
        for mismatch in power_sequence_mismatches(power_sequence_map, observed):
            found.append(
                Candidate(
                    rule_id="power.mapped_sequence_dependency_mismatch",
                    subject=f"{mismatch.stage_id}: required power-sequence stage differs",
                    message=(
                        "The project's mapped rail, power-good, or enable endpoints differ from "
                        "the native netlist. Review the explicit dependency map and component "
                        "identity. A matching topology does not establish startup timing, control "
                        "state, electrical suitability, or physical rail behavior."
                    ),
                    evidence={
                        "sequence_map_basis": (power_sequence_map.basis,),
                        "stage": (mismatch.stage_id,),
                        "stage_basis": (mismatch.stage_basis,),
                        "enable_control": (mismatch.enable_control,),
                        "expected_endpoints": mismatch.expected_endpoints,
                        "dependencies": tuple(
                            f"{item.id}: {item.predecessor_stage} → "
                            f"{item.successor_stage} on {item.signal_net}"
                            for item in power_sequence_map.dependencies
                            if mismatch.stage_id.casefold()
                            in {
                                item.predecessor_stage.casefold(),
                                item.successor_stage.casefold(),
                            }
                        ),
                        "output_endpoint": (f"{mismatch.output_pin} on {mismatch.output_net}",),
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
        declared_cycle = power_sequence_graph_has_cycle(power_sequence_map)
        observed_cycles = power_sequence_observed_enable_cycles(power_sequence_map, observed)
        if declared_cycle or observed_cycles:
            cycle_issues = (
                *(("The project-authored dependency graph is cyclic",) if declared_cycle else ()),
                *(
                    "The mapped native output-to-enable topology is cyclic across stages "
                    + ", ".join(cycle.stage_ids)
                    for cycle in observed_cycles
                ),
            )
            if declared_cycle and observed_cycles:
                subject = "authored and mapped power-sequence topology contains a cycle"
            elif declared_cycle:
                subject = "project-authored power-sequence dependency graph contains a cycle"
            else:
                subject = "mapped native output-to-enable topology contains a cycle"
            found.append(
                Candidate(
                    rule_id="power.mapped_sequence_dependency_mismatch",
                    subject=subject,
                    message=(
                        "A mapped power-sequence graph contains a cycle. Review the stage "
                        "directions, enable polarity, and source requirement. Native output-to-"
                        "enable edges are considered only when both exact mapped stages match "
                        "the netlist; this does not establish startup behavior or infer stage "
                        "roles from pin names or device families."
                    ),
                    evidence={
                        "sequence_map_basis": (power_sequence_map.basis,),
                        "dependencies": tuple(
                            f"{item.predecessor_stage} → {item.successor_stage} on {item.signal_net}"
                            for item in power_sequence_map.dependencies
                        ),
                        "declared_dependency_cycle": (str(declared_cycle).lower(),),
                        "observed_output_to_enable_cycle_stages": tuple(
                            ", ".join(cycle.stage_ids) for cycle in observed_cycles
                        ),
                        "observed_output_to_enable_cycle_edges": tuple(
                            edge for cycle in observed_cycles for edge in cycle.edges
                        ),
                        "map_sha256": (map_sha256,),
                        "issues": cycle_issues,
                    },
                )
            )
    return tuple(found)
