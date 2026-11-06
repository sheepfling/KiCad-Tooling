"""Source projection for generic connector USB SuperSpeed coverage prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_peer_generic_connector_models import UsbGenericConnectorSuperspeedPair

USB_SUPERSPEED_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = (
    "bus.usb_superspeed_generic_connector_pair_review"
)


@dataclass(frozen=True, slots=True)
class UsbSuperspeedGenericConnectorFindingEvidence:
    """One connector/PHY pair and its exact map input."""

    pair: UsbGenericConnectorSuperspeedPair
    data_path: UsbDataPathCandidateInputs


def project_usb_superspeed_generic_connector_evidence(
    source: UsbSuperspeedGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project native connector contacts, PHY pins, and optional map digest."""
    pair = source.pair
    direction = pair.signal_family.removeprefix("USB SuperSpeed ")
    prefix = f"USB_SuperSpeed_{direction}"
    evidence = {
        "connector": (pair.connector_reference,),
        "PHY": (pair.phy_reference,),
        f"{prefix}_positive_net": (pair.positive_net,),
        f"{prefix}_positive_PHY_pin": (pair.phy_positive_pin,),
        f"{prefix}_positive_generic_connector_pins": pair.positive_pins,
        f"{prefix}_positive_generic_pin_functions": pair.positive_functions,
        f"{prefix}_negative_net": (pair.negative_net,),
        f"{prefix}_negative_PHY_pin": (pair.phy_negative_pin,),
        f"{prefix}_negative_generic_connector_pins": pair.negative_pins,
        f"{prefix}_negative_generic_pin_functions": pair.negative_functions,
        "connector_native_pin_count": (str(pair.connector_pin_count),),
        "USB_SuperSpeed_map_state": (
            "no source-matched SuperSpeed connector/PHY map covers this pair",
        ),
    }
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_SUPERSPEED_GENERIC_CONNECTOR_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbSuperspeedGenericConnectorCandidate(Candidate):
    """Review prompt bound to exact generic connector and PHY pin assignments."""

    source_evidence: UsbSuperspeedGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbSuperspeedGenericConnectorFindingEvidence,
    ) -> UsbSuperspeedGenericConnectorCandidate:
        pair = source_evidence.pair
        projection = project_usb_superspeed_generic_connector_evidence(source_evidence)
        direction = pair.signal_family.removeprefix("USB SuperSpeed ")
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{pair.connector_reference} / {pair.phy_reference}: generic pins match "
                f"USB SuperSpeed {direction} pair"
            ),
            message=(
                "Native assignments place generic connector contacts on both exact P and N nets "
                f"of one recognized USB SuperSpeed {direction} PHY pair. Review the connector "
                "type, exact pinout, and intended interface, then author a SuperSpeed map if "
                "applicable. This prompt does not identify the connector as USB, infer generic "
                "pin functions, establish a complete USB path or PCB copper, or determine how "
                "power or reference pins should be connected."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_superspeed_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "USB SuperSpeed generic-connector evidence must match its source projection"
            )
