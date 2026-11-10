"""Synthetic mapped connector supply/return net-sharing cases."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)

INTERFACE_ID = "synthetic-supply-return-port"
INTERFACE_CATALOG_SHA256 = "e" * 64


def supply_return_netlist(
    *,
    supply_net: str = "AUX_SHARED_NODE",
    return_net: str = "AUX_SHARED_NODE",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one connector with independently controlled supply/return nets."""
    pins_by_net: dict[str, list[str]] = {}
    for pin, net in (("J1.1", supply_net), ("J1.2", return_net)):
        pins_by_net.setdefault(net, []).append(pin)
    return NetlistContract(
        components={},
        nets={name: tuple(pins) for name, pins in pins_by_net.items()},
        dnp_components=dnp,
        component_symbols={"J1": "Lint:GenericPort"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": "VBUS", "J1.2": "GND"},
        pin_electrical_types={"J1.1": "passive", "J1.2": "passive"},
    )


def supply_return_coverage(
    observed: NetlistContract,
    *,
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("supply", "return"),
    unconnected_pin_reasons: Mapping[str, str] | None = None,
) -> ConnectorCoverageReport:
    """Build complete source-matched role evidence for the synthetic connector."""
    interface_signals = ("SUPPLY_CONTACT", "RETURN_CONTACT")
    interface = InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal=interface_signals[0],
                role=roles[0],
                direction="input" if roles[0] == "supply" else "passive",
                voltage_domain="synthetic-5v" if roles[0] == "supply" else "synthetic-ground",
                mating=interface_signals[0],
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal=interface_signals[1],
                role=roles[1],
                direction="input" if roles[1] == "supply" else "passive",
                voltage_domain="synthetic-5v" if roles[1] == "supply" else "synthetic-ground",
                mating=interface_signals[1],
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic independently reviewed connector supply/return map",
        interface_id=interface.id,
        pin_map={"1": "1", "2": "2"},
        unconnected_pin_reasons=unconnected_pin_reasons or {},
    )
    return evaluate_connector_coverage(
        observed,
        (interface.id,),
        (review,),
        interfaces={interface.id: interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256=INTERFACE_CATALOG_SHA256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered the complete connector inventory"
        ),
    )


def supply_return_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate the typed design-lint service for the synthetic role map."""
    current_coverage = coverage if coverage is not None else supply_return_coverage(observed)
    project_id = "synthetic-mapped-supply-return-sharing"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    report = evaluate(
        project_id,
        coach,
        policy if policy is not None else DesignLintPolicy(),
        connector_coverage=current_coverage,
    )
    return report, current_coverage
