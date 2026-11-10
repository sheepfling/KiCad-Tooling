"""Review an open named power output beside an unlike connector peer."""

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

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_power_output_open"
_POWER_OUTPUT_ELECTRICAL_TYPES = frozenset({"power_out"})


def reviewed_peer_power_output_open_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Find one open mapped named power output beside an assigned peer output."""
    candidates: list[Candidate] = []
    pairs = reviewed_peer_power_contact_pairs(
        observed,
        coverage,
        electrical_types=_POWER_OUTPUT_ELECTRICAL_TYPES,
    )
    for pair in pairs:
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
        ):
            continue

        for opened_index, assigned_index in ((0, 1), (1, 0)):
            opened = pair.pins[opened_index]
            assigned = pair.pins[assigned_index]
            if opened.nets or opened.unconnected_reason is not None or len(assigned.nets) != 1:
                continue
            assignments = (
                f"{opened.component_pin}=<unassigned>",
                f"{assigned.component_pin}={assigned.nets[0]}",
            )
            evidence = reviewed_peer_power_pair_evidence(pair, assignments)
            evidence["interface_directions"] = ("output", "output")
            candidates.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(
                        f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                        "named power output is open beside an assigned peer"
                    ),
                    message=(
                        "Unlike connector symbols in this source-reviewed peer group map named "
                        "native power-output contacts with different recognized supply functions "
                        "to the same interface signal, output direction, and voltage domain, but "
                        "one contact has no assigned net or authored unconnected reason while its "
                        "peer has one assigned net. Review whether the open is intentional or a "
                        "connection is missing. The map does not require connecting the contacts, "
                        "select a target net, or prove PCB copper continuity."
                    ),
                    evidence=evidence,
                )
            )
    return sort_reviewed_peer_power_candidates(candidates)
