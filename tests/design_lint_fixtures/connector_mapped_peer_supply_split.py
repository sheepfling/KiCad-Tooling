"""Synthetic mapped peer supplies with independently controlled net assignments."""

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

ROLE = Literal["supply", "signal", "return", "shield", "other"]
INTERFACE_CATALOG_SHA256 = "e" * 64
RULE_ID = "connector.mapped_named_peer_supply_split_nets"


def mapped_peer_supply_netlist(
    *,
    assignments: tuple[tuple[str, ...], ...] = (("NODE_ALPHA",), ("NODE_BETA",)),
    functions: tuple[str, ...] = ("CONTACT_A", "CONTACT_B", "CONTACT_C"),
    symbols: tuple[str, ...] = (
        "Lint:NamedSupplyA",
        "Lint:NamedSupplyB",
        "Lint:NamedSupplyC",
    ),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build unlike synthetic connector symbols with named passive contacts."""
    references = tuple(f"J{index}" for index in range(1, len(assignments) + 1))
    if len(references) < 2 or len(functions) < len(references) or len(symbols) < len(references):
        raise ValueError("Peer supply fixtures need at least two fully described connectors")
    pins_by_net: dict[str, list[str]] = {}
    for reference, pin_nets in zip(references, assignments, strict=True):
        for net in pin_nets:
            pins_by_net.setdefault(net, []).append(f"{reference}.1")
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=f"Synthetic power port {index}",
                footprint=f"Synthetic:PowerPort{index}",
            )
            for index, reference in enumerate(references, start=1)
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


def mapped_peer_supply_coverage(
    observed: NetlistContract,
    *,
    domains: tuple[str, ...] = ("board-input", "board-input", "board-input"),
    groups: tuple[str | None, ...] = ("external-power", "external-power", "external-power"),
    roles: tuple[ROLE, ...] = ("supply", "supply", "supply"),
    opens: tuple[str | None, ...] = (None, None, None),
    catalog_digest: str | None = INTERFACE_CATALOG_SHA256,
) -> ConnectorCoverageReport:
    """Build complete source-matched maps and optional supply-comparison scopes."""
    references = tuple(sorted(observed.component_symbols, key=lambda item: (item.casefold(), item)))
    if not all(len(items) >= len(references) for items in (domains, groups, roles, opens)):
        raise ValueError("Peer supply metadata must describe every connector reference")

    interfaces: dict[str, InterfaceRecord] = {}
    reviews: list[ConnectorInterfaceReview] = []
    for index, reference in enumerate(references):
        interface_id = f"synthetic-{reference.casefold()}-supply-port"
        interface = InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal=f"POWER_{reference}",
                    role=roles[index],
                    direction="passive",
                    voltage_domain=domains[index],
                    mating=f"POWER_{reference}",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        interfaces[interface_id] = interface
        group = groups[index] if roles[index] == "supply" else None
        reviews.append(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis="Synthetic independently reviewed connector supply map",
                interface_id=interface_id,
                pin_map={"1": "1"},
                unconnected_pin_reasons={"1": opens[index]} if opens[index] else {},
                supply_comparison_group=group,
                supply_comparison_basis=(
                    "Synthetic reviewer selected this supply comparison group"
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
            basis="Synthetic review covered every connector reference"
        ),
    )


def mapped_peer_supply_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Run the normal typed design-lint service against synthetic peer supplies."""
    current_coverage = mapped_peer_supply_coverage(observed) if coverage is None else coverage
    project_id = "synthetic-mapped-named-peer-supply-split"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    return (
        evaluate(
            project_id, coach, policy or DesignLintPolicy(), connector_coverage=current_coverage
        ),
        current_coverage,
    )
