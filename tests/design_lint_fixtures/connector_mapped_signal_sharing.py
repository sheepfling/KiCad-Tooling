"""Synthetic connector signal-sharing netlists and source-matched maps."""

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

INTERFACE_ID = "synthetic-distinct-signal-port"
INTERFACE_CATALOG_SHA256 = "c" * 64


def signal_sharing_netlist(
    *,
    first_net: str = "SHARED_SIGNAL_NET",
    second_net: str = "SHARED_SIGNAL_NET",
    first_function: str = "Pin_1",
    second_function: str = "Pin_2",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one generic two-contact connector with controlled net assignments."""
    pins_by_net: dict[str, list[str]] = {}
    for pin, net in (("J1.1", first_net), ("J1.2", second_net)):
        pins_by_net.setdefault(net, []).append(pin)
    return NetlistContract(
        components={},
        nets={name: tuple(pins) for name, pins in pins_by_net.items()},
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:GenericPort"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": first_function, "J1.2": second_function},
        pin_electrical_types={"J1.1": "passive", "J1.2": "passive"},
    )


def signal_sharing_coverage(
    observed: NetlistContract,
    *,
    signal_names: tuple[str, str] = ("CONTROL_A", "CONTROL_B"),
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("signal", "signal"),
    unconnected_pin_reasons: Mapping[str, str] | None = None,
) -> ConnectorCoverageReport:
    """Build complete project-authored connector coverage for the synthetic netlist."""
    pins = tuple(
        InterfacePin(
            number=str(index),
            signal=signal,
            role=roles[index - 1],
            direction="bidirectional" if roles[index - 1] == "signal" else "passive",
            voltage_domain="logic-3v3" if roles[index - 1] == "signal" else "signal-return",
            mating=signal,
            orientation="straight",
            mechanical_clearance="synthetic",
        )
        for index, signal in enumerate(signal_names, start=1)
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


def signal_sharing_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate the normal typed design-lint service for the synthetic cases."""
    current_coverage = coverage if coverage is not None else signal_sharing_coverage(observed)
    project_id = "synthetic-mapped-signal-sharing"
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
