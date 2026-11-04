"""Translate STM32 CubeMX project-map coverage and mismatch observations."""

from __future__ import annotations

from .design_lint_stm32_candidate_evidence import (
    Stm32PinMapCandidate,
    Stm32PinMapMismatchFindingEvidence,
    Stm32UnmappedDeviceFindingEvidence,
)
from .design_lint_types import Candidate
from .stm32_pin_map_models import Stm32PinMapCoverageReport


def stm32_candidates(
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build firmware pin-map coverage findings from the authored project contract."""
    found: list[Candidate] = []
    if stm32_pin_map_coverage is not None:
        for device in stm32_pin_map_coverage.unmapped_devices:
            source_evidence = Stm32UnmappedDeviceFindingEvidence(
                report=stm32_pin_map_coverage,
                device=device,
            )
            found.append(
                Stm32PinMapCandidate.from_source_evidence(
                    source_evidence,
                    subject=f"{device.reference}: STM32 CubeMX pin-map coverage is missing",
                    message=(
                        "This fitted component is identified as an STM32 device, but the project "
                        "has no explicit CubeMX pin-map contract for it. Confirm that CubeMX is "
                        "the firmware source; if so, map every package pin to a KiCad symbol pin "
                        "or record a reasoned exclusion. This name-based discovery prompt does "
                        "not establish that the device is configured by CubeMX."
                    ),
                )
            )
        for mismatch in stm32_pin_map_coverage.mismatches:
            source_evidence = Stm32PinMapMismatchFindingEvidence(
                report=stm32_pin_map_coverage,
                mismatch=mismatch,
            )
            found.append(
                Stm32PinMapCandidate.from_source_evidence(
                    source_evidence,
                    subject=(
                        f"{mismatch.reference}.{mismatch.port_pin}: "
                        "CubeMX and KiCad pin map differs from the project contract"
                    ),
                    message=(
                        "A project-mapped STM32 package pin disagrees with the authored "
                        "CubeMX/KiCad pin-map contract. Review the MCU pinout, schematic net, "
                        "and firmware configuration. " + "; ".join(mismatch.issues)
                    ),
                )
            )
    return tuple(found)
