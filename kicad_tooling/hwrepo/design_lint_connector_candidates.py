"""Translate connector pin, return-domain, and return-distribution observations."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_identity import power_function_key, similar_connector_pin_groups
from .connector_peer_pin_findings import (
    connector_peer_pin_assignment_divergences,
    connector_peer_pin_assignment_outliers,
)
from .connector_return_pins import (
    connectors_without_connected_return,
    unconnected_generic_power_input_connector_pins,
    unconnected_named_connector_pins,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    NetlistContract,
    SimilarConnectorPinGroup,
)
from .power_rails import numbered_power_rail_groups
from .return_nets import (
    is_return_like_net_name,
    return_label_groups_without_pin_roles,
    return_net_groups,
)


def _connector_group_message(group: SimilarConnectorPinGroup) -> str:
    scope = (
        f" This comparison is scoped to source-reviewed peer-assignment group "
        f"{group.peer_assignment_group}."
        if group.peer_assignment_group is not None
        else ""
    )
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        return (
            "Connector supply contacts with the same source-reviewed voltage domain "
            f"({group.reviewed_voltage_domain}) use different or missing nets. Review whether "
            "they share a rail, are intentionally switched or isolated, or have independent "
            "sources; this role and domain classification does not require commonality." + scope
        )
    function = group.function
    if function == "ground/return":
        return (
            "Connector return pins identified by symbol functions or the source-matched project "
            "interface map use different or missing nets. Review whether the domains should be "
            "common, bonded, or intentionally isolated; role classification alone does not "
            "require commonality." + scope
        )
    if power_function_key(function) is not None:
        return (
            "Matching connector supply pins use different or missing nets. Review whether they "
            "share a rail, are intentionally separate, or have independent supplies." + scope
        )
    return (
        "Matching connector pin functions use different or missing nets. Review the intended "
        "pinout and signal relationship." + scope
    )


def _connector_group_role_source_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        domain = str(group.reviewed_voltage_domain)
        sources = [
            f"{pin}: project interface catalog role=supply; "
            f"voltage_domain={domain}; "
            f"native symbol function={observed.pin_functions.get(pin) or '<unnamed>'}"
            for pin in sorted(group.pins)
        ]
        return {
            "role_classification_sources": tuple(sources),
            "reviewed_voltage_domain": (domain,),
        }
    if group.function != "ground/return":
        return {}

    sources: list[str] = []
    has_catalog_role = False
    for pin in sorted(group.pins):
        native_function = observed.pin_functions.get(pin) or "<unnamed>"
        mapped = reviewed_connector_pins.get(pin)
        if mapped is not None and mapped.role == "return":
            has_catalog_role = True
            sources.append(
                f"{pin}: project interface catalog role=return; "
                f"native symbol function={native_function}"
            )
        else:
            sources.append(f"{pin}: native symbol function={native_function}")
    if not has_catalog_role:
        return {}
    return {"role_classification_sources": tuple(sources)}


def connector_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Build review prompts from connector pin roles and return-domain patterns."""
    found: list[Candidate] = []
    reviewed_connector_pins = source_matched_connector_pin_evidence(
        observed,
        connector_coverage,
    )

    reviewed_connector_peer_assignment_groups = source_matched_connector_peer_assignment_groups(
        observed,
        connector_coverage,
    )

    unconnected_named_pins = unconnected_named_connector_pins(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    )

    named_open_connector_pins = frozenset(item.pin for item in unconnected_named_pins)

    unconnected_power_input_pins = unconnected_generic_power_input_connector_pins(
        observed,
        reviewed_connector_references,
        excluded_pins=named_open_connector_pins,
    )

    unconnected_power_input_pin_keys = frozenset(
        item.pin.casefold() for item in unconnected_power_input_pins
    )

    for pin in unconnected_power_input_pins:
        evidence = {
            "symbol": (pin.symbol,),
            "pin_electrical_type": (pin.electrical_type,),
            pin.pin: (),
        }
        if pin.function is not None:
            evidence["native_pin_function"] = (pin.function,)
        found.append(
            Candidate(
                rule_id="connector.unconnected_power_input",
                subject=f"{pin.pin}: generic native power-input pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic connector pin as "
                    "power_in, but the exported netlist assigns it to no net. Review the approved "
                    "pinout to determine whether the contact is intentionally open or whether a "
                    "power or reference connection is missing. The electrical type does not "
                    "identify the contact's specific role or require it to be connected."
                ),
                evidence=evidence,
            )
        )

    repeated_connector_pin_groups = similar_connector_pin_groups(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
        reviewed_connector_peer_assignment_groups,
    )

    for group in repeated_connector_pin_groups:
        group_pin_keys = {pin.casefold() for pin in group.pins}
        if group_pin_keys and group_pin_keys <= unconnected_power_input_pin_keys:
            # The native power-input type provides the more specific open-pin finding.
            continue
        found.append(
            Candidate(
                rule_id="connector.repeated_pin_function",
                subject=f"{group.symbol}: {group.function}",
                message=_connector_group_message(group),
                evidence={
                    **dict(group.pins),
                    **_connector_group_role_source_evidence(
                        group,
                        observed,
                        reviewed_connector_pins,
                    ),
                    **(
                        {}
                        if group.peer_assignment_group is None
                        else {
                            "peer_assignment_group": (group.peer_assignment_group,),
                            "peer_assignment_basis": group.peer_assignment_basis,
                        }
                    ),
                },
            )
        )

    for group in connector_peer_pin_assignment_outliers(
        observed,
        reviewed_connector_references,
        reviewed_connector_peer_assignment_groups,
    ):
        if {pin.casefold() for pin in group.outlier_pins} <= unconnected_power_input_pin_keys:
            # The typed power-input finding already identifies every open outlier pin.
            continue
        if any(
            set(group.assignments) <= set(specific_group.pins)
            for specific_group in repeated_connector_pin_groups
        ):
            # A source-matched role finding already gives the same peers' exact
            # per-pin net assignments and a more useful classification.
            continue
        evidence = dict(group.assignments)
        evidence["symbol"] = (
            group.peer_symbols if group.peer_identity_basis == "part_id" else (group.symbol,)
        )
        evidence["pin_number"] = (group.pin_number,)
        evidence["outlier_pins"] = group.outlier_pins
        if group.peer_identity_basis == "part_id":
            evidence["peer_identity_basis"] = ("part_id",)
            evidence["peer_identity"] = (group.peer_identity,)
            evidence["peer_symbols"] = group.peer_symbols
        if group.peer_assignment_group is not None:
            evidence["peer_assignment_group"] = (group.peer_assignment_group,)
            evidence["peer_assignment_basis"] = group.peer_assignment_basis
        if group.peer_identity_basis == "part_id":
            subject = f"PART_ID {group.peer_identity} pin {group.pin_number}"
            message = (
                "Fitted connector symbol aliases with this native PART_ID have an unconnected "
                "or minority assignment on the same generic pin, and their value, footprint, "
                "pin inventory, function, and electrical-type metadata match. Review the approved "
                "pinout and intentional per-port isolation; matching part identity does not prove "
                "the nets must be common."
            )
        else:
            subject = f"{group.symbol} pin {group.pin_number}"
            message = (
                "The same pin number on fitted instances of this exact connector symbol has "
                "an unconnected or minority assignment, and at least one peer has no "
                "meaningful native pin-function role. Review the approved pinout and any "
                "intentional per-port isolation; matching symbol contacts do not prove that "
                "their nets must be common."
            )
        found.append(
            Candidate(
                rule_id="connector.peer_pin_assignment_outlier",
                subject=subject,
                message=(
                    message
                    + (
                        " The comparison is scoped by a source-reviewed peer-assignment group."
                        if group.peer_assignment_group is not None
                        else ""
                    )
                ),
                evidence=evidence,
            )
        )

    for group in connector_peer_pin_assignment_divergences(
        observed,
        reviewed_connector_references,
        reviewed_connector_peer_assignment_groups,
    ):
        if any(
            set(group.assignments) <= set(specific_group.pins)
            for specific_group in repeated_connector_pin_groups
        ):
            # Keep one finding when the higher-confidence role comparison
            # already covers every contact in this generic peer group.
            continue
        if group.peer_identity_basis == "part_id":
            subject = f"PART_ID {group.peer_identity} pin {group.pin_number}"
            message = (
                "Fitted connector symbol aliases with this native PART_ID assign a generic pin "
                "to different nets, and their value, footprint, pin inventory, function, and "
                "electrical-type metadata match. Review the approved pinout to decide whether "
                "these assignments should match or are intentionally independent; matching part "
                "identity does not establish a required connection."
            )
            symbols = group.peer_symbols
            identity_evidence = {
                "peer_identity_basis": ("part_id",),
                "peer_identity": (group.peer_identity,),
                "peer_symbols": group.peer_symbols,
            }
        else:
            subject = f"{group.symbol} pin {group.pin_number}"
            message = (
                "Fitted instances of this exact connector symbol assign the same pin number "
                "to different nets, and at least one instance has no meaningful native "
                "pin-function role. KiCad's generic Pin_N placeholder is treated as unknown. "
                "Review the approved pinout to decide whether these assignments should match "
                "or are intentionally independent; symbol identity alone does not establish "
                "a required connection."
            )
            symbols = (group.symbol,)
            identity_evidence = {}
        scoped_evidence = (
            {}
            if group.peer_assignment_group is None
            else {
                "peer_assignment_group": (group.peer_assignment_group,),
                "peer_assignment_basis": group.peer_assignment_basis,
            }
        )
        found.append(
            Candidate(
                rule_id="connector.peer_pin_assignment_divergence",
                subject=subject,
                message=(
                    message
                    + (
                        " The comparison is scoped by a source-reviewed peer-assignment group."
                        if group.peer_assignment_group is not None
                        else ""
                    )
                ),
                evidence={
                    **group.assignments,
                    "symbol": symbols,
                    "pin_number": (group.pin_number,),
                    "missing_pin_function_pins": group.missing_function_pins,
                    **identity_evidence,
                    **scoped_evidence,
                },
            )
        )

    repeated_pin_evidence = {
        pin
        for item in found
        if item.rule_id == "connector.repeated_pin_function"
        for pin in item.evidence
    }

    for pin in unconnected_named_pins:
        # A repeated-function finding already reports missing members in its group.
        if pin.pin in repeated_pin_evidence:
            continue
        if pin.category == "supply":
            rule_id: DesignLintRuleId = "connector.unconnected_supply_pin"
            description = "supply"
            review = "whether it is intentionally unused or a power connection is missing"
        else:
            rule_id = "connector.unconnected_return_pin"
            description = "return"
            review = (
                "whether it is intentionally unused or isolated, or a return connection is missing"
            )
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This source-matched project interface maps the connector contact as {description}, "
                    f"but it has no net assignment. Review {review}."
                    if pin.role_source == "project_interface"
                    else f"This named connector {description} pin has no net assignment. "
                    f"Review {review}."
                ),
                evidence={
                    pin.pin: (),
                    **(
                        {"role_source": ("project interface catalog",)}
                        if pin.role_source == "project_interface"
                        else {}
                    ),
                },
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

    for group in numbered_power_rail_groups(observed):
        found.append(
            Candidate(
                rule_id="net.numbered_power_rails",
                subject=group.stem,
                message=(
                    "Separately numbered positive supply nets may be intended as one rail. "
                    "Review whether they are common, intentionally isolated, or represent "
                    "independent supplies; similar names do not establish a required connection."
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
