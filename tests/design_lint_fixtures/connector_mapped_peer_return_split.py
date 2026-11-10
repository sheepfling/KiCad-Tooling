"""Synthetic source-mapped peer returns assigned to split schematic nets."""

from __future__ import annotations

from hashlib import sha256
from typing import Literal

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)

RULE_ID = "connector.mapped_named_peer_return_split_nets"
INTERFACE_CATALOG_SHA256 = "d" * 64


def mapped_peer_return_netlist(
    *,
    assignments: tuple[tuple[str, ...], ...] = (
        ("RETURN_SEGMENT_A",),
        ("RETURN_SEGMENT_B",),
    ),
    functions: tuple[str, ...] = ("AUX_REF", "COMMON_REF", "CONTACT_C"),
    symbols: tuple[str, ...] = (
        "Connector_Generic:Conn_01x01",
        "Connector_Generic:Conn_01x01",
        "Connector_Generic:Conn_01x01",
    ),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one-pin connector peers with independently controlled assignments."""
    references = tuple(f"J{index}" for index in range(1, len(assignments) + 1))
    if len(references) < 2 or len(functions) < len(references) or len(symbols) < len(references):
        raise ValueError("Peer return fixtures require at least two complete connector references")
    pins_by_net: dict[str, list[str]] = {}
    for reference, pin_nets in zip(references, assignments, strict=True):
        for net in pin_nets:
            pins_by_net.setdefault(net, []).append(f"{reference}.1")
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic peer port", footprint="Synthetic:1Pin")
            for reference in references
        },
        nets={name: tuple(sorted(pins)) for name, pins in sorted(pins_by_net.items())},
        dnp_components=dnp,
        component_symbols={reference: symbols[index] for index, reference in enumerate(references)},
        component_pin_numbers={reference: ("1",) for reference in references},
        pin_functions={
            f"{reference}.1": functions[index] for index, reference in enumerate(references)
        },
        pin_electrical_types={f"{reference}.1": "passive" for reference in references},
    )


def mapped_peer_return_coverage(
    observed: NetlistContract,
    *,
    domains: tuple[str, ...] = ("signal-return", "signal-return", "signal-return"),
    groups: tuple[str | None, ...] = (
        "external-returns",
        "external-returns",
        "external-returns",
    ),
    roles: tuple[Literal["return", "signal", "supply"], ...] = ("return", "return", "return"),
    opens: tuple[str | None, ...] = (None, None, None),
    catalog_digest: str | None = INTERFACE_CATALOG_SHA256,
) -> ConnectorCoverageReport:
    """Build complete authored interface and return-comparison coverage."""
    interfaces: dict[str, InterfaceRecord] = {}
    reviews: list[ConnectorInterfaceReview] = []
    references = tuple(sorted(observed.component_symbols, key=lambda item: (item.casefold(), item)))
    if not all(len(items) >= len(references) for items in (domains, groups, roles, opens)):
        raise ValueError("Peer return coverage metadata must cover each connector reference")
    for index, reference in enumerate(references):
        interface_id = f"synthetic-{reference.casefold()}-return-port"
        interface = InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal=f"RETURN_{reference}",
                    role=roles[index],
                    direction="passive",
                    voltage_domain=domains[index],
                    mating=f"RETURN_{reference}",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        interfaces[interface_id] = interface
        group = groups[index] if roles[index] == "return" else None
        reviews.append(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis="Synthetic independently reviewed connector pinout",
                interface_id=interface_id,
                pin_map={"1": "1"},
                unconnected_pin_reasons={"1": opens[index]} if opens[index] else {},
                return_comparison_group=group,
                return_comparison_basis=(
                    "Synthetic reviewer selected these return peers for comparison"
                    if group is not None
                    else None
                ),
            )
        )
    return evaluate_connector_coverage(
        observed,
        tuple(sorted(interfaces)),
        tuple(reviews),
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256=catalog_digest,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered both connector references"
        ),
    )


def mapped_peer_return_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Run the public typed design-lint evaluator on synthetic peer evidence."""
    current_coverage = coverage or mapped_peer_return_coverage(observed)
    project_id = "synthetic-mapped-peer-return-split"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    report = evaluate(
        project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=current_coverage,
    )
    return report, current_coverage
