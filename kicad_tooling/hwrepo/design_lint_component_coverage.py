"""Project-authored component topology map coverage resolution."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_return_distribution import scan_connector_return_distribution_map
from .crystal_networks import scan_crystal_network_map
from .i2c_addressing import scan_i2c_address_map
from .models import (
    ConnectorCoverageReport,
    ConnectorReturnDistributionCoverageReport,
    ConnectorReturnDistributionMap,
    CrystalNetworkCoverageReport,
    CrystalNetworkMap,
    DesignLintPolicy,
    Digest,
    I2cAddressCoverageReport,
    I2cAddressMap,
    NetlistContract,
    RcFilterCoverageReport,
    RcFilterMap,
    RegulatorFeedbackCoverageReport,
    RegulatorFeedbackMap,
)
from .rc_filters import scan_rc_filter_map
from .regulator_feedback import scan_regulator_feedback_map


@dataclass(frozen=True)
class ComponentMapCoverage:
    """Coverage reports for authored component-level topology maps."""

    i2c_address: I2cAddressCoverageReport
    crystal_network: CrystalNetworkCoverageReport
    regulator_feedback: RegulatorFeedbackCoverageReport
    rc_filter: RcFilterCoverageReport
    connector_return_distribution: ConnectorReturnDistributionCoverageReport


def resolve_component_map_coverage(
    *,
    policy: DesignLintPolicy,
    observed: NetlistContract,
    netlist_sha256: Digest | None,
    connector_coverage: ConnectorCoverageReport | None,
    i2c_address_coverage: I2cAddressCoverageReport | None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None,
    rc_filter_coverage: RcFilterCoverageReport | None,
    connector_return_distribution_coverage: ConnectorReturnDistributionCoverageReport | None,
) -> ComponentMapCoverage:
    """Evaluate each configured map against the exact source-bound netlist."""
    if i2c_address_coverage is None:
        address_map: I2cAddressMap | None = policy.i2c_address_map
        if address_map is None:
            i2c_address_coverage = I2cAddressCoverageReport()
        elif netlist_sha256 is None:
            i2c_address_coverage = I2cAddressCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for I2C address review",
            )
        else:
            try:
                i2c_address_coverage = scan_i2c_address_map(address_map, observed, netlist_sha256)
            except (OSError, ValueError, TypeError) as exc:
                i2c_address_coverage = I2cAddressCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=netlist_sha256,
                    issue=f"Could not compare the I2C address map with native evidence: {exc}",
                )
    if crystal_network_coverage is None:
        network_map: CrystalNetworkMap | None = policy.crystal_network_map
        if network_map is None:
            crystal_network_coverage = CrystalNetworkCoverageReport()
        elif netlist_sha256 is None:
            crystal_network_coverage = CrystalNetworkCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for crystal network review",
            )
        else:
            try:
                crystal_network_coverage = scan_crystal_network_map(
                    network_map, observed, netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                crystal_network_coverage = CrystalNetworkCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=netlist_sha256,
                    issue=f"Could not compare the crystal network map with native evidence: {exc}",
                )
    if regulator_feedback_coverage is None:
        feedback_map: RegulatorFeedbackMap | None = policy.regulator_feedback_map
        if feedback_map is None:
            regulator_feedback_coverage = RegulatorFeedbackCoverageReport()
        elif netlist_sha256 is None:
            regulator_feedback_coverage = RegulatorFeedbackCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for regulator feedback review",
            )
        else:
            try:
                regulator_feedback_coverage = scan_regulator_feedback_map(
                    feedback_map, observed, netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                regulator_feedback_coverage = RegulatorFeedbackCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=netlist_sha256,
                    issue=f"Could not compare the regulator feedback map with native evidence: {exc}",
                )
    if rc_filter_coverage is None:
        filter_map: RcFilterMap | None = policy.rc_filter_map
        if filter_map is None:
            rc_filter_coverage = RcFilterCoverageReport()
        elif netlist_sha256 is None:
            rc_filter_coverage = RcFilterCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for RC filter review",
            )
        else:
            try:
                rc_filter_coverage = scan_rc_filter_map(filter_map, observed, netlist_sha256)
            except (OSError, ValueError, TypeError) as exc:
                rc_filter_coverage = RcFilterCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=netlist_sha256,
                    issue=f"Could not compare the RC filter map with native evidence: {exc}",
                )
    if connector_return_distribution_coverage is None:
        distribution_map: ConnectorReturnDistributionMap | None = (
            policy.connector_return_distribution_map
        )
        if distribution_map is None:
            connector_return_distribution_coverage = ConnectorReturnDistributionCoverageReport()
        else:
            try:
                connector_return_distribution_coverage = scan_connector_return_distribution_map(
                    distribution_map,
                    connector_coverage,
                    netlist_sha256,
                )
            except (OSError, ValueError, TypeError) as exc:
                connector_return_distribution_coverage = ConnectorReturnDistributionCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=netlist_sha256,
                    interface_catalog_sha256=(
                        None
                        if connector_coverage is None
                        else connector_coverage.interface_catalog_sha256
                    ),
                    issue=(
                        "Could not compare the connector return-distribution map with "
                        f"source-bound evidence: {exc}"
                    ),
                )
    return ComponentMapCoverage(
        i2c_address=i2c_address_coverage,
        crystal_network=crystal_network_coverage,
        regulator_feedback=regulator_feedback_coverage,
        rc_filter=rc_filter_coverage,
        connector_return_distribution=connector_return_distribution_coverage,
    )
