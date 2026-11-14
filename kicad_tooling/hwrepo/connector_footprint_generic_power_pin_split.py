"""Review unanchored generic power-pin splits across similar connector aliases."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "connector.footprint_peer_generic_power_pin_unanchored_split"
_GENERIC_POWER_TYPES = frozenset({"power_in", "power_out"})


@dataclass(frozen=True, slots=True)
class ConnectorFootprintGenericPowerPinSplitEvidence:
    """One generic native power contact split across an unanchored alias cohort."""

    scan: ConnectorFootprintPeerPinScan
    divergence: ConnectorFootprintPeerPinDivergence
    pin_electrical_type: str

    def __post_init__(self) -> None:
        if self.divergence not in self.scan.unanchored_divergences:
            raise ValueError("Power-pin split evidence must come from the supplied peer scan")
        if (
            self.divergence.peer_assignment_group is not None
            or self.divergence.common_anchor_pin_numbers
            or not pin_function_is_generic(self.divergence.pin_function)
            or len(self.divergence.assignments) < 2
            or any(len(nets) != 1 for nets in self.divergence.assignments.values())
            or len({nets[0] for nets in self.divergence.assignments.values()}) < 2
        ):
            raise ValueError("Power-pin split evidence requires unanchored assigned generic peers")
        expected_type = _matching_native_power_type(self.scan, self.divergence)
        if expected_type is None or self.pin_electrical_type != expected_type:
            raise ValueError("Power-pin split evidence must match native peer pin types")

    @property
    def projection(self) -> CandidateEvidenceProjection:
        """Return stable finding evidence from the validated native peer snapshot."""
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "value": (self.divergence.value,),
                "footprint": (self.divergence.footprint,),
                "pin_number": (self.divergence.pin_number,),
                "pin_function": (self.divergence.pin_function,),
                "pin_electrical_type": (self.pin_electrical_type,),
                "assignments": tuple(
                    f"{pin}={nets[0]}"
                    for pin, nets in sorted(
                        self.divergence.assignments.items(),
                        key=lambda item: (item[0].casefold(), item[0]),
                    )
                ),
                "symbols": self.divergence.symbols,
                "common_anchor_pin_numbers": (),
            },
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintGenericPowerPinSplitCandidate(Candidate):
    """Source-bound review candidate for one generic native power-pin split."""

    source_evidence: ConnectorFootprintGenericPowerPinSplitEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintGenericPowerPinSplitEvidence,
    ) -> ConnectorFootprintGenericPowerPinSplitCandidate:
        """Build a candidate whose report fields match its immutable source evidence."""
        projection = source_evidence.projection
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.divergence.value} "
                f"[{source_evidence.divergence.footprint}] "
                f"pin {source_evidence.divergence.pin_number}"
            ),
            message=(
                "Fitted, footprint-similar connector aliases assign this generic native "
                f"{source_evidence.pin_electrical_type} contact to different nets without a "
                "common-net anchor. Review the approved pinout and intended port isolation; "
                "similarity does not establish that the nets should be joined."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = self.source_evidence.projection
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Power-pin split candidate must match its native source evidence")


def unanchored_generic_power_pin_split_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Review assigned generic power contacts split across unscoped alias peers."""
    candidates: list[Candidate] = []
    for divergence in scan.unanchored_divergences:
        if (
            divergence.peer_assignment_group is not None
            or divergence.common_anchor_pin_numbers
            or not pin_function_is_generic(divergence.pin_function)
            or len(divergence.assignments) < 2
            or any(len(nets) != 1 for nets in divergence.assignments.values())
            or len({nets[0] for nets in divergence.assignments.values()}) < 2
        ):
            continue
        electrical_type = _matching_native_power_type(scan, divergence)
        if electrical_type is None:
            continue
        source = ConnectorFootprintGenericPowerPinSplitEvidence(
            scan=scan,
            divergence=divergence,
            pin_electrical_type=electrical_type,
        )
        candidates.append(
            ConnectorFootprintGenericPowerPinSplitCandidate.from_source_evidence(source)
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.subject.casefold(), item.subject, item.evidence["assignments"]),
        )
    )


def _matching_native_power_type(
    scan: ConnectorFootprintPeerPinScan,
    divergence: ConnectorFootprintPeerPinDivergence,
) -> str | None:
    """Return one matching supported native power type for every assigned peer."""
    observed_types = {
        pin.casefold(): pin_type.strip().casefold()
        for pin, pin_type in scan.source.observed.pin_electrical_types.items()
    }
    peer_types = {
        observed_types.get(f"{pin.rsplit('.', 1)[0]}.{divergence.pin_number}".casefold())
        for pin in divergence.assignments
    }
    if len(peer_types) != 1:
        return None
    (peer_type,) = peer_types
    return peer_type if peer_type in _GENERIC_POWER_TYPES else None
