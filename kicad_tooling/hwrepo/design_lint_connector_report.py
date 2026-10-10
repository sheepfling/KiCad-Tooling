"""Format connector and peer-pin heuristic coverage evidence."""

from __future__ import annotations

from .models import DesignLintReport


def connector_peer_report_lines(report: DesignLintReport) -> list[str]:
    """Render connector inventory and peer-pin coverage sections."""
    lines: list[str] = []
    if report.connector_coverage is not None:
        coverage = report.connector_coverage
        lines.append(f"Connector coverage: {coverage.status}")
        lines.append(f"  Scope: {coverage.scope}")
        if coverage.inventory_review_basis is not None:
            lines.append(f"  Inventory review basis: {coverage.inventory_review_basis}")
        if coverage.interface_catalog_path is not None:
            lines.append(
                "  Interface catalog: "
                f"{coverage.interface_catalog_path} "
                f"({coverage.interface_catalog_sha256 or 'unavailable'})"
            )
        for identifier in coverage.unbound_interface_ids:
            lines.append(f"  Unbound interface: {identifier}")
        for issue in coverage.catalog_issues:
            lines.append(f"  Catalog issue: {issue}")
        for entry in coverage.entries:
            lines.append(f"  {entry.status} connector {entry.reference}")
            if entry.interface_id is not None:
                lines.append(f"    Interface: {entry.interface_id}")
            if entry.basis:
                lines.append(f"    Basis: {entry.basis}")
            if entry.peer_assignment_group is not None:
                lines.append(f"    Peer-assignment group: {entry.peer_assignment_group}")
                lines.append(f"    Peer-assignment basis: {entry.peer_assignment_basis}")
            for pin in entry.mapped_pins:
                function = pin.symbol_function or "<unnamed>"
                nets = ", ".join(pin.nets) or "<unconnected>"
                lines.append(
                    f"    Interface pin {pin.interface_pin_number} ({pin.interface_signal}) "
                    f"maps to {pin.component_pin}: role={pin.role or '<unclassified>'}; "
                    f"symbol={function}; nets={nets}"
                )
            for pin, reason in entry.unlisted_pin_reasons.items():
                lines.append(f"    Reviewed unlisted pin {pin}: {reason}")
            for pin in entry.interface_pins_unmapped:
                lines.append(f"    Unmapped interface pin: {pin}")
            for pin in entry.interface_pins_unknown:
                lines.append(f"    Unknown interface pin: {pin}")
            for pin in entry.component_pins_unaccounted:
                lines.append(f"    Unreviewed component pin: {pin}")
            for pin in entry.component_pins_unknown:
                lines.append(f"    Unknown component pin: {pin}")
            for issue in entry.issues:
                lines.append(f"    Issue: {issue}")

    peer_coverage = report.connector_peer_pin_coverage

    if peer_coverage is not None:
        lines.append(f"Connector peer-pin heuristic coverage: {peer_coverage.status}")
        lines.append(f"  Native netlist SHA-256: {peer_coverage.netlist_sha256}")
        lines.append(
            f"  Connector candidates: {peer_coverage.connector_candidate_count}; fitted: "
            f"{peer_coverage.fitted_connector_count}; exact-symbol peer groups: "
            f"{peer_coverage.exact_symbol_peer_group_count}"
        )
        lines.append(
            f"  Exact-symbol pin groups: {peer_coverage.exact_symbol_pin_group_count}; "
            f"unknown functions: "
            f"{peer_coverage.exact_symbol_pin_groups_with_unknown_function_count}; "
            f"common assignments: {peer_coverage.exact_symbol_pin_groups_with_common_assignment_count}; "
            f"different assignments: "
            f"{peer_coverage.exact_symbol_pin_groups_with_different_assignments_count}; "
            f"all unassigned: {peer_coverage.exact_symbol_pin_groups_all_unassigned_count}; "
            f"with an open assignment: "
            f"{peer_coverage.exact_symbol_pin_groups_with_open_assignment_count}"
        )
        part_id_coverage = peer_coverage.part_id_alias_coverage
        lines.append(
            f"  Cross-symbol PART_ID aliases: {part_id_coverage.status}; candidate/eligible "
            f"groups: {part_id_coverage.candidate_group_count}/"
            f"{part_id_coverage.eligible_peer_group_count}; compared pin groups: "
            f"{part_id_coverage.compared_pin_group_count}; incomplete identity/inventory/"
            f"metadata groups: {part_id_coverage.incomplete_component_identity_group_count}/"
            f"{part_id_coverage.incomplete_pin_inventory_group_count}/"
            f"{part_id_coverage.incomplete_pin_metadata_group_count}; ambiguous assignments: "
            f"{part_id_coverage.ambiguous_assignment_pin_group_count}; outlier/divergence "
            f"findings: {part_id_coverage.outlier_finding_count}/"
            f"{part_id_coverage.divergence_finding_count}"
        )
        lines.append(
            f"  Repeated function groups: {peer_coverage.repeated_function_group_count}; "
            f"common assignments: "
            f"{peer_coverage.repeated_function_groups_with_common_assignment_count}; "
            f"different assignments: "
            f"{peer_coverage.repeated_function_groups_with_different_assignments_count}; "
            f"all unassigned: {peer_coverage.repeated_function_groups_all_unassigned_count}; "
            f"with an open assignment: "
            f"{peer_coverage.repeated_function_groups_with_open_assignment_count}"
        )
        lines.append(
            "  Review findings: repeated-function "
            f"{peer_coverage.repeated_function_finding_count}; peer outliers "
            f"{peer_coverage.peer_pin_outlier_finding_count}; peer divergences "
            f"{peer_coverage.peer_pin_divergence_finding_count}"
        )
        lines.append(f"  Scope: {peer_coverage.scope}")
        for reference in peer_coverage.incomplete_pin_inventory_references:
            lines.append(f"  Incomplete exact-symbol pin inventory: {reference}")

    if report.component_peer_pin_coverage:
        lines.append("Component peer-pin assignment heuristic coverage:")
        for coverage in report.component_peer_pin_coverage:
            lines.append(
                f"  {coverage.rule_id}: {coverage.status} (mode: {coverage.mode}; "
                f"exact-symbol/PART_ID peer groups: "
                f"{coverage.exact_symbol_peer_group_count}/"
                f"{coverage.part_id_peer_group_count}; "
                f"PART_ID candidate/ineligible-identity groups: "
                f"{coverage.part_id_candidate_group_count}/"
                f"{coverage.part_id_incomplete_component_identity_group_count}; "
                f"complete/incomplete inventories: "
                f"{coverage.complete_pin_inventory_group_count}/"
                f"{coverage.incomplete_pin_inventory_group_count}; "
                f"comparable/type-matched/function-compatible pin groups: "
                f"{coverage.comparable_pin_group_count}/"
                f"{coverage.matching_electrical_type_pin_group_count}/"
                f"{coverage.compatible_function_pin_group_count}; "
                f"ambiguous/unambiguous assignments: "
                f"{coverage.ambiguous_assignment_pin_group_count}/"
                f"{coverage.unambiguous_assignment_pin_group_count}; "
                f"candidates/deduplicated/findings/suppressed: "
                f"{coverage.candidate_group_count}/"
                f"{coverage.deduplicated_candidate_group_count}/"
                f"{coverage.finding_count}/{coverage.suppressed_candidate_count})"
            )
            lines.append(f"    Native netlist SHA-256: {coverage.netlist_sha256}")
            if coverage.part_id_incomplete_component_identity_references:
                references = ", ".join(coverage.part_id_incomplete_component_identity_references)
                lines.append(f"    PART_ID identity mismatch references: {references}")
            for reference in coverage.incomplete_pin_inventory_references:
                lines.append(f"    Incomplete peer inventory group includes: {reference}")
    return lines
