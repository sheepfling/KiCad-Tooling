"""Typed source evidence for named footprint-similar connector divergences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_footprint_peer_assignments import (
    connector_footprint_peer_pin_assignments,
    connector_footprint_peer_pin_net_map,
)
from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    ConnectorFootprintPeerPinInventory,
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinNamedDivergence,
    ConnectorFootprintPeerPinScanSource,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    partition_peer_assignments,
    pin_function_is_generic,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorFootprintNamedDivergenceRuleId: TypeAlias = Literal[
    "connector.footprint_named_power_input_assignment_divergence",
    "connector.footprint_named_power_output_assignment_divergence",
    "connector.footprint_named_signal_assignment_divergence",
    "connector.footprint_named_passive_assignment_divergence",
]

_RULE_ELECTRICAL_TYPES: dict[ConnectorFootprintNamedDivergenceRuleId, frozenset[str]] = {
    "connector.footprint_named_power_input_assignment_divergence": frozenset({"power_in"}),
    "connector.footprint_named_power_output_assignment_divergence": frozenset({"power_out"}),
    "connector.footprint_named_signal_assignment_divergence": SIGNAL_ELECTRICAL_TYPES,
    "connector.footprint_named_passive_assignment_divergence": frozenset({"passive"}),
}


def _group_and_inventory(
    source: ConnectorFootprintPeerPinScanSource,
    divergence: ConnectorFootprintPeerPinNamedDivergence,
) -> tuple[
    ConnectorFootprintPeerGroup,
    tuple[str, ...],
    ConnectorFootprintPeerPinInventory,
]:
    references = tuple(
        sorted(
            {pin.rpartition(".")[0] for pin in divergence.assignments},
            key=lambda item: (item.casefold(), item),
        )
    )
    if len(references) < 2 or any(
        "." not in pin or pin.rpartition(".")[2].casefold() != divergence.pin_number.casefold()
        for pin in divergence.assignments
    ):
        raise ValueError("Connector named divergence must retain multiple native peer pins")

    peer_group = next(
        (
            group
            for group in connector_footprint_peer_candidate_groups(
                source.observed,
                source.declared_references,
            )
            if group.value == divergence.value
            and group.footprint == divergence.footprint
            and {reference.casefold() for reference in references}
            <= {reference.casefold() for reference in group.references}
        ),
        None,
    )
    if peer_group is None:
        raise ValueError("Connector named divergence peers must match a current footprint group")

    inventory = complete_connector_footprint_peer_pin_inventory(
        source.observed,
        peer_group.references,
    )
    if inventory is None:
        raise ValueError("Connector named divergence requires a current complete pin inventory")
    return peer_group, references, inventory


def _validate_current_divergence(
    source: ConnectorFootprintPeerPinScanSource,
    divergence: ConnectorFootprintPeerPinNamedDivergence,
) -> None:
    peer_group, references, inventory = _group_and_inventory(source, divergence)
    observed = source.observed
    pin_nets = connector_footprint_peer_pin_net_map(observed)
    components = {reference.casefold(): item for reference, item in observed.components.items()}
    symbols = {reference.casefold(): item for reference, item in observed.component_symbols.items()}
    functions = {pin.casefold(): item for pin, item in observed.pin_functions.items()}
    electrical_types = {pin.casefold(): item for pin, item in observed.pin_electrical_types.items()}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}

    for reference in peer_group.references:
        component = components.get(reference.casefold())
        if (
            component is None
            or reference.casefold() in unpopulated
            or component.value.strip() != divergence.value
            or component.footprint.strip() != divergence.footprint
            or component.part_id is not None
            or symbols.get(reference.casefold()) is None
        ):
            raise ValueError("Connector named divergence identity must match current fitted peers")

    current_symbols = tuple(
        sorted(
            {symbols[reference.casefold()] for reference in references},
            key=lambda item: (item.casefold(), item),
        )
    )
    if current_symbols != divergence.symbols or len(current_symbols) < 2:
        raise ValueError("Connector named divergence must retain current distinct native symbols")

    current_functions: list[str] = []
    current_types: list[str] = []
    for pin_number in inventory.pin_numbers:
        pin_functions = tuple(
            functions.get(
                f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}".casefold()
            )
            for reference in peer_group.references
        )
        pin_types = tuple(
            electrical_types.get(
                f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}".casefold()
            )
            for reference in peer_group.references
        )
        if (
            any(value is None or not value.strip() for value in (*pin_functions, *pin_types))
            or len({value.strip().casefold() for value in pin_functions if value is not None}) != 1
            or len({value.strip().casefold() for value in pin_types if value is not None}) != 1
        ):
            raise ValueError("Connector named divergence requires matching current pin metadata")
        if pin_number.casefold() == divergence.pin_number.casefold():
            for reference in references:
                display_number = inventory.displayed_numbers_by_reference[reference.casefold()][
                    pin_number.casefold()
                ]
                function = functions.get(f"{reference}.{display_number}".casefold())
                pin_type = electrical_types.get(f"{reference}.{display_number}".casefold())
                if function is not None:
                    current_functions.append(function)
                if pin_type is not None:
                    current_types.append(pin_type)

    if not current_functions or not current_types:
        raise ValueError("Connector named divergence pin must remain in the current inventory")
    if (
        current_functions[0] != divergence.pin_function
        or current_types[0] != divergence.pin_electrical_type
        or any(
            value.strip().casefold() != current_functions[0].strip().casefold()
            for value in current_functions
        )
        or any(
            value.strip().casefold() != current_types[0].strip().casefold()
            for value in current_types
        )
    ):
        raise ValueError("Connector named divergence metadata must match the current source")

    representative_number = inventory.pin_numbers[0]
    representative_assignments = {
        f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][representative_number.casefold()]}": ()
        for reference in peer_group.references
    }
    scoped_references = {reference.casefold() for reference in references}
    matching_scope = next(
        (
            scope
            for scope in partition_peer_assignments(
                representative_assignments,
                source.peer_assignment_groups,
            )
            if {pin.rpartition(".")[0].casefold() for pin in scope.assignments_by_pin}
            == scoped_references
        ),
        None,
    )
    if matching_scope is None or (
        matching_scope.peer_assignment_group != divergence.peer_assignment_group
        or matching_scope.peer_assignment_basis != divergence.peer_assignment_basis
    ):
        raise ValueError(
            "Connector named divergence scope must match the current authored grouping"
        )

    current_assignments = {
        reference.casefold(): connector_footprint_peer_pin_assignments(
            pin_nets,
            f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][divergence.pin_number.casefold()]}",
        )
        for reference in references
    }
    expected_assignments = {
        pin.rpartition(".")[0].casefold(): connector_footprint_peer_pin_assignments(pin_nets, pin)
        for pin in divergence.assignments
    }
    if current_assignments != expected_assignments or any(
        len(nets) != 1 for nets in current_assignments.values()
    ):
        raise ValueError("Connector named divergence assignments must match current native nets")
    if len({nets[0] for nets in current_assignments.values()}) < 2:
        raise ValueError("Connector named divergence requires distinct current native nets")

    current_anchors = tuple(
        sorted(
            pin_number
            for pin_number in inventory.pin_numbers
            if len(
                {
                    connector_footprint_peer_pin_assignments(
                        pin_nets,
                        f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}",
                    )
                    for reference in references
                }
            )
            == 1
            and all(
                len(
                    connector_footprint_peer_pin_assignments(
                        pin_nets,
                        f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}",
                    )
                )
                == 1
                for reference in references
            )
        )
    )
    if current_anchors != divergence.common_anchor_pin_numbers or not current_anchors:
        raise ValueError("Connector named divergence anchors must match the current native nets")


@dataclass(frozen=True, slots=True)
class ConnectorFootprintNamedDivergenceEvidence:
    """Named pin divergence and its exact native scan source."""

    divergence: ConnectorFootprintPeerPinNamedDivergence
    rule_id: ConnectorFootprintNamedDivergenceRuleId

    def __post_init__(self) -> None:
        expected_type = _RULE_ELECTRICAL_TYPES[self.rule_id]
        if self.divergence.pin_electrical_type.strip().casefold() not in expected_type:
            raise ValueError("Connector divergence rule must match native electrical type")
        if (
            pin_function_is_generic(self.divergence.pin_function)
            or is_named_supply_function(self.divergence.pin_function)
            or is_return_function(self.divergence.pin_function)
        ):
            raise ValueError("Connector divergence requires an explicit named contact")
        _validate_current_divergence(self.divergence.source, self.divergence)


def project_connector_footprint_named_divergence(
    source: ConnectorFootprintNamedDivergenceEvidence,
) -> CandidateEvidenceProjection:
    """Project the existing footprint-peer evidence shape from a validated source."""
    divergence = source.divergence
    evidence: dict[str, tuple[str, ...]] = {
        "value": (divergence.value,),
        "footprint": (divergence.footprint,),
        "pin_number": (divergence.pin_number,),
        "pin_function": (divergence.pin_function,),
        "pin_electrical_type": (divergence.pin_electrical_type.strip().casefold(),),
        "assignments": tuple(f"{pin}={nets[0]}" for pin, nets in divergence.assignments.items()),
        "symbols": divergence.symbols,
        "common_anchor_pin_numbers": divergence.common_anchor_pin_numbers,
    }
    if divergence.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (divergence.peer_assignment_group,)
        evidence["peer_assignment_basis"] = divergence.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=source.rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorFootprintNamedDivergenceCandidate(Candidate):
    """Finding retaining the validated named peer and source scan context."""

    source_evidence: ConnectorFootprintNamedDivergenceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintNamedDivergenceEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorFootprintNamedDivergenceCandidate:
        projection = project_connector_footprint_named_divergence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_footprint_named_divergence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Connector divergence fields must match typed source projection")


def connector_footprint_named_divergence_candidate(
    divergence: ConnectorFootprintPeerPinNamedDivergence,
    rule_id: ConnectorFootprintNamedDivergenceRuleId,
    *,
    subject: str,
    message: str,
) -> ConnectorFootprintNamedDivergenceCandidate:
    """Build one candidate from a current named footprint-peer divergence."""
    source_evidence = ConnectorFootprintNamedDivergenceEvidence(
        divergence=divergence,
        rule_id=rule_id,
    )
    return ConnectorFootprintNamedDivergenceCandidate.from_source_evidence(
        source_evidence,
        subject=subject,
        message=message,
    )
