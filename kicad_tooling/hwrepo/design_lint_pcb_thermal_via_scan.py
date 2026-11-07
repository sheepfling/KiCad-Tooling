"""PCB thermal-via scan failure reports, kept separate from scan coordination."""

from __future__ import annotations

from .design_lint_pcb_coverage_common import PcbRuleMode, map_sha256
from .model_primitives import RepositoryPath
from .pcb_thermal_via_models import PcbThermalViaCoverageReport, PcbThermalViaMap


def blocked_thermal_via_coverage(
    requirements: PcbThermalViaMap | None,
    mode: PcbRuleMode,
    board_path: RepositoryPath,
    issue: str,
) -> PcbThermalViaCoverageReport:
    """Keep configured evidence failures explicit while preserving off/no-map states."""
    if requirements is None:
        return PcbThermalViaCoverageReport()
    if mode == "off":
        return PcbThermalViaCoverageReport(status="DISABLED", mode=mode)
    return PcbThermalViaCoverageReport(
        status="BLOCKED",
        mode=mode,
        map_sha256=map_sha256(requirements),
        board_path=board_path,
        issue=issue,
    )
