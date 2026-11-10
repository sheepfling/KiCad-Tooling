"""Review split named power outputs across unlike connector peers."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .connector_reviewed_peer_power_contacts import (
    reviewed_peer_power_contact_pairs,
    reviewed_peer_power_pair_evidence,
    sort_reviewed_peer_power_candidates,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_power_output_split"
_POWER_OUTPUT_ELECTRICAL_TYPES = frozenset({"power_out"})


def reviewed_peer_power_output_split_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Find unlike named supply outputs split across fully reviewed peers."""
    candidates: list[Candidate] = []
    pairs = reviewed_peer_power_contact_pairs(
        observed,
        coverage,
        electrical_types=_POWER_OUTPUT_ELECTRICAL_TYPES,
    )
    for pair in pairs:
        left, right = pair.pins
        if (
            pair.classification != "named power contacts"
            or any(pin.role != "supply" for pin in pair.pins)
            or any(
                pin.direction is None or pin.direction.strip().casefold() != "output"
                for pin in pair.pins
            )
            or any(category is None for category in pair.power_categories)
            or pair.power_categories[0] == pair.power_categories[1]
            or pair.electrical_types != ("power_out", "power_out")
            or len(left.nets) != 1
            or len(right.nets) != 1
            or left.nets[0].casefold() == right.nets[0].casefold()
        ):
            continue
        assignments = (
            f"{left.component_pin}={left.nets[0]}",
            f"{right.component_pin}={right.nets[0]}",
        )
        evidence = reviewed_peer_power_pair_evidence(pair, assignments)
        evidence["interface_directions"] = ("output", "output")
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                    "named power outputs use separate nets"
                ),
                message=(
                    "Unlike connector symbols in this source-reviewed peer group map named "
                    "native power-output contacts with different recognized supply functions "
                    "to the same interface signal, output direction, and voltage domain, but "
                    "assign them to different nets. Review whether separate sources, protection, "
                    "or isolation are intentional. The map does not prove these nets should be "
                    "joined or that PCB copper is continuous."
                ),
                evidence=evidence,
            )
        )
    return sort_reviewed_peer_power_candidates(candidates)
