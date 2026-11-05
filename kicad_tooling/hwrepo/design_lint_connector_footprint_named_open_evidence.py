"""Source-bound candidate evidence for named connector contacts left open."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .connector_comparison_scope_types import connector_comparison_scopes_by_reference
from .connector_coverage import source_matched_connector_peer_assignment_groups
from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_footprint_peer_pins import scan_connector_footprint_peer_pin_assignments
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorNamedOpenRuleId = Literal[
    "connector.footprint_named_power_input_open_outlier",
    "connector.footprint_named_power_output_open_outlier",
    "connector.footprint_named_signal_input_open_outlier",
    "connector.footprint_named_signal_output_open_outlier",
    "connector.footprint_named_passive_open_outlier",
    "connector.footprint_named_signal_mode_dependent_open_outlier",
]

MODE_DEPENDENT_SIGNAL_TYPES = SIGNAL_ELECTRICAL_TYPES - frozenset({"input", "output"})
_RULE_ELECTRICAL_TYPES: Mapping[ConnectorNamedOpenRuleId, frozenset[str]] = {
    "connector.footprint_named_power_input_open_outlier": frozenset({"power_in"}),
    "connector.footprint_named_power_output_open_outlier": frozenset({"power_out"}),
    "connector.footprint_named_signal_input_open_outlier": frozenset({"input"}),
    "connector.footprint_named_signal_output_open_outlier": frozenset({"output"}),
    "connector.footprint_named_passive_open_outlier": frozenset({"passive"}),
    "connector.footprint_named_signal_mode_dependent_open_outlier": (MODE_DEPENDENT_SIGNAL_TYPES),
}
_RULE_ROLE_LABELS: Mapping[ConnectorNamedOpenRuleId, str] = {
    "connector.footprint_named_power_input_open_outlier": "power-input",
    "connector.footprint_named_power_output_open_outlier": "power-output",
    "connector.footprint_named_signal_input_open_outlier": "signal-input",
    "connector.footprint_named_signal_output_open_outlier": "signal-output",
    "connector.footprint_named_passive_open_outlier": "passive signal",
    "connector.footprint_named_signal_mode_dependent_open_outlier": "mode-dependent signal",
}


@dataclass(frozen=True, slots=True)
class ConnectorNamedOpenEvidence:
    """One named open-peer record tied to its current scan and optional coverage."""

    scan: ConnectorFootprintPeerPinScan
    coverage: ConnectorCoverageReport | None
    item: ConnectorFootprintPeerPinOpenOutlier
    rule_id: ConnectorNamedOpenRuleId

    def __post_init__(self) -> None:
        _validate_current_named_open_evidence(self)

    @classmethod
    def from_scan(
        cls,
        *,
        scan: ConnectorFootprintPeerPinScan,
        coverage: ConnectorCoverageReport | None,
        item: ConnectorFootprintPeerPinOpenOutlier,
        rule_id: ConnectorNamedOpenRuleId,
    ) -> ConnectorNamedOpenEvidence:
        """Capture one role-classified open contact from the exact peer scan."""
        return cls(scan=scan, coverage=coverage, item=item, rule_id=rule_id)


def _validate_current_named_open_evidence(source: ConnectorNamedOpenEvidence) -> None:
    scan = source.scan
    item = source.item
    observed = scan.source.observed
    current_peer_groups = source_matched_connector_peer_assignment_groups(
        observed,
        source.coverage,
    )
    if connector_comparison_scopes_by_reference(current_peer_groups) != (
        connector_comparison_scopes_by_reference(scan.source.peer_assignment_groups)
    ):
        raise ValueError("Named connector open scan must retain current source-matched peer groups")

    current_scan = scan_connector_footprint_peer_pin_assignments(
        observed,
        scan.source.declared_references,
        current_peer_groups,
    )
    if item not in scan.open_outliers or item not in current_scan.open_outliers:
        raise ValueError("Named connector open evidence must belong to the current peer scan")
    expected_types = _RULE_ELECTRICAL_TYPES[source.rule_id]
    if (
        item.pin_electrical_type.strip().casefold() not in expected_types
        or pin_function_is_generic(item.pin_function)
        or is_named_supply_function(item.pin_function)
        or is_return_function(item.pin_function)
        or not item.common_anchor_pin_numbers
        or item.open_pins != tuple(pin for pin, nets in item.assignments.items() if not nets)
        or not item.open_pins
        or not any(item.assignments.values())
    ):
        raise ValueError("Named connector open evidence must match its role and open-peer scope")


def project_connector_named_open_evidence(
    source: ConnectorNamedOpenEvidence,
) -> CandidateEvidenceProjection:
    """Project the stable named-open report fields from current typed evidence."""
    _validate_current_named_open_evidence(source)
    item = source.item
    evidence: dict[str, tuple[str, ...]] = {
        "value": (item.value,),
        "footprint": (item.footprint,),
        "pin_number": (item.pin_number,),
        "pin_function": (item.pin_function,),
        "pin_electrical_type": (item.pin_electrical_type,),
        "assignments": tuple(
            f"{pin}={','.join(nets) if nets else '<unassigned>'}"
            for pin, nets in item.assignments.items()
        ),
        "open_pins": item.open_pins,
        "symbols": item.symbols,
        "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
        "peer_identity_basis": ("footprint_value",),
    }
    if item.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (item.peer_assignment_group,)
        evidence["peer_assignment_basis"] = item.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=source.rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorNamedOpenCandidate(Candidate):
    """Finding that retains the scan and coverage behind a named open contact."""

    source_evidence: ConnectorNamedOpenEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorNamedOpenEvidence,
    ) -> ConnectorNamedOpenCandidate:
        projection = project_connector_named_open_evidence(source_evidence)
        item = source_evidence.item
        role_label = _RULE_ROLE_LABELS[source_evidence.rule_id]
        message = (
            "Fitted connector instances with distinct native symbols share the same "
            "value, footprint, complete pin inventory, and matching native pin "
            "metadata. This explicit native "
            f"{role_label} contact is assigned to one net on some peers and left open on others, "
            "while another pin provides a common-net anchor. Review the approved pinout for an "
            "intentionally unused contact or a missing connection; these similarity clues do not "
            "establish that the contact must connect."
            + (
                " The comparison is scoped to a source-reviewed peer-assignment group."
                if item.peer_assignment_group is not None
                else ""
            )
        )
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{item.value} [{item.footprint}] pin {item.pin_number} ({item.pin_function}): "
                f"named {role_label} contact is open on a similar connector peer"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_named_open_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Named connector open fields must match their current source projection"
            )
