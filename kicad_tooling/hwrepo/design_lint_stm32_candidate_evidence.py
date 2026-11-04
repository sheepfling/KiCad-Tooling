"""Typed source evidence and projection for STM32/CubeMX pin-map findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .stm32_pin_map_models import (
    Stm32PinMapCoverageReport,
    Stm32PinMapMismatch,
    Stm32UnmappedDevice,
)

RULE_ID: DesignLintRuleId = "mcu.stm32_cubemx_pin_map"


@dataclass(frozen=True, slots=True)
class Stm32UnmappedDeviceFindingEvidence:
    """One unmapped-device prompt with its complete source-bound coverage report."""

    report: Stm32PinMapCoverageReport
    device: Stm32UnmappedDevice

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Unmapped STM32 finding requires incomplete coverage")
        if self.device not in self.report.unmapped_devices:
            raise ValueError("Unmapped STM32 finding must belong to the source report")
        if self.report.netlist_sha256 != self.device.netlist_sha256:
            raise ValueError("Unmapped STM32 finding must match the report netlist identity")


@dataclass(frozen=True, slots=True)
class Stm32PinMapMismatchFindingEvidence:
    """One exact pin mismatch with its complete IOC, map, and netlist evidence."""

    report: Stm32PinMapCoverageReport
    mismatch: Stm32PinMapMismatch

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("STM32 mismatch finding requires evaluated coverage")
        if self.mismatch not in self.report.mismatches:
            raise ValueError("STM32 mismatch finding must belong to the source report")
        if self.report.map_sha256 != self.mismatch.map_sha256:
            raise ValueError("STM32 mismatch finding must match the report map identity")
        if self.report.netlist_sha256 != self.mismatch.netlist_sha256:
            raise ValueError("STM32 mismatch finding must match the report netlist identity")
        if self.report.ioc_source_hashes.get(self.mismatch.ioc_path) != self.mismatch.ioc_sha256:
            raise ValueError("STM32 mismatch finding must match the report IOC identity")


Stm32FindingSource: TypeAlias = (
    Stm32UnmappedDeviceFindingEvidence | Stm32PinMapMismatchFindingEvidence
)


def project_stm32_pin_map_evidence(
    source: Stm32FindingSource,
) -> CandidateEvidenceProjection:
    """Project one typed source into the established STM32 finding fields."""
    if isinstance(source, Stm32UnmappedDeviceFindingEvidence):
        device = source.device
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "reference": (device.reference,),
                "part": (device.observed_part,),
                "symbol": (device.observed_symbol or "<unknown>",),
                "native_netlist_sha256": (device.netlist_sha256,),
            },
        )

    mismatch = source.mismatch
    expected_labels = (
        ("<not checked>",)
        if mismatch.accepted_ioc_gpio_labels is None
        else tuple(
            "<absent>" if item is None else item for item in mismatch.accepted_ioc_gpio_labels
        )
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "mcu_reference": (mismatch.reference,),
            "package_pin": (mismatch.port_pin,),
            "symbol_pin": (f"{mismatch.reference}.{mismatch.symbol_pin}",),
            "expected_net": (mismatch.expected_net,),
            "observed_net": mismatch.observed_nets or ("<unconnected>",),
            "accepted_ioc_signal": mismatch.accepted_ioc_signals,
            "observed_ioc_signal": (mismatch.observed_ioc_signal or "<missing>",),
            "accepted_ioc_gpio_label": expected_labels,
            "observed_ioc_gpio_label": (mismatch.observed_ioc_gpio_label or "<absent>",),
            "ioc_path": (mismatch.ioc_path,),
            "ioc_sha256": (mismatch.ioc_sha256,),
            "map_sha256": (mismatch.map_sha256,),
            "native_netlist_sha256": (mismatch.netlist_sha256,),
        },
    )


@dataclass(frozen=True, slots=True)
class Stm32PinMapCandidate(Candidate):
    """STM32 finding that retains and verifies its typed source evidence."""

    source_evidence: Stm32FindingSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: Stm32FindingSource,
        *,
        subject: str,
        message: str,
    ) -> Stm32PinMapCandidate:
        projection = project_stm32_pin_map_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_stm32_pin_map_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("STM32 evidence must match its source projection")
