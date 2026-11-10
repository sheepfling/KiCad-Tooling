"""Source-matched connector domain assignments grouped by exact native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_connector_domain_shared_net_candidate_evidence import (
    ConnectorDomainRole,
    MappedConnectorDomainAssignment,
)
from .netlist_contract_models import NetlistContract


def mapped_connector_domain_assignments_by_net(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport,
    *,
    role: ConnectorDomainRole,
) -> dict[str, tuple[MappedConnectorDomainAssignment, ...]]:
    """Collect fitted, unambiguous, source-matched assignments for one role."""
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    assignments_by_net: dict[str, list[MappedConnectorDomainAssignment]] = defaultdict(list)
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", maxsplit=1)[0]
        if (
            reference.casefold() in unpopulated
            or mapped.role != role
            or not mapped.voltage_domain
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        assignments_by_net[mapped.nets[0]].append(
            MappedConnectorDomainAssignment(
                pin=pin,
                native_net=mapped.nets[0],
                voltage_domain=mapped.voltage_domain,
                mapped_pin=mapped,
                interface_role=role,
            )
        )
    return {
        net: tuple(sorted(assignments, key=lambda item: (item.voltage_domain, item.pin)))
        for net, assignments in sorted(assignments_by_net.items())
    }
