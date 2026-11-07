"""Review exact two-contact USB SuperSpeed pairs without an identified reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import connector_candidate_references
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .connector_return_pins import (
    connector_pin_for_assigned_net,
    connector_pin_group_has_return_role,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .usb_peer_endpoint_analysis import pin_net_index, usb_superspeed_endpoints

USB_SUPERSPEED_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = (
    "connector.usb_superspeed_pair_without_return_review"
)
UsbSuperSpeedFamily = Literal["USB SuperSpeed TX", "USB SuperSpeed RX"]


@dataclass(frozen=True, slots=True)
class UsbSuperSpeedConnectorReturnPair:
    """A complete two-pin connector assigned to one recognized PHY pair."""

    connector_reference: str
    phy_reference: str
    signal_family: UsbSuperSpeedFamily
    connector_pin_count: int
    positive_pin: str
    positive_function: str
    positive_net: str
    positive_phy_pins: tuple[str, ...]
    negative_pin: str
    negative_function: str
    negative_net: str
    negative_phy_pins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UsbSuperSpeedConnectorReturnEvidence:
    """Exact native connector and PHY assignments used by the review prompt."""

    pair: UsbSuperSpeedConnectorReturnPair


def _project_evidence(
    source: UsbSuperSpeedConnectorReturnEvidence,
) -> CandidateEvidenceProjection:
    pair = source.pair
    evidence = {
        "connector": (pair.connector_reference,),
        "PHY": (pair.phy_reference,),
        "connector_native_pin_count": (str(pair.connector_pin_count),),
        "connected_contact_count": ("2",),
        "USB_SuperSpeed_family": (pair.signal_family,),
        "USB_SuperSpeed_positive_net": (pair.positive_net,),
        "USB_SuperSpeed_positive_connector_pin": (pair.positive_pin,),
        "USB_SuperSpeed_positive_connector_function": (pair.positive_function,),
        "USB_SuperSpeed_positive_PHY_pins": pair.positive_phy_pins,
        "USB_SuperSpeed_negative_net": (pair.negative_net,),
        "USB_SuperSpeed_negative_connector_pin": (pair.negative_pin,),
        "USB_SuperSpeed_negative_connector_function": (pair.negative_function,),
        "USB_SuperSpeed_negative_PHY_pins": pair.negative_phy_pins,
        "identified_connector_return_role": (),
    }
    return CandidateEvidenceProjection(
        rule_id=USB_SUPERSPEED_CONNECTOR_RETURN_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbSuperSpeedConnectorReturnCandidate(Candidate):
    """Source-bound review prompt for one exact two-pin SuperSpeed pair."""

    source_evidence: UsbSuperSpeedConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbSuperSpeedConnectorReturnEvidence,
    ) -> UsbSuperSpeedConnectorReturnCandidate:
        pair = source_evidence.pair
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{pair.connector_reference}: two-pin USB SuperSpeed connector pair has "
                "no identified reference return"
            ),
            message=(
                "The native netlist assigns this complete two-contact connector to both exact "
                f"nets of one recognized {pair.signal_family} PHY pair, and no native connector "
                "function or current source-matched pin role identifies a reference return. "
                "Review whether the signal reference is provided elsewhere, the interface is "
                "intentionally isolated, or the approved pinout requires a reference contact. "
                "This is a review cue; it does not require board ground, infer external cabling "
                "or USB compliance, or prove PCB copper continuity."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "USB SuperSpeed connector-return evidence must match its source projection"
            )


def usb_superspeed_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Review a complete two-pin connector on an exact native SuperSpeed PHY pair.

    Pair identity comes from native U/IC pin functions and assignments. The
    prompt does not infer connector purpose or a required common-ground path.
    """
    assignments = pin_net_index(observed)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    connector_references = connector_candidate_references(
        observed,
        reviewed_connector_references,
    )
    dnp = {reference.casefold() for reference in observed.dnp_components}
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    endpoints = tuple(
        endpoint
        for reference in observed.component_symbols
        for endpoint in usb_superspeed_endpoints(
            (reference,), observed, assignments, connector=False
        )
        if endpoint.signal_family != "USB 2.0 data"
    )
    findings: list[Candidate] = []

    for reference in connector_references:
        reference_key = reference.casefold()
        numbers = inventories.get(reference_key)
        if (
            reference_key in dnp
            or reference_key in not_applicable
            or numbers is None
            or len(numbers) != 2
            or len({number.casefold() for number in numbers}) != 2
            or not connector_pin_metadata_matches_inventory(
                reference_key,
                numbers,
                functions,
                electrical_types,
            )
        ):
            continue
        assigned: dict[str, tuple[str, str]] = {}
        for number in numbers:
            pin = f"{reference}.{number}"
            pin_key = pin.casefold()
            nets = assignments.nets_by_pin_key.get(pin_key, frozenset())
            function = functions.get(pin_key)
            if len(nets) != 1 or function is None:
                assigned = {}
                break
            assigned[pin] = (next(iter(nets)), function)
        if len(assigned) != 2:
            continue

        pair_findings: list[Candidate] = []
        for endpoint in endpoints:
            if endpoint.signal_family == "USB SuperSpeed TX":
                signal_family: UsbSuperSpeedFamily = "USB SuperSpeed TX"
            elif endpoint.signal_family == "USB SuperSpeed RX":
                signal_family = "USB SuperSpeed RX"
            else:
                continue
            positive = connector_pin_for_assigned_net(assigned, endpoint.positive_net)
            negative = connector_pin_for_assigned_net(assigned, endpoint.negative_net)
            if (
                positive is None
                or negative is None
                or positive[0].casefold() == negative[0].casefold()
            ):
                continue
            connector_pins = (positive[0], negative[0])
            if connector_pin_group_has_return_role(connector_pins, observed.pin_functions, mapped):
                continue
            pair_findings.append(
                UsbSuperSpeedConnectorReturnCandidate.from_source_evidence(
                    UsbSuperSpeedConnectorReturnEvidence(
                        UsbSuperSpeedConnectorReturnPair(
                            connector_reference=reference,
                            phy_reference=endpoint.reference,
                            signal_family=signal_family,
                            connector_pin_count=len(numbers),
                            positive_pin=positive[0],
                            positive_function=positive[1],
                            positive_net=endpoint.positive_net,
                            positive_phy_pins=endpoint.positive_pins,
                            negative_pin=negative[0],
                            negative_function=negative[1],
                            negative_net=endpoint.negative_net,
                            negative_phy_pins=endpoint.negative_pins,
                        )
                    )
                )
            )
        if len(pair_findings) == 1:
            findings.extend(pair_findings)
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted((key, value) for key, value in item.evidence.items())),
            ),
        )
    )
