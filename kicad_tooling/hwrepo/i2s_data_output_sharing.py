"""Review fitted I2S serial-data output pins sharing one schematic net."""

from __future__ import annotations

from dataclasses import dataclass

from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2s_endpoint_inventory import I2sEndpointInventory, i2s_data_output_function
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import (
    SignalOutputSharingGroup,
    signal_output_sharing_groups,
)

RULE_ID: DesignLintRuleId = "bus.i2s_data_outputs_share_net"


def i2s_data_output_sharing_groups(
    observed: NetlistContract,
) -> tuple[SignalOutputSharingGroup, ...]:
    """Group I2S-context output aliases after the endpoint inventory is complete."""
    inventory = I2sEndpointInventory.from_netlist(observed)
    i2s_references = {
        endpoint.reference.casefold()
        for endpoint in inventory.clock_data_endpoints()
        if i2s_data_output_function(endpoint.data_function)
    }

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if reference.casefold() in i2s_references and i2s_data_output_function(function):
            return "tx", "i2s"
        return None

    return signal_output_sharing_groups(
        observed,
        role_and_channel=role_and_channel,
        expected_role="tx",
        is_supported_reference=is_integrated_circuit_reference,
        require_pin_inventory=True,
        skip_return_like_nets=True,
        exclude_nets_with_incomplete_evidence=True,
    )


@dataclass(frozen=True, slots=True)
class I2sDataOutputSharingEvidence:
    """A current same-net I2S output group projected from the native netlist."""

    observed: NetlistContract
    group: SignalOutputSharingGroup

    def __post_init__(self) -> None:
        if self.group not in i2s_data_output_sharing_groups(self.observed):
            raise ValueError("I2S output-sharing evidence must match the current fitted netlist")


def project_i2s_data_output_sharing_evidence(
    source: I2sDataOutputSharingEvidence,
) -> CandidateEvidenceProjection:
    """Project native endpoint roles and exact net assignment into stable evidence."""
    group = source.group
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "components": group.components,
            "functions": group.functions,
            "pins": group.pins,
            "pin_types": group.pin_types,
            "net": (group.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class I2sDataOutputSharingCandidate(Candidate):
    """Review candidate bound to a current I2S data-output net group."""

    source_evidence: I2sDataOutputSharingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2sDataOutputSharingEvidence,
    ) -> I2sDataOutputSharingCandidate:
        group = source_evidence.group
        projection = project_i2s_data_output_sharing_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=f"{', '.join(group.components)}: I2S data-output pins share {group.net}",
            message=(
                f"Fitted IC I2S serial-data output pins {', '.join(group.pins)} share one "
                f"schematic net ({group.net}) with native pin types "
                f"{', '.join(group.pin_types)}. Review whether the shared output path is "
                "intentional. Tri-state audio buses and other multi-device topologies can be "
                "valid; native function names do not prove driver behavior or required topology."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i2s_data_output_sharing_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I2S output-sharing candidate must preserve its native projection")


def i2s_data_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find multiple fitted I2S serial-data outputs on one exact non-return net."""
    return tuple(
        I2sDataOutputSharingCandidate.from_source_evidence(
            I2sDataOutputSharingEvidence(observed=observed, group=group)
        )
        for group in i2s_data_output_sharing_groups(observed)
    )
