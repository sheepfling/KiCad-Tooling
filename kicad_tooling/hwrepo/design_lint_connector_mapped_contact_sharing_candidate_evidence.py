"""Typed source records and report projections for mapped connector contacts sharing nets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

MappedContactSharingRole: TypeAlias = Literal["shield", "return", "supply"]
MappedContactSharingRuleId: TypeAlias = Literal[
    "connector.mapped_shield_signal_share_net",
    "connector.mapped_signal_return_share_net",
    "connector.mapped_supply_signal_share_net",
]
SHIELD_SIGNAL_RULE_ID: MappedContactSharingRuleId = "connector.mapped_shield_signal_share_net"
SIGNAL_RETURN_RULE_ID: MappedContactSharingRuleId = "connector.mapped_signal_return_share_net"
SUPPLY_SIGNAL_RULE_ID: MappedContactSharingRuleId = "connector.mapped_supply_signal_share_net"


@dataclass(frozen=True, slots=True)
class MappedConnectorContactsAtNet:
    """Source-matched mapped contacts of one selected role pair on a native net."""

    net_name: str
    primary_role: MappedContactSharingRole
    primary_contacts: tuple[ConnectorMappedPinEvidence, ...]
    signal_contacts: tuple[ConnectorMappedPinEvidence, ...]

    def __post_init__(self) -> None:
        if not self.net_name:
            raise ValueError("Mapped connector contact groups require a native net name")
        if self.primary_role not in {"shield", "return", "supply"}:
            raise ValueError(
                "Mapped contact-sharing primary role must be shield, return, or supply"
            )
        if self.primary_contacts != tuple(
            sorted(self.primary_contacts, key=lambda item: item.component_pin)
        ):
            raise ValueError("Primary mapped contacts must be sorted by component pin")
        if self.signal_contacts != tuple(
            sorted(self.signal_contacts, key=lambda item: item.component_pin)
        ):
            raise ValueError("Signal mapped contacts must be sorted by component pin")


@dataclass(frozen=True, slots=True)
class MappedConnectorContactSharingFindingEvidence:
    """Mapped role contacts on one net, bound to current netlist and complete coverage."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    contacts: MappedConnectorContactsAtNet

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Mapped connector contact sharing requires complete catalog evidence")
        if not self.contacts.primary_contacts or not self.contacts.signal_contacts:
            raise ValueError("Mapped contact sharing requires both source-matched roles")

        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        role_contacts = (
            (self.contacts.primary_role, self.contacts.primary_contacts),
            ("signal", self.contacts.signal_contacts),
        )
        for expected_role, contacts in role_contacts:
            for mapped in contacts:
                if current.get(mapped.component_pin) != mapped:
                    raise ValueError(
                        "Mapped sharing contacts must match current connector coverage"
                    )
                reference = mapped.component_pin.rsplit(".", maxsplit=1)[0]
                if reference.casefold() in dnp_references:
                    raise ValueError(
                        "Unpopulated connectors cannot support contact-sharing findings"
                    )
                if mapped.role != expected_role:
                    raise ValueError("Mapped contact role must match its sharing group")
                if mapped.unconnected_reason is not None or mapped.nets != (
                    self.contacts.net_name,
                ):
                    raise ValueError("Mapped sharing contacts must share one assigned native net")

    @property
    def rule_id(self) -> MappedContactSharingRuleId:
        if self.contacts.primary_role == "shield":
            return SHIELD_SIGNAL_RULE_ID
        if self.contacts.primary_role == "return":
            return SIGNAL_RETURN_RULE_ID
        return SUPPLY_SIGNAL_RULE_ID


def project_mapped_connector_contact_sharing_evidence(
    source: MappedConnectorContactSharingFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed role contacts and catalog identity into stable report fields."""
    primary_prefix = source.contacts.primary_role
    primary_pins = tuple(sorted(item.component_pin for item in source.contacts.primary_contacts))
    primary_names = tuple(
        sorted(
            {item.interface_signal for item in source.contacts.primary_contacts},
            key=str.casefold,
        )
    )
    signal_pins = tuple(sorted(item.component_pin for item in source.contacts.signal_contacts))
    signal_names = tuple(
        sorted(
            {item.interface_signal for item in source.contacts.signal_contacts},
            key=str.casefold,
        )
    )
    return CandidateEvidenceProjection(
        rule_id=source.rule_id,
        evidence={
            f"{primary_prefix}_component_pin": primary_pins,
            f"{primary_prefix}_interface_signal": primary_names,
            "signal_component_pin": signal_pins,
            "signal_interface_signal": signal_names,
            "assigned_net": (source.contacts.net_name,),
            "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
        },
    )


@dataclass(frozen=True, slots=True)
class MappedConnectorContactSharingCandidate(Candidate):
    """Candidate retaining the exact mapped role contacts and current source records."""

    source_evidence: MappedConnectorContactSharingFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedConnectorContactSharingFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedConnectorContactSharingCandidate:
        projection = project_mapped_connector_contact_sharing_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_connector_contact_sharing_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Mapped contact sharing fields must match their typed source projection"
            )
