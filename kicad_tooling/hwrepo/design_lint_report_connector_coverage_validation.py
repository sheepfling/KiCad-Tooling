from __future__ import annotations

from .connector_peer_pin_models import ConnectorPeerPinHeuristicCoverage
from .design_lint_finding_models import DesignLintFinding
from .model_primitives import Digest


def validate_connector_peer_pin_coverage(
    *,
    netlist_sha256: Digest | None,
    findings: tuple[DesignLintFinding, ...],
    connector_peer_pin_coverage: ConnectorPeerPinHeuristicCoverage | None,
) -> None:
    if connector_peer_pin_coverage is not None:
        item = connector_peer_pin_coverage
        if item.netlist_sha256 != netlist_sha256:
            raise ValueError("Connector peer-pin coverage must use this report's native netlist")
        expected_counts = (
            (
                "connector.repeated_pin_function",
                item.repeated_function_finding_count,
            ),
            (
                "connector.peer_pin_assignment_outlier",
                item.peer_pin_outlier_finding_count,
            ),
            (
                "connector.peer_pin_assignment_divergence",
                item.peer_pin_divergence_finding_count,
            ),
            (
                "connector.generic_peer_pin_all_open",
                item.generic_peer_pin_all_open_finding_count,
            ),
            (
                "connector.footprint_named_signal_assignment_divergence",
                item.footprint_alias_coverage.named_signal_divergence_finding_count,
            ),
            (
                "connector.footprint_named_passive_assignment_divergence",
                item.footprint_alias_coverage.named_passive_divergence_finding_count,
            ),
        )
        for rule_id, expected_count in expected_counts:
            actual_count = sum(finding.rule_id == rule_id for finding in findings)
            if actual_count != expected_count:
                raise ValueError(f"Connector peer-pin coverage count must match {rule_id} findings")
        footprint_findings = sum(
            finding.rule_id == "connector.footprint_peer_pin_assignment_divergence"
            for finding in findings
        )
        if footprint_findings != item.footprint_alias_coverage.divergence_finding_count:
            raise ValueError("Connector footprint-alias peer coverage count must match findings")
        named_power_input_divergence_findings = sum(
            finding.rule_id == "connector.footprint_named_power_input_assignment_divergence"
            for finding in findings
        )
        if (
            named_power_input_divergence_findings
            != item.footprint_alias_coverage.named_power_input_divergence_finding_count
        ):
            raise ValueError("Named power-input footprint-alias coverage count must match findings")
        named_power_input_all_open_findings = sum(
            finding.rule_id == "connector.footprint_named_power_input_all_open"
            for finding in findings
        )
        if (
            named_power_input_all_open_findings
            != item.footprint_alias_coverage.named_power_input_all_open_finding_count
        ):
            raise ValueError(
                "Named power-input all-open footprint-alias coverage count must match findings"
            )
        named_power_output_all_open_findings = sum(
            finding.rule_id == "connector.footprint_named_power_output_all_open"
            for finding in findings
        )
        if (
            named_power_output_all_open_findings
            != item.footprint_alias_coverage.named_power_output_all_open_finding_count
        ):
            raise ValueError(
                "Named power-output all-open footprint-alias coverage count must match findings"
            )
        named_signal_all_open_findings = sum(
            finding.rule_id == "connector.footprint_named_signal_all_open" for finding in findings
        )
        if (
            named_signal_all_open_findings
            != item.footprint_alias_coverage.named_signal_all_open_finding_count
        ):
            raise ValueError(
                "Named signal all-open footprint-alias coverage count must match findings"
            )
        named_power_output_divergence_findings = sum(
            finding.rule_id == "connector.footprint_named_power_output_assignment_divergence"
            for finding in findings
        )
        if (
            named_power_output_divergence_findings
            != item.footprint_alias_coverage.named_power_output_divergence_finding_count
        ):
            raise ValueError(
                "Named power-output footprint-alias coverage count must match findings"
            )
        footprint_open_findings = sum(
            finding.rule_id
            in {
                "connector.footprint_peer_pin_open_outlier",
                "connector.footprint_named_power_input_open_outlier",
                "connector.footprint_named_signal_input_open_outlier",
                "connector.footprint_named_power_output_open_outlier",
                "connector.footprint_named_signal_output_open_outlier",
                "connector.footprint_named_signal_mode_dependent_open_outlier",
                "connector.footprint_named_passive_open_outlier",
            }
            for finding in findings
        )
        if footprint_open_findings != item.footprint_alias_coverage.open_outlier_finding_count:
            raise ValueError(
                "Connector footprint-alias open-peer coverage count must match findings"
            )
        footprint_all_open_findings = sum(
            finding.rule_id == "connector.footprint_peer_pin_all_open" for finding in findings
        )
        if footprint_all_open_findings != item.footprint_alias_coverage.all_open_finding_count:
            raise ValueError(
                "Connector footprint-alias all-open coverage count must match findings"
            )
        part_id_expected_counts = (
            (
                "connector.peer_pin_assignment_outlier",
                item.part_id_alias_coverage.outlier_finding_count,
            ),
            (
                "connector.peer_pin_assignment_divergence",
                item.part_id_alias_coverage.divergence_finding_count,
            ),
        )
        for rule_id, expected_count in part_id_expected_counts:
            actual_count = sum(
                finding.rule_id == rule_id
                and finding.evidence.get("peer_identity_basis") == ("part_id",)
                for finding in findings
            )
            if actual_count != expected_count:
                raise ValueError(
                    f"Connector PART_ID peer coverage count must match {rule_id} findings"
                )
