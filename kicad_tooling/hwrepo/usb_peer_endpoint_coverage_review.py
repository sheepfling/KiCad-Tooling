"""Review recognized USB endpoint groups left outside supported path coverage."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_data_path_models import usb_data_path_map_sha256
from .usb_peer_reference_types import (
    UsbPeerEndpointGroupCoverage,
    UsbPeerReferenceCoverage,
    UsbPeerReferencePathCoverage,
    UsbPeerReferenceScan,
)

RULE_ID: DesignLintRuleId = "bus.usb_endpoint_path_coverage_incomplete"


@dataclass(frozen=True, slots=True)
class UsbEndpointPathCoverageEvidence:
    """The exact recognized groups and source map behind one coverage prompt."""

    coverage: UsbPeerReferenceCoverage
    data_path: UsbDataPathCandidateInputs
    unassessed_groups: tuple[UsbPeerEndpointGroupCoverage, ...]


def _group_key(group: UsbPeerEndpointGroupCoverage) -> tuple[str, str, str | None, str]:
    return (
        group.endpoint_role,
        group.reference.casefold(),
        group.port_group,
        group.signal_family,
    )


def _compatible_port_group(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _matches_endpoint(
    group: UsbPeerEndpointGroupCoverage,
    *,
    role: str,
    reference: str,
    port_group: str | None,
    signal_family: str,
) -> bool:
    return (
        group.endpoint_role == role
        and group.reference.casefold() == reference.casefold()
        and group.signal_family == signal_family
        and _compatible_port_group(group.port_group, port_group)
    )


def _mapped_endpoint_groups(
    coverage: UsbPeerReferenceCoverage, data_path: UsbDataPathCandidateInputs
) -> set[tuple[str, str, str | None, str]]:
    path_map = data_path.authored_map
    if path_map is None:
        return set()
    mapped: set[tuple[str, str, str | None, str]] = set()
    for interface in path_map.interfaces:
        connector_groups = tuple(
            group
            for group in coverage.endpoint_groups
            if group.endpoint_role == "connector"
            and group.reference.casefold() == interface.connector_reference.casefold()
            and group.signal_family == "USB 2.0 data"
            and _compatible_port_group(group.port_group, interface.data_port_group)
        )
        phy_groups = tuple(
            group
            for group in coverage.endpoint_groups
            if group.endpoint_role == "phy"
            and group.reference.casefold() == interface.phy_reference.casefold()
            and group.signal_family == "USB 2.0 data"
            and _compatible_port_group(group.port_group, interface.data_port_group)
        )
        for connector_group in connector_groups:
            for phy_group in phy_groups:
                if _compatible_port_group(connector_group.port_group, phy_group.port_group):
                    mapped.update((_group_key(connector_group), _group_key(phy_group)))
    for interface in path_map.superspeed_interfaces:
        connector_groups = tuple(
            group
            for group in coverage.endpoint_groups
            if group.endpoint_role == "connector"
            and group.reference.casefold() == interface.connector_reference.casefold()
            and group.signal_family == interface.connector_signal_family
        )
        phy_groups = tuple(
            group
            for group in coverage.endpoint_groups
            if group.endpoint_role == "phy"
            and group.reference.casefold() == interface.phy_reference.casefold()
            and group.signal_family == interface.phy_signal_family
        )
        if connector_groups and phy_groups:
            mapped.update(_group_key(group) for group in (*connector_groups, *phy_groups))
    return mapped


def _covered_endpoint_groups(
    coverage: UsbPeerReferenceCoverage, data_path: UsbDataPathCandidateInputs
) -> set[tuple[str, str, str | None, str]]:
    covered = _mapped_endpoint_groups(coverage, data_path)
    for path in coverage.path_entries:
        for group in coverage.endpoint_groups:
            connector_match = _matches_endpoint(
                group,
                role="connector",
                reference=path.connector_reference,
                port_group=path.data_link.port_group,
                signal_family=path.data_link.connector_signal_family,
            )
            phy_match = _matches_endpoint(
                group,
                role="phy",
                reference=path.phy_reference,
                port_group=path.data_link.port_group,
                signal_family=path.data_link.phy_signal_family,
            )
            if connector_match or phy_match:
                covered.add(_group_key(group))
    for path in coverage.unsupported_multi_pin_paths:
        for group in coverage.endpoint_groups:
            connector_match = _matches_endpoint(
                group,
                role="connector",
                reference=path.connector_reference,
                port_group=path.port_group,
                signal_family="USB 2.0 data",
            )
            phy_match = _matches_endpoint(
                group,
                role="phy",
                reference=path.phy_reference,
                port_group=path.port_group,
                signal_family="USB 2.0 data",
            )
            if connector_match or phy_match:
                covered.add(_group_key(group))
    return covered


def _group_label(group: UsbPeerEndpointGroupCoverage) -> str:
    port = f", port {group.port_group}" if group.port_group is not None else ""
    return f"{group.endpoint_role} {group.reference} ({group.signal_family}{port}; {group.disposition})"


def _path_label(path: UsbPeerReferencePathCoverage) -> str:
    port = f", port {path.data_link.port_group}" if path.data_link.port_group is not None else ""
    return (
        f"{path.connector_reference} -> {path.phy_reference} "
        f"({path.data_link.connector_signal_family}{port})"
    )


def _project_usb_endpoint_path_coverage(
    source: UsbEndpointPathCoverageEvidence,
) -> CandidateEvidenceProjection:
    evidence: dict[str, tuple[str, ...]] = {
        "unassessed_USB_endpoint_groups": tuple(
            _group_label(item) for item in source.unassessed_groups
        ),
        "supported_USB_peer_paths": tuple(
            _path_label(item) for item in source.coverage.path_entries
        ),
    }
    map_sha256 = usb_data_path_map_sha256(source.data_path.authored_map)
    if map_sha256 is not None:
        evidence["USB_data_path_map_SHA-256"] = (map_sha256,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_path_source_SHA-256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UsbEndpointPathCoverageCandidate(Candidate):
    """A stable REVIEW prompt backed by exact USB endpoint scan evidence."""

    source_evidence: UsbEndpointPathCoverageEvidence

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_usb_endpoint_path_coverage(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB endpoint coverage fields must match their typed evidence")


def usb_endpoint_path_coverage_candidates(
    scan: UsbPeerReferenceScan,
    data_path: UsbDataPathCandidateInputs,
) -> tuple[Candidate, ...]:
    """Prompt when a recognized active USB connector group remains unassessed."""
    coverage = scan.coverage
    active_connectors = tuple(
        item
        for item in coverage.endpoint_groups
        if item.endpoint_role == "connector" and item.disposition != "DNP"
    )
    if not active_connectors:
        return ()
    covered = _covered_endpoint_groups(coverage, data_path)
    unassessed = tuple(
        item
        for item in coverage.endpoint_groups
        if item.disposition != "DNP" and _group_key(item) not in covered
    )
    if not unassessed:
        return ()
    source = UsbEndpointPathCoverageEvidence(
        coverage=coverage,
        data_path=data_path,
        unassessed_groups=unassessed,
    )
    projection = _project_usb_endpoint_path_coverage(source)
    return (
        UsbEndpointPathCoverageCandidate(
            rule_id=projection.rule_id,
            subject=f"USB path coverage: {len(unassessed)} endpoint group(s) unassessed",
            message=(
                "The USB analyzer recognized active endpoint groups that are not included in a "
                "supported connector-to-PHY path or an exact authored map. Review their intended "
                "role and path, add the applicable project map, or document why the topology is "
                "outside this analyzer. This prompt does not infer a missing connection, require "
                "a common reference, or establish an electrical defect."
            ),
            evidence=projection.evidence,
            source_evidence=source,
        ),
    )
