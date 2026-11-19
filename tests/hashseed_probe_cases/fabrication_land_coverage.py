"""Source-bound land-coverage fault/control reports for hash-seed probes."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import (
    write_synthetic_fabrication,
    write_trapezoid_land_coverage_fault,
)
from tests.json_types import JsonObject

_SETTINGS = FabricationConnectivitySettings(check_raster_phase_stability=False)


def _report(directory: Path, *, fault: bool) -> JsonObject:
    if fault:
        board, artifacts = write_trapezoid_land_coverage_fault(directory)
    else:
        directory.mkdir(parents=True)
        board, artifacts = write_synthetic_fabrication(directory)
    report = analyze_fabrication_connectivity(board, artifacts, _SETTINGS)
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Return complete PASS and REVIEW reports for the same synthetic design."""
    with TemporaryDirectory(prefix="fabrication-land-coverage-hashseed-") as temporary:
        root = Path(temporary)
        return {
            "fabrication_land_coverage_control": _report(root / "control", fault=False),
            "fabrication_land_coverage_fault": _report(root / "fault", fault=True),
        }
