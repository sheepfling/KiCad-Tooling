"""Native acceptance for USB topologies without project-authored data maps."""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256

from .ci_hosted_support import HostedLog
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate
from .hwrepo.models import DesignLintPolicy
from .hwrepo.netlist_contract_models import NetlistContract


def validate_usb_unmapped_topology_fixtures(
    *,
    observed_contracts: Mapping[tuple[str, str], NetlistContract],
    source_hashes: Mapping[str, str],
    raw_hashes: Mapping[tuple[str, str], str],
    normalized_hashes: Mapping[tuple[str, str], str],
    project: str,
    kicad_version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Verify inline-path and shared-data-net candidates from native exports."""
    cases = (
        (
            "inline-component-control",
            "inline-component-unmapped-coverage",
            "U2",
            "split_endpoint_nets",
            "J1 / U1: unmapped USB multi-pin topology port 1 (U2)",
        ),
        (
            "protection-shunt-split-reference",
            "protection-shunt-unmapped-topology",
            "U6",
            "shared_data_net_attachment",
            "J1 / U1: unmapped USB multi-pin data attachment port 1 (U6)",
        ),
    )
    for case, stage, component, topology, expected_subject in cases:
        observed = observed_contracts[(case, "first")]
        report = evaluate(
            f"synthetic-usb-unmapped-{component.casefold()}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-usb-unmapped-{component.casefold()}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, "first")],
            ),
            DesignLintPolicy(),
        )
        coverage = report.usb_peer_reference_coverage
        unsupported = () if coverage is None else coverage.unsupported_multi_pin_paths or ()
        findings = tuple(
            item
            for item in report.findings
            if item.rule_id == "bus.usb_unmapped_multi_pin_topology"
        )
        if (
            coverage is None
            or coverage.supported_data_path_count != 0
            or len(unsupported) != 1
            or unsupported[0].topology != topology
            or unsupported[0].component_reference != component
            or len(findings) != 1
            or findings[0].subject != expected_subject
            or any(
                item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
                for item in report.findings
            )
        ):
            raise ValueError(f"Native {case} did not retain its exact unmapped topology review")
        if topology == "split_endpoint_nets" and (
            unsupported[0].positive_connector_net,
            unsupported[0].positive_phy_net,
            unsupported[0].negative_connector_net,
            unsupported[0].negative_phy_net,
        ) != ("USB_DP_PORT", "USB_DP_PHY", "USB_DM_PORT", "USB_DM_PHY"):
            raise ValueError("Native inline topology omitted exact U2 endpoint-side nets")
        if topology == "shared_data_net_attachment" and (
            unsupported[0].positive_connector_net.casefold()
            != unsupported[0].positive_phy_net.casefold()
            or unsupported[0].negative_connector_net.casefold()
            != unsupported[0].negative_phy_net.casefold()
        ):
            raise ValueError("Native shunt topology omitted its two shared USB data nets")
        normalized = json.dumps(
            observed.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if sha256(normalized).hexdigest() != normalized_hashes[(case, "first")]:
            raise ValueError(f"Native {case} replay used a different normalized netlist")
        log.event(
            f"usb-data-path-fixture/{stage}",
            "PASS",
            project=project,
            kicad_version=kicad_version,
            image=image,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            coverage_status=coverage.status,
            lint_status=report.status,
            supported_data_paths=coverage.supported_data_path_count,
            unsupported_component_references=component,
            usb_reference_findings="none",
            usb_unmapped_topology_findings=findings[0].subject,
        )
