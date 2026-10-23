"""Translate source-bound connector pin and peer-assignment observations."""

from __future__ import annotations

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
    source_matched_connector_return_comparison_groups,
    source_matched_connector_supply_comparison_groups,
)
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import similar_connector_pin_groups
from .connector_mapped_interface_pins import (
    unassigned_mapped_interface_power_contacts,
    unassigned_mapped_interface_shield_pins,
    unassigned_mapped_interface_signal_pins,
)
from .connector_peer_candidate_evidence import (
    connector_group_evidence,
    connector_group_message,
)
from .connector_peer_pin_all_open import all_open_generic_connector_peer_pin_candidates
from .connector_peer_pin_findings import (
    connector_peer_pin_assignment_divergences,
    connector_peer_pin_assignment_outliers,
)
from .connector_peer_power_input import (
    connector_named_power_input_all_open,
    connector_named_power_input_assignment_divergence,
    connector_named_power_input_open_assignments,
)
from .connector_peer_power_output import (
    connector_named_power_output_all_open,
    connector_named_power_output_assignment_divergence,
    connector_named_power_output_open_assignments,
)
from .connector_return_pins import (
    unconnected_generic_power_input_connector_pins,
    unconnected_generic_power_output_connector_pins,
    unconnected_named_connector_pins,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract


def connector_pin_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    power_output_review_enabled: bool = True,
) -> tuple[Candidate, ...]:
    """Build review prompts from connector pin roles and peer assignments."""
    found: list[Candidate] = []
    reviewed_connector_pins = source_matched_connector_pin_evidence(
        observed,
        connector_coverage,
    )

    reviewed_connector_peer_assignment_groups = source_matched_connector_peer_assignment_groups(
        observed,
        connector_coverage,
    )
    reviewed_connector_return_comparison_groups = source_matched_connector_return_comparison_groups(
        observed, connector_coverage
    )
    reviewed_connector_supply_comparison_groups = source_matched_connector_supply_comparison_groups(
        observed, connector_coverage
    )

    unconnected_named_pins = unconnected_named_connector_pins(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    )

    named_open_connector_pins = frozenset(item.pin for item in unconnected_named_pins) | frozenset(
        pin
        for pin, mapped in reviewed_connector_pins.items()
        if mapped.unconnected_reason is not None
    )

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

    unconnected_power_output_pins = unconnected_generic_power_output_connector_pins(
        observed,
        reviewed_connector_references,
        excluded_pins=named_open_connector_pins,
    )
    unconnected_power_output_pin_keys = frozenset(
        item.pin.casefold() for item in unconnected_power_output_pins
    )
    for pin in unconnected_power_output_pins:
        evidence = {
            "symbol": (pin.symbol,),
            "pin_electrical_type": (pin.electrical_type,),
            pin.pin: (),
        }
        if pin.function is not None:
            evidence["native_pin_function"] = (pin.function,)
        found.append(
            Candidate(
                rule_id="connector.unconnected_power_output",
                subject=f"{pin.pin}: generic native power-output pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic connector pin as "
                    "power_out, but the exported netlist assigns it to no net. Review the "
                    "approved pinout to determine whether the contact is intentionally open "
                    "or whether a power-output connection is missing. The electrical type does "
                    "not identify the contact's specific role or require it to be connected."
                ),
                evidence=evidence,
            )
        )

    repeated_connector_pin_groups = similar_connector_pin_groups(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
        reviewed_connector_peer_assignment_groups,
        return_comparison_groups=reviewed_connector_return_comparison_groups,
        supply_comparison_groups=reviewed_connector_supply_comparison_groups,
    )

    for group in repeated_connector_pin_groups:
        group_pin_keys = {pin.casefold() for pin in group.pins}
        if group_pin_keys and group_pin_keys <= unconnected_power_input_pin_keys:
            # The native power-input type provides the more specific open-pin finding.
            continue
        if (
            power_output_review_enabled
            and group_pin_keys
            and group_pin_keys <= unconnected_power_output_pin_keys
        ):
            # The native power-output type provides the more specific open-pin finding.
            continue
        found.append(
            Candidate(
                rule_id="connector.repeated_pin_function",
                subject=f"{group.symbol}: {group.function}",
                message=connector_group_message(group),
                evidence={
                    **dict(group.pins),
                    **connector_group_evidence(
                        group,
                        observed,
                        reviewed_connector_pins,
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
        if (
            power_output_review_enabled
            and {pin.casefold() for pin in group.outlier_pins} <= unconnected_power_output_pin_keys
        ):
            # Keep the typed power-output finding when it is enabled.
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

    found.extend(
        all_open_generic_connector_peer_pin_candidates(
            observed,
            reviewed_connector_references,
            reviewed_connector_pins,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_input_open_assignments(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_input_all_open(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_input_assignment_divergence(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_output_open_assignments(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_output_all_open(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(
        connector_named_power_output_assignment_divergence(
            observed,
            reviewed_connector_references,
            reviewed_connector_peer_assignment_groups,
        )
    )
    found.extend(unassigned_mapped_interface_signal_pins(observed, connector_coverage))
    found.extend(unassigned_mapped_interface_shield_pins(observed, connector_coverage))
    found.extend(unassigned_mapped_interface_power_contacts(observed, connector_coverage))

    return tuple(found)
