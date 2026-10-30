"""Review unanchored generic pin splits in source-matched connector peer groups."""

from __future__ import annotations

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_unanchored_assignment_divergence"


def reviewed_unanchored_connector_alias_divergences(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Prompt only for complete generic pin splits scoped by current project review."""
    candidates: list[Candidate] = []
    for item in scan.unanchored_divergences:
        if (
            item.peer_assignment_group is None
            or not item.peer_assignment_basis
            or item.common_anchor_pin_numbers
            or not pin_function_is_generic(item.pin_function)
            or len(item.assignments) < 2
            or any(len(nets) != 1 for nets in item.assignments.values())
            or len({nets[0] for nets in item.assignments.values()}) < 2
        ):
            continue
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
                message=(
                    "Fitted connector aliases with the same value, footprint, complete pin inventory, "
                    "and native pin metadata assign this generic contact to different nets in one "
                    "current source-matched peer group, but have no shared-net anchor. Review the "
                    "approved pinouts and intended port design. The peer group scopes comparison; "
                    "it does not say the nets must match, and this finding does not establish that "
                    "the contacts should be joined."
                ),
                evidence={
                    "value": (item.value,),
                    "footprint": (item.footprint,),
                    "pin_number": (item.pin_number,),
                    "pin_function": (item.pin_function,),
                    "assignments": tuple(
                        f"{pin}={nets[0]}"
                        for pin, nets in sorted(
                            item.assignments.items(),
                            key=lambda pair: (pair[0].casefold(), pair[0]),
                        )
                    ),
                    "symbols": item.symbols,
                    "common_anchor_pin_numbers": (),
                    "peer_assignment_group": (item.peer_assignment_group,),
                    "peer_assignment_basis": item.peer_assignment_basis,
                },
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                tuple(item.evidence["assignments"]),
                tuple(item.evidence["symbols"]),
            ),
        )
    )
