"""Dispatch mapped-coverage candidate building to thematic owners."""

from __future__ import annotations

from .design_lint_candidate_inputs import MappedCandidateInputs
from .design_lint_crystal_candidates import crystal_network_candidates
from .design_lint_power_path_candidates import power_path_candidates
from .design_lint_power_sequence_candidates import power_sequence_candidates
from .design_lint_protection_candidates import protection_candidates
from .design_lint_rc_filter_candidates import rc_filter_candidates
from .design_lint_regulator_candidates import regulator_feedback_candidates
from .design_lint_types import Candidate
from .design_lint_usb_data_path_candidates import usb_data_path_candidates
from .models import (
    NetlistContract,
)
from .power_path_models import PowerPathMap
from .power_sequence_models import PowerSequenceMap
from .usb_data_path_models import UsbDataPathMap


def mapped_coverage_candidates(
    observed: NetlistContract,
    inputs: MappedCandidateInputs,
    *,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
    power_path_map: PowerPathMap | None = None,
    power_sequence_map: PowerSequenceMap | None = None,
) -> tuple[Candidate, ...]:
    """Build mapped-coverage candidates in stable theme order."""
    return (
        *protection_candidates(inputs.external_protection),
        *crystal_network_candidates(inputs.crystal_network),
        *regulator_feedback_candidates(inputs.regulator_feedback),
        *rc_filter_candidates(inputs.rc_filter),
        *usb_data_path_candidates(observed, usb_data_path_map, usb_data_map_sha256),
        *power_path_candidates(observed, power_path_map),
        *power_sequence_candidates(observed, power_sequence_map),
    )
