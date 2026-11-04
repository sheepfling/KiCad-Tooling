"""Dispatch mapped-coverage candidate building to thematic owners."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class MappedCoverageCandidateInputs:
    """Observed topology, resolved coverage, and the authored maps it evaluates."""

    observed: NetlistContract
    coverage: MappedCandidateInputs
    usb_data_path_map: UsbDataPathMap | None
    usb_data_map_sha256: str | None
    power_path_map: PowerPathMap | None
    power_sequence_map: PowerSequenceMap | None


@dataclass(frozen=True, slots=True)
class MappedCoverageCandidateResult:
    """Mapped-coverage findings with typed power path and sequence counts."""

    candidates: tuple[Candidate, ...]

    @property
    def usb_data_path_finding_count(self) -> int:
        return sum(item.rule_id == "bus.usb_data_path_mismatch" for item in self.candidates)

    @property
    def power_path_finding_count(self) -> int:
        return sum(item.rule_id == "power.mapped_series_path_mismatch" for item in self.candidates)

    @property
    def power_sequence_finding_count(self) -> int:
        return sum(
            item.rule_id == "power.mapped_sequence_dependency_mismatch" for item in self.candidates
        )


def mapped_coverage_candidates(
    observed: NetlistContract,
    inputs: MappedCandidateInputs,
    *,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
    power_path_map: PowerPathMap | None = None,
    power_sequence_map: PowerSequenceMap | None = None,
) -> tuple[Candidate, ...]:
    """Preserve the keyword-based mapped-coverage candidate interface."""
    return scan_mapped_coverage_candidates(
        MappedCoverageCandidateInputs(
            observed=observed,
            coverage=inputs,
            usb_data_path_map=usb_data_path_map,
            usb_data_map_sha256=usb_data_map_sha256,
            power_path_map=power_path_map,
            power_sequence_map=power_sequence_map,
        )
    ).candidates


def scan_mapped_coverage_candidates(
    inputs: MappedCoverageCandidateInputs,
) -> MappedCoverageCandidateResult:
    """Build mapped-coverage findings from one typed theme request."""
    return MappedCoverageCandidateResult(
        (
            *protection_candidates(inputs.coverage.external_protection),
            *crystal_network_candidates(inputs.coverage.crystal_network),
            *regulator_feedback_candidates(inputs.coverage.regulator_feedback),
            *rc_filter_candidates(inputs.coverage.rc_filter),
            *usb_data_path_candidates(
                inputs.observed,
                inputs.usb_data_path_map,
                inputs.usb_data_map_sha256,
            ),
            *power_path_candidates(inputs.observed, inputs.power_path_map),
            *power_sequence_candidates(inputs.observed, inputs.power_sequence_map),
        )
    )
