"""Text rendering for opt-in board-only footprint coverage."""

from __future__ import annotations

from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def board_only_footprint_report_lines(
    inventory: PcbComponentInventoryCoverageReport,
) -> list[str]:
    """Render exact board-only references and the source-bound coverage state."""
    coverage = inventory.board_only_footprint_coverage
    if coverage.status == "DISABLED":
        return []
    lines = [f"PCB board-only footprint review: {coverage.status} (mode: {coverage.mode})"]
    for item in coverage.footprints:
        lines.append(f"  No schematic counterpart: {item.reference} ({item.footprint})")
    if coverage.issue is not None:
        lines.append(f"  Coverage issue: {coverage.issue}")
    return lines
