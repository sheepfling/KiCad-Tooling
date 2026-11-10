"""Review source-mapped connector supplies assigned to a return net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_supply_return_share_net"


def mapped_supply_return_sharing_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review a fitted connector when mapped supply and return pins share one exact net."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    contacts_by_reference_and_net: dict[
        tuple[str, str], dict[str, list[ConnectorMappedPinEvidence]]
    ] = defaultdict(lambda: {"supply": [], "return": []})
    for pin, mapped in source_matched_connector_pin_evidence(observed, coverage).items():
        reference, separator, _pin_number = pin.rpartition(".")
        if (
            not separator
            or mapped.role not in {"supply", "return"}
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue
        contacts_by_reference_and_net[(reference, mapped.nets[0])][mapped.role].append(mapped)

    candidates: list[Candidate] = []
    for (reference, net_name), roles in sorted(
        contacts_by_reference_and_net.items(),
        key=lambda item: (item[0][0].casefold(), item[0][1].casefold(), item[0]),
    ):
        supplies = tuple(sorted(roles["supply"], key=lambda item: item.component_pin))
        returns = tuple(sorted(roles["return"], key=lambda item: item.component_pin))
        if not supplies or not returns:
            continue

        supply_names = tuple(
            sorted(
                {item.interface_signal for item in supplies},
                key=lambda item: (item.casefold(), item),
            )
        )
        return_names = tuple(
            sorted(
                {item.interface_signal for item in returns},
                key=lambda item: (item.casefold(), item),
            )
        )
        evidence = {
            "component_reference": (reference,),
            "supply_component_pin": tuple(item.component_pin for item in supplies),
            "supply_interface_signal": supply_names,
            "return_component_pin": tuple(item.component_pin for item in returns),
            "return_interface_signal": return_names,
            "interface_role": ("supply", "return"),
            "assigned_net": (net_name,),
            "interface_catalog_sha256": (coverage.interface_catalog_sha256,),
        }
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference}: mapped supply and return contacts share native net {net_name}"
                ),
                message=(
                    f"The current source-matched connector map identifies {', '.join(supply_names)} "
                    f"as supply contacts and {', '.join(return_names)} as return contacts, but the "
                    f"native netlist assigns them to the same net ({net_name}). Review whether the "
                    "assignment creates an unintended supply-to-return short or reflects an "
                    "intentional topology. The mapped roles do not prove required separation, "
                    "electrical intent, or PCB copper continuity."
                ),
                evidence=evidence,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence.items())),
            ),
        )
    )
