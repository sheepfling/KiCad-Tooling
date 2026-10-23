"""Review connector pin scopes that leave otherwise comparable peers isolated."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import (
    source_matched_connector_pin_evidence,
    source_matched_connector_return_comparison_groups,
    source_matched_connector_supply_comparison_groups,
)
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import similar_connector_pin_groups
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "connector.return_supply_scope_singleton"


def connector_scope_singleton_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt when a reviewed scope leaves a comparable connector without peers.

    Only source-matched connector pinouts are considered. The rule reports a
    coverage consequence of a scope; it does not ask that pins use the same
    net or imply that the scoped interfaces are electrically related.
    """
    if coverage is None:
        return ()

    pin_evidence = source_matched_connector_pin_evidence(observed, coverage)
    if not pin_evidence:
        return ()

    return_groups = source_matched_connector_return_comparison_groups(observed, coverage)
    supply_groups = source_matched_connector_supply_comparison_groups(observed, coverage)
    candidates: list[Candidate] = []

    for group in similar_connector_pin_groups(
        observed,
        reviewed_connector_pins=pin_evidence,
        include_consistent=True,
    ):
        if group.function == "ground/return":
            scope_kind = "return_comparison_group"
            scope_map = return_groups
            role = "return"
        elif group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
            scope_kind = "supply_comparison_group"
            scope_map = supply_groups
            role = f"supply in voltage domain {group.reviewed_voltage_domain}"
        else:
            # Signal comparison scope remains with its dedicated connector
            # checks. This prompt is limited to mapped power-reference roles.
            continue

        references = tuple(
            sorted(
                {pin.rsplit(".", 1)[0] for pin in group.pins},
                key=lambda reference: (reference.casefold(), reference),
            )
        )
        if len(references) < 2 or any(
            reference.casefold() not in {key.casefold() for key in scope_map}
            for reference in references
        ):
            # Incomplete scopes retain the existing broad comparison.
            continue

        scope_by_reference = {
            reference.casefold(): (scope, basis) for reference, (scope, basis) in scope_map.items()
        }
        references_by_scope: dict[str, set[str]] = defaultdict(set)
        for reference in references:
            scope, _ = scope_by_reference[reference.casefold()]
            references_by_scope[scope.casefold()].add(reference)

        isolated_references = tuple(
            sorted(
                (
                    reference
                    for scoped_references in references_by_scope.values()
                    if len(scoped_references) == 1
                    for reference in scoped_references
                ),
                key=lambda reference: (reference.casefold(), reference),
            )
        )
        if not isolated_references:
            continue

        pin_assignments = tuple(
            sorted(
                (
                    f"{pin}={','.join(nets) if nets else '<unassigned>'}; {scope_kind}={scope}"
                    for pin, nets in group.pins.items()
                    for scope, _ in (scope_by_reference[pin.rsplit(".", 1)[0].casefold()],)
                ),
                key=str.casefold,
            )
        )
        scope_evidence = tuple(
            sorted(
                (
                    f"{reference}: {scope_kind}={scope}; {basis}"
                    for reference in references
                    for scope, basis in (scope_by_reference[reference.casefold()],)
                ),
                key=str.casefold,
            )
        )
        evidence: dict[str, tuple[str, ...]] = {
            "comparison_role": (role,),
            "comparable_references": references,
            "isolated_references": isolated_references,
            "scope_evidence": scope_evidence,
            "mapped_pin_assignments": pin_assignments,
            "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
        }
        if coverage.interface_catalog_path is not None:
            evidence["interface_catalog_path"] = (str(coverage.interface_catalog_path),)
        evidence.update({pin: nets or ("<unassigned>",) for pin, nets in group.pins.items()})
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{role}: reviewed connector scope leaves a comparable reference without peers"
                ),
                message=(
                    "Current source-matched connector pinouts place these otherwise comparable "
                    "contacts into scopes where at least one reference has no peer. The existing "
                    "peer checks do not compare that reference with the other mapped connectors. "
                    "Review whether the narrower scope is intentional or needs adjustment. Scope "
                    "membership does not require a shared net or prove electrical isolation."
                ),
                evidence=evidence,
            )
        )

    return tuple(candidates)
