"""Project-scoped connector signal/return contact distribution review."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal, localcontext

from .models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorPinRole,
    ConnectorReturnDistributionCoverageReport,
    ConnectorReturnDistributionEntry,
    ConnectorReturnDistributionMap,
    ConnectorReturnDistributionRequirement,
)


def _required_returns(signal_count: int, maximum_ratio: float) -> int:
    """Calculate the smallest integer return count that meets the authored ratio."""
    if signal_count == 0:
        return 0
    with localcontext() as context:
        context.prec = 50
        count = Decimal(signal_count) / Decimal(str(maximum_ratio))
        return int(count.to_integral_value(rounding=ROUND_CEILING))


def _incomplete_entry(
    requirement: ConnectorReturnDistributionRequirement,
    connector: ConnectorCoverageEntry | None,
    issues: tuple[str, ...],
) -> ConnectorReturnDistributionEntry:
    return ConnectorReturnDistributionEntry(
        id=requirement.id,
        connector_reference=None if connector is None else connector.reference,
        interface_id=requirement.interface_id,
        status="INCOMPLETE",
        signal_pin_count=0,
        return_pin_count=0,
        required_return_pin_count=0,
        minimum_signal_pin_count=requirement.minimum_signal_pin_count,
        maximum_signal_to_return_ratio=requirement.maximum_signal_to_return_ratio,
        basis=requirement.basis,
        issues=issues,
    )


def _entry(
    requirement: ConnectorReturnDistributionRequirement,
    connector: ConnectorCoverageEntry,
) -> ConnectorReturnDistributionEntry:
    if connector.status != "COVERED":
        return _incomplete_entry(
            requirement,
            connector,
            (
                (
                    f"Connector pin review is {connector.status}; complete its interface mapping "
                    "before counting contact roles"
                ),
                *connector.issues,
            ),
        )

    role_maps: dict[ConnectorPinRole, dict[str, str]] = {
        "signal": {},
        "return": {},
        "supply": {},
        "shield": {},
        "other": {},
    }
    unclassified: dict[str, str] = {}
    for pin in connector.mapped_pins:
        if pin.role is None:
            unclassified[pin.interface_pin_number] = pin.component_pin
        else:
            role_maps[pin.role][pin.interface_pin_number] = pin.component_pin
    if unclassified:
        return ConnectorReturnDistributionEntry(
            id=requirement.id,
            connector_reference=connector.reference,
            interface_id=requirement.interface_id,
            status="INCOMPLETE",
            signal_pin_map=dict(sorted(role_maps["signal"].items())),
            return_pin_map=dict(sorted(role_maps["return"].items())),
            supply_pin_map=dict(sorted(role_maps["supply"].items())),
            shield_pin_map=dict(sorted(role_maps["shield"].items())),
            other_pin_map=dict(sorted(role_maps["other"].items())),
            unclassified_pin_map=dict(sorted(unclassified.items())),
            signal_pin_count=len(role_maps["signal"]),
            return_pin_count=len(role_maps["return"]),
            required_return_pin_count=0,
            minimum_signal_pin_count=requirement.minimum_signal_pin_count,
            maximum_signal_to_return_ratio=requirement.maximum_signal_to_return_ratio,
            basis=requirement.basis,
            issues=(
                (
                    "Interface catalog must assign signal, return, supply, shield, or other role "
                    "to every mapped pin used by this threshold"
                ),
            ),
        )

    signal_count = len(role_maps["signal"])
    return_count = len(role_maps["return"])
    required_count = (
        _required_returns(signal_count, requirement.maximum_signal_to_return_ratio)
        if signal_count >= requirement.minimum_signal_pin_count
        else 0
    )
    ratio = None if return_count == 0 else signal_count / return_count
    if signal_count < requirement.minimum_signal_pin_count:
        status = "BELOW_SCOPE"
    elif ratio is None or ratio > requirement.maximum_signal_to_return_ratio:
        status = "OUT_OF_RANGE"
    else:
        status = "COMPLETE"
    return ConnectorReturnDistributionEntry(
        id=requirement.id,
        connector_reference=connector.reference,
        interface_id=requirement.interface_id,
        status=status,
        signal_pin_map=dict(sorted(role_maps["signal"].items())),
        return_pin_map=dict(sorted(role_maps["return"].items())),
        supply_pin_map=dict(sorted(role_maps["supply"].items())),
        shield_pin_map=dict(sorted(role_maps["shield"].items())),
        other_pin_map=dict(sorted(role_maps["other"].items())),
        signal_pin_count=signal_count,
        return_pin_count=return_count,
        required_return_pin_count=required_count,
        signal_to_return_ratio=ratio,
        minimum_signal_pin_count=requirement.minimum_signal_pin_count,
        maximum_signal_to_return_ratio=requirement.maximum_signal_to_return_ratio,
        basis=requirement.basis,
    )


def scan_connector_return_distribution_map(
    requirement_map: ConnectorReturnDistributionMap,
    connector_coverage: ConnectorCoverageReport | None,
    netlist_sha256: str | None,
) -> ConnectorReturnDistributionCoverageReport:
    """Compare authored ratios with explicitly mapped interface pin roles."""
    if connector_coverage is None:
        return ConnectorReturnDistributionCoverageReport(
            status="BLOCKED",
            issue="Source-bound connector interface coverage is unavailable for return-distribution review",
        )
    if netlist_sha256 is None:
        return ConnectorReturnDistributionCoverageReport(
            status="BLOCKED",
            issue="Source-bound native netlist hash is unavailable for return-distribution review",
        )
    if connector_coverage.interface_catalog_sha256 is None:
        return ConnectorReturnDistributionCoverageReport(
            status="BLOCKED",
            netlist_sha256=netlist_sha256,
            issue="Hash-bound interface catalog is unavailable for role-based contact review",
        )

    entries: list[ConnectorReturnDistributionEntry] = []
    for requirement in requirement_map.requirements:
        matching = tuple(
            item
            for item in connector_coverage.entries
            if item.interface_id is not None
            and item.interface_id.casefold() == requirement.interface_id.casefold()
        )
        if not matching:
            entries.append(
                _incomplete_entry(
                    requirement,
                    None,
                    (f"No reviewed connector is bound to interface {requirement.interface_id}",),
                )
            )
            continue
        entries.extend(_entry(requirement, connector) for connector in matching)

    return ConnectorReturnDistributionCoverageReport(
        status="INCOMPLETE" if any(item.status == "INCOMPLETE" for item in entries) else "COMPLETE",
        netlist_sha256=netlist_sha256,
        interface_catalog_sha256=connector_coverage.interface_catalog_sha256,
        entries=tuple(entries),
    )
