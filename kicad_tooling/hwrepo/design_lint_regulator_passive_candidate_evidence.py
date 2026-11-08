"""Source-bound evidence for authored regulator passive topology findings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .netlist_contract_models import NetlistContract
from .regulator_passive_checks import (
    regulator_passive_pin_role_issues,
    regulator_passive_topology_issues,
)
from .regulator_passive_models import (
    RegulatorPassiveTopologyMap,
    RegulatorPassiveTopologyRequirement,
)


@dataclass(frozen=True, slots=True)
class RegulatorPassiveTopologyFindingEvidence:
    """One mismatch revalidated against its complete authored map and netlist."""

    observed: NetlistContract
    requirements: RegulatorPassiveTopologyMap
    topology_id: str
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        requirement = self.requirement
        current = tuple(
            (current_id, current_issues)
            for current_id, current_issues in regulator_passive_topology_issues(
                self.requirements,
                self.observed,
            )
            if current_id.casefold() == self.topology_id.casefold()
        )
        if requirement.id != self.topology_id or len(current) != 1:
            raise ValueError("Regulator passive evidence requires one current topology mismatch")
        if current[0][1] != self.issues or not self.issues:
            raise ValueError("Regulator passive issues must match the current map and netlist")

    @property
    def requirement(self) -> RegulatorPassiveTopologyRequirement:
        """Return the exact project-authored topology retained by this source."""
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.topology_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator passive evidence requires one authored topology")
        return matches[0]

    @property
    def component_references(self) -> tuple[str, ...]:
        """Return the existing sorted identity projection for every mapped variant."""
        requirement = self.requirement
        references = (
            requirement.regulator.reference,
            *(item.component.reference for item in requirement.required_passives),
            *(
                passive.component.reference
                for alternative in requirement.approved_alternatives
                for passive in alternative.required_passives
            ),
        )
        return tuple(sorted(references, key=str.casefold))

    @property
    def map_sha256(self) -> str:
        """Return the digest of the complete authored regulator map."""
        return hashlib.sha256(self.requirements.model_dump_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RegulatorPassivePinRoleFindingEvidence:
    """One exact native pin-role mismatch under a project-authored topology map."""

    observed: NetlistContract
    requirements: RegulatorPassiveTopologyMap
    topology_id: str
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        current = tuple(
            (current_id, current_issues)
            for current_id, current_issues in regulator_passive_pin_role_issues(
                self.requirements,
                self.observed,
            )
            if current_id.casefold() == self.topology_id.casefold()
        )
        if (
            self.requirement.id != self.topology_id
            or len(current) != 1
            or current[0][1] != self.issues
            or not self.issues
        ):
            raise ValueError("Regulator pin-role evidence must match the current map and netlist")

    @property
    def requirement(self) -> RegulatorPassiveTopologyRequirement:
        """Return the exact project-authored topology retained by this source."""
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.topology_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator pin-role evidence requires one authored topology")
        return matches[0]

    @property
    def component_references(self) -> tuple[str, ...]:
        """Return identities for all components covered by the authored topology variants."""
        requirement = self.requirement
        references = (
            requirement.regulator.reference,
            *(item.component.reference for item in requirement.required_passives),
            *(
                passive.component.reference
                for alternative in requirement.approved_alternatives
                for passive in alternative.required_passives
            ),
        )
        return tuple(sorted(references, key=str.casefold))

    @property
    def map_sha256(self) -> str:
        """Return the digest of the complete authored regulator map."""
        return hashlib.sha256(self.requirements.model_dump_json().encode("utf-8")).hexdigest()
