"""Build review findings for eligible named input contacts open across aliases."""

from __future__ import annotations

from .connector_footprint_peer_pins import ConnectorFootprintPeerPinOpenOutlier
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate


def open_input_outlier_candidates(
    records: tuple[ConnectorFootprintPeerPinOpenOutlier, ...],
    *,
    rule_id: DesignLintRuleId,
    role_label: str,
) -> tuple[Candidate, ...]:
    """Convert already classified open-input peer records into review candidates."""
    candidates = tuple(
        Candidate(
            rule_id=rule_id,
            subject=(
                f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function}): "
                f"named {role_label} contact is open on a similar connector peer"
            ),
            message=(
                "Fitted connector instances with distinct native symbols share the same "
                "value, footprint, complete pin inventory, and matching native pin "
                f"metadata. This explicit native {role_label} contact is assigned to one "
                "net on some peers and left open on others, while another pin provides a "
                "common-net anchor. Review the approved pinout for an intentionally unused "
                "contact or a missing connection; these similarity clues do not establish "
                "that the contact must connect."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
            evidence={
                "value": (item.value,),
                "footprint": (item.footprint,),
                "pin_number": (item.pin_number,),
                "pin_function": (item.pin_function,),
                "pin_electrical_type": (item.pin_electrical_type,),
                "assignments": tuple(
                    f"{pin}={','.join(nets) if nets else '<unassigned>'}"
                    for pin, nets in item.assignments.items()
                ),
                "open_pins": item.open_pins,
                "symbols": item.symbols,
                "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
                "peer_identity_basis": ("footprint_value",),
                **(
                    {}
                    if item.peer_assignment_group is None
                    else {
                        "peer_assignment_group": (item.peer_assignment_group,),
                        "peer_assignment_basis": item.peer_assignment_basis,
                    }
                ),
            },
        )
        for item in records
    )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.subject.casefold(),
                candidate.subject,
                tuple(sorted(candidate.evidence)),
            ),
        )
    )
