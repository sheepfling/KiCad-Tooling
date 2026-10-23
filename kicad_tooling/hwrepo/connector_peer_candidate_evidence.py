"""Review messages and source evidence for repeated connector-pin findings."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_coverage_models import ConnectorMappedPinEvidence
from .connector_identity import power_function_key
from .connector_peer_pin_models import SimilarConnectorPinGroup
from .models import NetlistContract


def connector_group_message(group: SimilarConnectorPinGroup) -> str:
    """Describe why a repeated-pin group needs review without declaring intent."""
    if group.return_comparison_group is not None:
        scope = (
            " This comparison is scoped to source-reviewed return-comparison group "
            f"{group.return_comparison_group}; grouping scopes comparisons only and does not "
            "establish continuity, bonding, or electrical isolation."
        )
    elif group.peer_assignment_group is not None:
        scope = (
            " This comparison is scoped to source-reviewed peer-assignment group "
            f"{group.peer_assignment_group}."
        )
    else:
        scope = ""
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        return (
            "Connector supply contacts with the same source-reviewed voltage domain "
            f"({group.reviewed_voltage_domain}) use different or missing nets. Review whether "
            "they share a rail, are intentionally switched or isolated, or have independent "
            "sources; this role and domain classification does not require commonality." + scope
        )
    if group.function == "ground/return":
        return (
            "Connector return pins identified by symbol functions or the source-matched project "
            "interface map use different or missing nets. Review whether the domains should be "
            "common, bonded, or intentionally isolated; role classification alone does not "
            "require commonality." + scope
        )
    if power_function_key(group.function) is not None:
        return (
            "Matching connector supply pins use different or missing nets. Review whether they "
            "share a rail, are intentionally separate, or have independent supplies." + scope
        )
    return (
        "Matching connector pin functions use different or missing nets. Review the intended "
        "pinout and signal relationship." + scope
    )


def connector_group_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    """Add authored comparison-scope and mapped-role evidence to a lint finding."""
    evidence: dict[str, tuple[str, ...]] = {}
    if group.peer_assignment_group is not None:
        evidence.update(
            {
                "peer_assignment_group": (group.peer_assignment_group,),
                "peer_assignment_basis": group.peer_assignment_basis,
            }
        )
    if group.return_comparison_group is not None:
        evidence.update(
            {
                "return_comparison_group": (group.return_comparison_group,),
                "return_comparison_basis": group.return_comparison_basis,
            }
        )
    evidence.update(_connector_group_role_source_evidence(group, observed, reviewed_connector_pins))
    return evidence


def _connector_group_role_source_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        domain = str(group.reviewed_voltage_domain)
        sources = [
            f"{pin}: project interface catalog role=supply; "
            f"voltage_domain={domain}; "
            f"native symbol function={observed.pin_functions.get(pin) or '<unnamed>'}"
            for pin in sorted(group.pins)
        ]
        return {
            "role_classification_sources": tuple(sources),
            "reviewed_voltage_domain": (domain,),
        }
    if group.function != "ground/return":
        return {}

    sources: list[str] = []
    has_catalog_role = False
    for pin in sorted(group.pins):
        native_function = observed.pin_functions.get(pin) or "<unnamed>"
        mapped = reviewed_connector_pins.get(pin)
        if mapped is not None and mapped.role == "return":
            has_catalog_role = True
            sources.append(
                f"{pin}: project interface catalog role=return; "
                f"native symbol function={native_function}"
            )
        else:
            sources.append(f"{pin}: native symbol function={native_function}")
    if not has_catalog_role:
        return {}
    return {"role_classification_sources": tuple(sources)}
