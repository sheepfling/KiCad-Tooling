"""Dispatch mapped-coverage candidate building to thematic owners."""

from __future__ import annotations

from .design_lint_crystal_candidates import crystal_network_candidates
from .design_lint_power_path_candidates import power_path_candidates
from .design_lint_power_sequence_candidates import power_sequence_candidates
from .design_lint_protection_candidates import protection_candidates
from .design_lint_rc_filter_candidates import rc_filter_candidates
from .design_lint_regulator_candidates import regulator_feedback_candidates
from .design_lint_types import Candidate
from .design_lint_usb_data_path_candidates import usb_data_path_candidates
from .models import (
    CrystalNetworkCoverageReport,
    ExternalProtectionCoverageReport,
    NetlistContract,
    PowerPathMap,
    PowerSequenceMap,
    RcFilterCoverageReport,
    RegulatorFeedbackCoverageReport,
    UsbDataPathMap,
)


def mapped_coverage_candidates(
    observed: NetlistContract,
    *,
    external_protection_coverage: ExternalProtectionCoverageReport | None = None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None,
    rc_filter_coverage: RcFilterCoverageReport | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
    power_path_map: PowerPathMap | None = None,
    power_sequence_map: PowerSequenceMap | None = None,
) -> tuple[Candidate, ...]:
    """Build mapped-coverage candidates in stable theme order."""
    return (
        *protection_candidates(external_protection_coverage),
        *crystal_network_candidates(crystal_network_coverage),
        *regulator_feedback_candidates(regulator_feedback_coverage),
        *rc_filter_candidates(rc_filter_coverage),
        *usb_data_path_candidates(observed, usb_data_path_map, usb_data_map_sha256),
        *power_path_candidates(observed, power_path_map),
        *power_sequence_candidates(observed, power_sequence_map),
    )
