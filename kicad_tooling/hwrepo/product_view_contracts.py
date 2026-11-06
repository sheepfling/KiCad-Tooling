"""Exact authored coverage checks for system and harness product views."""

from __future__ import annotations

from . import project_models
from .product_models import ConnectionKind, ProductRecord


def validate_system_wiring_contract(
    product: ProductRecord, validation: project_models.SystemWiringValidationContract
) -> None:
    """Fail unless a system diagram declares complete typed product traceability.

    The drawing is a review view. Product records remain authoritative for relation
    kinds, terminals, harnesses, and mechanical handoffs, so a visual line cannot
    silently turn a functional or mechanical relationship into electrical truth.
    """
    connections = {connection.id: connection for connection in product.connections}
    terminals = {terminal.id for terminal in product.terminals}
    harnesses = {harness.id for harness in product.harnesses}
    handoffs = {handoff.id for handoff in product.mechanical}
    declared_connections = set(validation.connection_ids)
    if declared_connections != set(connections):
        raise ValueError(
            "System wiring connection coverage differs; "
            f"missing={sorted(set(connections) - declared_connections)}, "
            f"extra={sorted(declared_connections - set(connections))}"
        )
    endpoints = {
        terminal_id
        for connection in connections.values()
        for terminal_id in (connection.from_terminal, connection.to_terminal)
    }
    if set(validation.terminal_ids) != endpoints or not endpoints <= terminals:
        raise ValueError("System wiring terminal coverage differs from connection endpoints")
    if set(validation.harness_ids) != harnesses:
        raise ValueError("System wiring harness coverage differs from the product contract")
    if set(validation.mechanical_handoff_ids) != handoffs:
        raise ValueError(
            "System wiring mechanical-handoff coverage differs from the product contract"
        )


def validate_harness_interface_contract(
    product: ProductRecord, validation: project_models.HarnessInterfaceValidationContract
) -> None:
    """Fail unless a harness view owns exactly its declared electrical conductors."""
    connections = {connection.id: connection for connection in product.connections}
    terminals = {terminal.id for terminal in product.terminals}
    harnesses = {harness.id for harness in product.harnesses}
    declared_harnesses = set(validation.harness_ids)
    if not declared_harnesses <= set(harnesses):
        raise ValueError("Harness interface references an unknown product harness")
    expected_connections = {
        connection.id
        for connection in connections.values()
        if connection.kind is ConnectionKind.ELECTRICAL and connection.harness in declared_harnesses
    }
    declared_connections = set(validation.connection_ids)
    if declared_connections != expected_connections:
        raise ValueError(
            "Harness interface conductor coverage differs; "
            f"missing={sorted(expected_connections - declared_connections)}, "
            f"extra={sorted(declared_connections - expected_connections)}"
        )
    endpoints = {
        terminal_id
        for connection_id in declared_connections
        for terminal_id in (
            connections[connection_id].from_terminal,
            connections[connection_id].to_terminal,
        )
    }
    if set(validation.terminal_ids) != endpoints or not endpoints <= terminals:
        raise ValueError("Harness interface terminal coverage differs from conductor endpoints")
