"""Translate connector return roles and cross-net return-domain patterns."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_return_pins import (
    connectors_without_connected_return,
    unconnected_named_connector_pins,
)
from .design_lint_types import Candidate
from .models import ConnectorCoverageReport, NetlistContract
from .return_nets import (
    is_return_like_net_name,
    return_label_groups_without_pin_roles,
    return_net_groups,
)


def return_domain_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Build review prompts for disconnected and similarly named return domains."""
    reviewed_connector_pins = source_matched_connector_pin_evidence(
        observed,
        connector_coverage,
    )
    unconnected_named_pins = unconnected_named_connector_pins(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    )
    found: list[Candidate] = []
    connectors_with_unconnected_return = {
        item.pin.rsplit(".", 1)[0] for item in unconnected_named_pins if item.category == "return"
    }

    for group in connectors_without_connected_return(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    ):
        # A specifically named unconnected return is a more precise finding.
        if group.reference in connectors_with_unconnected_return:
            continue
        return_named_candidates = tuple(
            f"{pin}: {net}"
            for pin, nets in sorted(group.pins.items())
            for net in nets
            if is_return_like_net_name(net)
        )
        message = (
            f"This connector has {group.connected_pin_count} connected non-shield pins, but no "
            "native symbol function or a source-matched project interface role identifies a connected "
            "ground/return. Review the approved "
            "pinout to determine whether one contact is a signal return or the interface is "
            "intentionally isolated."
        )
        evidence = dict(group.pins)
        if return_named_candidates:
            message += (
                " Some assigned net labels look return-related; their spelling does not "
                "identify the connector pin role."
            )
            evidence["return_named_net_candidates"] = return_named_candidates
        found.append(
            Candidate(
                rule_id="connector.no_connected_return",
                subject=(
                    f"{group.reference}: return pin role not identified"
                    if return_named_candidates
                    else f"{group.reference}: no connected return"
                ),
                message=message,
                evidence=evidence,
            )
        )

    for group in return_net_groups(observed):
        found.append(
            Candidate(
                rule_id="net.numbered_returns",
                subject=group.stem,
                message=(
                    "Separately numbered return nets may be intended as one return domain. "
                    "Review whether they are common, bonded, or intentionally isolated."
                ),
                evidence=dict(group.nets),
            )
        )

    for group in return_label_groups_without_pin_roles(observed):
        found.append(
            Candidate(
                rule_id="net.return_labels_without_pin_roles",
                subject=group.stem,
                message=(
                    "Multiple return-like net labels are assigned to pins whose exported symbol "
                    "functions do not identify a return. Review the connector pinout and decide "
                    "whether these domains are common, bonded, or intentionally isolated; labels "
                    "alone do not establish that they should be joined."
                ),
                evidence=dict(group.nets),
            )
        )

    return tuple(found)
