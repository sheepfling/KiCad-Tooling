"""Synthetic mapped connector supply-to-signal net-sharing cases."""

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

INTERFACE_ID = "synthetic-supply-signal-port"
INTERFACE_CATALOG_SHA256 = "d" * 64


def supply_signal_netlist(
    *,
    supply_net: str = "SHARED_NET",
    signal_net: str = "SHARED_NET",
    supply_function: str = "Pin_1",
    signal_function: str = "Pin_2",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one two-contact connector with independently controlled assignments."""
    pins_by_net: dict[str, list[str]] = {}
    for pin, net in (("J1.1", supply_net), ("J1.2", signal_net)):
        pins_by_net.setdefault(net, []).append(pin)
    return NetlistContract(
        components={},
        nets={name: tuple(pins) for name, pins in pins_by_net.items()},
        dnp_components=dnp,
        component_symbols={"J1": "Lint:GenericPort"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": supply_function, "J1.2": signal_function},
        pin_electrical_types={"J1.1": "passive", "J1.2": "passive"},
    )


def supply_signal_coverage(
    observed: NetlistContract,
    *,
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("supply", "signal"),
    unconnected_pin_reasons: Mapping[str, str] | None = None,
) -> ConnectorCoverageReport:
    """Build a complete independently authored map for the synthetic connector."""
    pins = tuple(
        InterfacePin(
            number=str(index),
            signal=name,
            role=roles[index - 1],
            direction="input",
            voltage_domain="synthetic-voltage-domain",
            mating=name,
            orientation="straight",
            mechanical_clearance="synthetic",
        )
        for index, name in enumerate(("SUPPLY_IN", "DATA_IN"), start=1)
    )
    interface = InterfaceRecord(id=INTERFACE_ID, revision="synthetic-1", pins=pins)
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic independently reviewed connector pin map",
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


def supply_signal_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate the normal typed service for a synthetic supply/signal map."""
    current_coverage = coverage if coverage is not None else supply_signal_coverage(observed)
    project_id = "synthetic-mapped-supply-signal-sharing"
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
