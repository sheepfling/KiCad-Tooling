"""Translate connector return roles and cross-net return-domain patterns."""

from __future__ import annotations

from .component_return_pin_domains import component_return_pin_net_divergences
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_can_review import can_connector_missing_return_candidates
from .connector_return_i2c_review import i2c_connector_missing_return_candidates
from .connector_return_i3c_review import i3c_connector_missing_return_candidates
from .connector_return_pins import (
    connectors_without_connected_return,
    unconnected_named_connector_pins,
)
from .connector_return_rs485_review import rs485_connector_missing_return_candidates
from .connector_return_serial_review import serial_connector_missing_return_candidates
from .connector_return_signal_net import return_pin_protocol_signal_net_candidates
from .connector_return_supply import return_pin_positive_rail_candidates
from .connector_return_swd_review import swd_connector_missing_return_candidates
from .connector_return_usb2_review import usb2_connector_missing_return_candidates
from .connector_return_usb_superspeed_review import (
    usb_superspeed_connector_missing_return_candidates,
)
from .design_lint_return_candidate_evidence import (
    ConnectorNoReturnEvidence,
    NumberedReturnEvidence,
    ReturnDomainCandidate,
    UnroledReturnLabelsEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
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
    found.extend(component_return_pin_net_divergences(observed, reviewed_connector_references))
    found.extend(
        serial_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        i2c_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        i3c_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        swd_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        can_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        rs485_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        usb2_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        usb_superspeed_connector_missing_return_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    found.extend(
        return_pin_positive_rail_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(
        return_pin_protocol_signal_net_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
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
        if return_named_candidates:
            message += (
                " Some assigned net labels look return-related; their spelling does not "
                "identify the connector pin role."
            )
        found.append(
            ReturnDomainCandidate.from_source_evidence(
                ConnectorNoReturnEvidence(group, return_named_candidates),
                subject=(
                    f"{group.reference}: return pin role not identified"
                    if return_named_candidates
                    else f"{group.reference}: no connected return"
                ),
                message=message,
            )
        )

    for group in return_net_groups(observed):
        found.append(
            ReturnDomainCandidate.from_source_evidence(
                NumberedReturnEvidence(group),
                subject=group.stem,
                message=(
                    "Separately numbered return nets may be intended as one return domain. "
                    "Review whether they are common, bonded, or intentionally isolated."
                ),
            )
        )

    for group in return_label_groups_without_pin_roles(observed):
        found.append(
            ReturnDomainCandidate.from_source_evidence(
                UnroledReturnLabelsEvidence(group),
                subject=group.stem,
                message=(
                    "Multiple return-like net labels are assigned to pins whose exported symbol "
                    "functions do not identify a return. Review the connector pinout and decide "
                    "whether these domains are common, bonded, or intentionally isolated; labels "
                    "alone do not establish that they should be joined."
                ),
            )
        )

    return tuple(found)
