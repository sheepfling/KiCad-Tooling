"""Build mapped power-sequence review candidates."""

from __future__ import annotations

from .design_lint_power_sequence_candidate_evidence import (
    PowerSequenceCandidate,
    PowerSequenceCycleFindingEvidence,
    PowerSequenceMismatchFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .power_sequence_models import PowerSequenceMap
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
        for mismatch in power_sequence_mismatches(power_sequence_map, observed):
            found.append(
                PowerSequenceCandidate.from_source_evidence(
                    PowerSequenceMismatchFindingEvidence(
                        sequence_map=power_sequence_map,
                        mismatch=mismatch,
                    ),
                    subject=f"{mismatch.stage_id}: required power-sequence stage differs",
                    message=(
                        "The project's mapped rail, power-good, or enable endpoints differ from "
                        "the native netlist. Review the explicit dependency map and component "
                        "identity. A matching topology does not establish startup timing, control "
                        "state, electrical suitability, or physical rail behavior."
                    ),
                )
            )
        declared_cycle = power_sequence_graph_has_cycle(power_sequence_map)
        observed_cycles = power_sequence_observed_enable_cycles(power_sequence_map, observed)
        if declared_cycle or observed_cycles:
            if declared_cycle and observed_cycles:
                subject = "authored and mapped power-sequence topology contains a cycle"
            elif declared_cycle:
                subject = "project-authored power-sequence dependency graph contains a cycle"
            else:
                subject = "mapped native output-to-enable topology contains a cycle"
            found.append(
                PowerSequenceCandidate.from_source_evidence(
                    PowerSequenceCycleFindingEvidence(
                        sequence_map=power_sequence_map,
                        declared_dependency_cycle=declared_cycle,
                        observed_cycles=observed_cycles,
                    ),
                    subject=subject,
                    message=(
                        "A mapped power-sequence graph contains a cycle. Review the stage "
                        "directions, enable polarity, and source requirement. Native output-to-"
                        "enable edges are considered only when both exact mapped stages match "
                        "the netlist; this does not establish startup behavior or infer stage "
                        "roles from pin names or device families."
                    ),
                )
            )
    return tuple(found)
