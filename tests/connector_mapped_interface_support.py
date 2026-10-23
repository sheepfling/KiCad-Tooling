"""Shared synthetic source-matched connector-interface coverage builders."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.models import InterfacePin, InterfaceRecord, NetlistContract

CATALOG_SHA256 = "b" * 64
INTERFACE_ID = "synthetic-connector-interface"


def interface_record(*, target_role: ConnectorPinRole = "signal") -> InterfaceRecord:
    role_fields = {
        "signal": ("UART_RX", "input", "logic-3v3", "UART_TX"),
        "return": ("SIGNAL_RETURN", "passive", "signal-return", "SIGNAL_RETURN"),
        "supply": ("SUPPLY", "passive", "logic-supply", "SUPPLY"),
        "shield": ("CHASSIS_SHIELD", "passive", "chassis", "CHASSIS_BOND"),
        "other": ("OTHER", "passive", "unspecified", "OTHER"),
    }
    target_signal, direction, voltage_domain, mating = role_fields[target_role]
    return InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="UART_TX",
                role="signal",
                direction="output",
                voltage_domain="logic-3v3",
                mating="UART_RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal=target_signal,
                role=target_role,
                direction=direction,
                voltage_domain=voltage_domain,
                mating=mating,
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="3",
                signal="SIGNAL_RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="SIGNAL_RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def interface_coverage(
    source: NetlistContract,
    *,
    target_role: ConnectorPinRole = "signal",
    unconnected_reason: str | None = None,
    pin_numbers: tuple[str, ...] = ("1", "2", "3"),
) -> ConnectorCoverageReport:
    interface = interface_record(target_role=target_role)
    interface = interface.model_copy(
        update={"pins": tuple(pin for pin in interface.pins if str(pin.number) in pin_numbers)}
    )
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic independently reviewed connector pinout",
        interface_id=interface.id,
        pin_map={number: number for number in pin_numbers},
        unconnected_pin_reasons=({} if unconnected_reason is None else {"2": unconnected_reason}),
    )
    return evaluate_connector_coverage(
        source,
        (interface.id,),
        (review,),
        interfaces={interface.id: interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256=CATALOG_SHA256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered the complete connector inventory"
        ),
    )
