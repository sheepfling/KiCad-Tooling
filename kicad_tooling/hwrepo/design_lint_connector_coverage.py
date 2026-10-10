"""Connector inventory and external-protection coverage from project contracts."""

from __future__ import annotations

from pathlib import Path

from .connector_coverage import evaluate as evaluate_connector_coverage
from .contracts import read_model, repo_path
from .discovery import ProjectConfig, load_registry
from .electrical import load_analysis
from .evidence import digest
from .external_protection import evaluate as evaluate_external_protection
from .models import (
    ConnectorCoverageReport,
    DesignLintPolicy,
    ExternalProtectionCoverageReport,
    InterfaceRecord,
    InterfacesCatalog,
    NetlistContract,
    UsbCAnalysis,
    UsbCProtectionAnalysis,
)


def connector_coverage_from_project(
    root: Path, config: ProjectConfig, observed: NetlistContract
) -> ConnectorCoverageReport:
    """Bind project connector reviews to the configured interface catalog when used."""
    needs_catalog = bool(config.interfaces) or any(
        review.disposition == "interface" for review in config.connector_reviews
    )
    if not needs_catalog:
        return evaluate_connector_coverage(
            observed,
            config.interfaces,
            config.connector_reviews,
            inventory_review=config.connector_inventory_review,
        )

    registry = load_registry(root)
    catalog_relative = registry.catalogs.interfaces
    catalog_path = repo_path(root, catalog_relative)
    catalog_hash: str | None = None
    catalog: InterfacesCatalog | None = None
    issues: list[str] = []
    try:
        catalog_hash = digest(catalog_path)
        catalog = read_model(catalog_path, InterfacesCatalog)
        if digest(catalog_path) != catalog_hash:
            issues.append("Interface catalog changed during connector coverage inspection")
    except (OSError, ValueError, TypeError) as exc:
        issues.append(f"Could not read the configured interface catalog: {exc}")

    interfaces: dict[str, InterfaceRecord] = {}
    if catalog is not None:
        for record in catalog.interfaces:
            if record.id in interfaces:
                issues.append(f"Interface catalog repeats ID {record.id}")
            else:
                interfaces[record.id] = record
        missing = sorted(set(config.interfaces) - interfaces.keys())
        issues.extend(
            f"Project interface ID is absent from the catalog: {identifier}"
            for identifier in missing
        )

    return evaluate_connector_coverage(
        observed,
        config.interfaces,
        config.connector_reviews,
        interfaces=interfaces,
        interface_catalog_path=catalog_relative,
        interface_catalog_sha256=catalog_hash,
        catalog_issues=tuple(issues),
        inventory_review=config.connector_inventory_review,
    )


def usb_c_protection_scope(
    root: Path,
    config: ProjectConfig,
    connector_coverage: ConnectorCoverageReport,
) -> tuple[dict[str, str], str | None, str | None]:
    """Return connector pins whose protection disposition is owned by USB-C review."""
    if config.electrical is None:
        return {}, None, None
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during external-protection inspection")
    handled: dict[str, str] = {}
    if contract is None or not isinstance(contract.usb_c, UsbCAnalysis):
        return handled, relative_path, expected_digest
    for port in contract.usb_c.ports:
        prefix = f"{port.connector}.".casefold()
        handled[port.cc1.connector_pin] = port.cc1.net
        handled[port.cc2.connector_pin] = port.cc2.net
        handled.update(
            {
                assignment.pin: assignment.net
                for assignment in port.vbus_pins
                if assignment.pin.casefold().startswith(prefix)
            }
        )
        handled.update(
            {pin: port.ground_net for pin in port.ground_pins if pin.casefold().startswith(prefix)}
        )
    handled.update(mapped_usb_c_protection_pins(contract.usb_c, connector_coverage))
    return handled, relative_path, expected_digest


def mapped_usb_c_protection_pins(
    analysis: UsbCAnalysis,
    connector_coverage: ConnectorCoverageReport,
) -> dict[str, str]:
    """Map covered connector pins to exact non-reference nets in USB-C protector maps."""
    handled: dict[str, str] = {}
    for port in analysis.ports:
        if not isinstance(port.protection, UsbCProtectionAnalysis):
            continue
        reference_nets = {port.ground_net, port.vbus_net, port.cc1.net, port.cc2.net}
        protected_signal_nets = {
            assignment.net
            for component in port.protection.components
            for assignment in component.pins
            if assignment.net not in reference_nets
        }
        for connector in connector_coverage.entries:
            if connector.reference.casefold() != port.connector.casefold():
                continue
            if connector.status != "COVERED":
                continue
            for pin in connector.mapped_pins:
                if len(pin.nets) == 1 and pin.nets[0] in protected_signal_nets:
                    handled[pin.component_pin] = pin.nets[0]
    return handled


def external_protection_coverage_from_project(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    observed: NetlistContract,
    connector_coverage: ConnectorCoverageReport,
    netlist_sha256: str | None,
) -> ExternalProtectionCoverageReport:
    """Bind authored protection maps and reused USB-C dispositions to native evidence."""
    has_reviewed_interface_pins = any(
        entry.status == "COVERED" and entry.mapped_pins for entry in connector_coverage.entries
    )
    if policy.external_protection_map is None and not has_reviewed_interface_pins:
        return evaluate_external_protection(None, observed, None, netlist_sha256)
    try:
        handled, contract_path, contract_hash = usb_c_protection_scope(
            root, config, connector_coverage
        )
    except (OSError, ValueError, TypeError) as exc:
        return ExternalProtectionCoverageReport(
            status="BLOCKED",
            netlist_sha256=netlist_sha256,
            issue=(
                "Could not inspect the electrical contract for duplicate USB-C protection "
                f"coverage: {exc}"
            ),
        )
    return evaluate_external_protection(
        policy.external_protection_map,
        observed,
        connector_coverage,
        netlist_sha256,
        handled_by_existing_contract=handled,
        electrical_contract_path=contract_path,
        electrical_contract_sha256=contract_hash,
    )
