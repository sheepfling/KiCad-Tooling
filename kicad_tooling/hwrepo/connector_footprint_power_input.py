"""Review open named power-input pins across footprint-alias connectors."""

from __future__ import annotations

from .connector_footprint_peer_pins import ConnectorFootprintPeerPinScan
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_named_power_input_open_outlier"


def footprint_named_power_input_open_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Review a named power-input contact open on one footprint-alias peer.

    Peer identity, complete inventories, matching pin metadata, one common
    anchor, and a single net among assigned peers are assembled by the shared
    footprint-alias scan. The evidence only prompts review; it does not prove
    that the contacts should share a net.
    """
    candidates: list[Candidate] = []
    for item in scan.open_outliers:
        function = item.pin_function
        if (
            item.pin_electrical_type.strip().casefold() != "power_in"
            or pin_function_is_generic(function)
            or is_named_supply_function(function)
            or is_return_function(function)
        ):
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{item.value} [{item.footprint}] pin {item.pin_number} ({function}): "
                    "named power-input contact is open on a similar connector peer"
                ),
                message=(
                    "Fitted connector instances with distinct native symbols share the same "
                    "value, footprint, complete pin inventory, and matching native pin "
                    "metadata. This explicit power_in contact is assigned to one net on some "
                    "peers and left open on others, while another pin provides a common-net "
                    "anchor. Review the approved pinout for an intentionally unused contact or "
                    "a missing connection; these similarity clues do not establish that the "
                    "contact must connect."
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
                    "pin_function": (function,),
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
