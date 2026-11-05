"""Review named power-input assignments across connector symbol aliases."""

from __future__ import annotations

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_peer_named_power_aliases import (
    connector_named_power_alias_peers,
)
from .design_lint_connector_named_power_alias_candidate_evidence import (
    ConnectorNamedPowerAliasRuleId,
    connector_named_power_alias_candidate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: ConnectorNamedPowerAliasRuleId = "connector.peer_power_input_open_assignment"
ALL_OPEN_RULE_ID: ConnectorNamedPowerAliasRuleId = "connector.peer_power_input_named_all_open"
DIVERGENCE_RULE_ID: ConnectorNamedPowerAliasRuleId = (
    "connector.peer_power_input_named_assignment_divergence"
)


def connector_named_power_input_open_assignments(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopes | None = None,
) -> tuple[Candidate, ...]:
    """Review a named power-input contact open on one PART_ID symbol alias peer.

    The shared connector scan supplies fitted peers only after matching native
    PART_ID, value, footprint, complete pin inventory, and every pin's function
    and electrical type. This rule narrows that evidence to native ``power_in``
    pins with explicit, unrecognized functions. It reports only mixed
    assigned/open groups spanning distinct symbols; it does not require a
    common net.
    """
    found: list[Candidate] = []
    for peer in connector_named_power_alias_peers(
        observed,
        "power_in",
        declared_references,
        peer_assignment_groups,
    ):
        group = peer.group
        if any(len(nets) > 1 for nets in group.assignments.values()):
            continue
        assigned_pins = tuple(pin for pin, nets in group.assignments.items() if len(nets) == 1)
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        if not assigned_pins or not open_pins:
            continue

        found.append(
            connector_named_power_alias_candidate(
                peer,
                RULE_ID,
                subject=(
                    f"PART_ID {group.part_id} pin {group.pin_number} ({peer.function}): "
                    "named connector power-input peer assignment is open"
                ),
                message=(
                    "Fitted connector symbols sharing this native PART_ID use the same explicit, "
                    "unrecognized power_in pin function, but at least one peer is open while "
                    "another has one net assignment. Review the approved interface pinout for a "
                    "missing connection or an intentionally unused contact; matching part identity "
                    "and pin metadata do not establish that the contacts should share a net."
                ),
            )
        )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )


def connector_named_power_input_all_open(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopes | None = None,
) -> tuple[Candidate, ...]:
    """Review a named power-input pin left open on every guarded connector alias."""
    found: list[Candidate] = []
    for peer in connector_named_power_alias_peers(
        observed,
        "power_in",
        declared_references,
        peer_assignment_groups,
    ):
        group = peer.group
        if any(group.assignments.values()):
            continue

        found.append(
            connector_named_power_alias_candidate(
                peer,
                ALL_OPEN_RULE_ID,
                subject=(
                    f"PART_ID {group.part_id} pin {group.pin_number} ({peer.function}): "
                    "named connector power-input peer pin is open everywhere"
                ),
                message=(
                    "Fitted connector symbols sharing this native PART_ID use the same explicit, "
                    "unrecognized power_in pin function, but every alias is open. Review the "
                    "approved interface pinout for intentionally unused contacts or a missing "
                    "connection; matching part identity and pin metadata do not establish that "
                    "the contacts should share a net."
                ),
            )
        )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )


def connector_named_power_input_assignment_divergence(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopes | None = None,
) -> tuple[Candidate, ...]:
    """Review fully assigned named power-input pins on distinct alias nets."""
    found: list[Candidate] = []
    for peer in connector_named_power_alias_peers(
        observed,
        "power_in",
        declared_references,
        peer_assignment_groups,
    ):
        group = peer.group
        if any(len(nets) != 1 for nets in group.assignments.values()):
            continue
        assigned_nets = {nets[0] for nets in group.assignments.values()}
        if len(assigned_nets) < 2:
            continue

        found.append(
            connector_named_power_alias_candidate(
                peer,
                DIVERGENCE_RULE_ID,
                subject=(
                    f"PART_ID {group.part_id} pin {group.pin_number} ({peer.function}): "
                    "named connector power-input peer assignments diverge"
                ),
                message=(
                    "Fitted connector symbols sharing this native PART_ID use the same explicit, "
                    "unrecognized power_in pin function, but every alias has one net assignment "
                    "and the assignments use different nets. Review the approved interface "
                    "pinout for intentionally separate supplies or a possible assignment "
                    "mismatch; matching part identity and pin metadata do not establish that the "
                    "nets should be joined."
                ),
            )
        )

    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )
