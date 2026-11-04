"""Typed I2C address finding sources and their stable report projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cResponderAddressCoverageEntry,
)
from .i2c_addressing import UnmappedI2cResponder, format_i2c_address


def _validate_coverage_source(coverage: I2cAddressCoverageReport) -> None:
    if coverage.status not in {"COMPLETE", "INCOMPLETE"}:
        raise ValueError("I2C address findings require evaluated coverage")
    if coverage.netlist_sha256 is None:
        raise ValueError("I2C address finding coverage must bind a native netlist digest")


@dataclass(frozen=True, slots=True)
class I2cAddressMismatchEvidence:
    """One eligible strapped-address mismatch from a source-bound coverage report."""

    coverage: I2cAddressCoverageReport
    entry: I2cResponderAddressCoverageEntry

    def __post_init__(self) -> None:
        _validate_coverage_source(self.coverage)
        if self.entry not in self.coverage.entries:
            raise ValueError("I2C address mismatch entry must belong to its coverage report")
        if (
            self.entry.status != "COMPLETE"
            or self.entry.mode != "strapped"
            or self.entry.expected_address == self.entry.observed_address
        ):
            raise ValueError("I2C address mismatch source must describe a complete differing strap")


@dataclass(frozen=True, slots=True)
class I2cAddressCollisionEvidence:
    """A source-bound set of complete responders sharing one segment address."""

    coverage: I2cAddressCoverageReport
    entries: tuple[I2cResponderAddressCoverageEntry, ...]

    def __post_init__(self) -> None:
        _validate_coverage_source(self.coverage)
        if len(self.entries) < 2:
            raise ValueError("I2C address collision evidence needs multiple responders")
        if any(entry not in self.coverage.entries for entry in self.entries):
            raise ValueError("I2C collision entries must belong to their coverage report")
        first = self.entries[0]
        if first.status != "COMPLETE" or first.observed_address is None:
            raise ValueError("I2C address collision entries must be complete static observations")
        if any(
            entry.status != "COMPLETE"
            or entry.segment_id != first.segment_id
            or entry.observed_address != first.observed_address
            for entry in self.entries
        ):
            raise ValueError("I2C collision entries must share one segment and observed address")
        if len({entry.reference.casefold() for entry in self.entries}) != len(self.entries):
            raise ValueError("I2C address collision evidence cannot repeat a responder")


@dataclass(frozen=True, slots=True)
class I2cUnmappedResponderEvidence:
    """A typed native responder hint paired with the map state used to find it."""

    responder: UnmappedI2cResponder
    address_map: I2cAddressMap | None

    def __post_init__(self) -> None:
        if self.address_map is None:
            return
        mapped_references = {
            item.reference.casefold()
            for segment in self.address_map.segments
            for item in segment.responders
        }
        if self.responder.reference.casefold() in mapped_references:
            raise ValueError("Mapped I2C responders cannot be marked as unmapped")


I2cAddressFindingEvidence: TypeAlias = (
    I2cAddressMismatchEvidence | I2cAddressCollisionEvidence | I2cUnmappedResponderEvidence
)

I2cAddressEvidenceProjection = CandidateEvidenceProjection


def _address_entry_evidence(
    entries: tuple[I2cResponderAddressCoverageEntry, ...],
) -> dict[str, tuple[str, ...]]:
    evidence: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        evidence[f"{entry.reference}.symbol"] = (
            f"expected {entry.expected_symbol}; observed {entry.observed_symbol or 'unknown'}",
        )
        evidence[f"{entry.reference}.SDA"] = (
            f"{entry.sda_pin} -> {', '.join(entry.sda_nets) or 'unconnected'}",
        )
        evidence[f"{entry.reference}.SCL"] = (
            f"{entry.scl_pin} -> {', '.join(entry.scl_nets) or 'unconnected'}",
        )
        evidence[f"{entry.reference}.address"] = (
            (
                f"expected {format_i2c_address(entry.expected_address)}; "
                f"observed {format_i2c_address(entry.observed_address)}"
            ),
        )
        for bit in entry.address_bits:
            evidence[f"{entry.reference}.bit{bit.bit}"] = (
                (
                    f"{bit.pin} function {bit.observed_function or 'unknown'}; "
                    f"nets {', '.join(bit.nets) or 'unconnected'}; "
                    f"resolved {bit.resolved_value if bit.resolved_value is not None else 'unknown'}"
                ),
            )
        evidence[f"{entry.reference}.basis"] = (entry.basis,)
    return evidence


def project_i2c_address_evidence(
    source: I2cAddressFindingEvidence,
) -> I2cAddressEvidenceProjection:
    """Project the owning coverage or scan record to stable report fields."""
    if isinstance(source, I2cAddressMismatchEvidence):
        return I2cAddressEvidenceProjection(
            rule_id="bus.i2c_address_mismatch",
            evidence={
                "segment": (source.entry.segment_id,),
                **_address_entry_evidence((source.entry,)),
            },
        )
    if isinstance(source, I2cAddressCollisionEvidence):
        first = source.entries[0]
        return I2cAddressEvidenceProjection(
            rule_id="bus.i2c_address_collision",
            evidence={
                "segment": (first.segment_id,),
                "address": (format_i2c_address(first.observed_address),),
                **_address_entry_evidence(source.entries),
            },
        )
    responder = source.responder
    return I2cAddressEvidenceProjection(
        rule_id="bus.i2c_unmapped_responder",
        evidence={
            "SDA_pins": responder.sda_pins,
            "SCL_pins": responder.scl_pins,
            "assigned_net_pairs": tuple(f"{sda} / {scl}" for sda, scl in responder.signal_pairs),
            "address_map": (
                ("configured",) if source.address_map is not None else ("not_configured",)
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class I2cAddressCandidate(Candidate):
    """Internal address finding that retains its source evidence record."""

    source_evidence: I2cAddressFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2cAddressFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> I2cAddressCandidate:
        projection = project_i2c_address_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i2c_address_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("I2C address candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("I2C address evidence must match its typed source projection")
