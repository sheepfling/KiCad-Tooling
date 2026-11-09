"""Source-bound evidence for mapped active regulator-support pin roles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .netlist_contract_models import NetlistContract
from .regulator_support_checks import (
    regulator_support_pin_net_coverage_issues,
    regulator_support_pin_net_issues,
    regulator_support_pin_role_issues,
)
from .regulator_support_models import (
    RegulatorSupportComponentRequirement,
    RegulatorSupportNetComponentRequirement,
    RegulatorSupportPinNetMap,
    RegulatorSupportPinNetTopologyRequirement,
    RegulatorSupportPinRoleMap,
    RegulatorSupportTopologyRequirement,
)


@dataclass(frozen=True, slots=True)
class RegulatorSupportPinRoleFindingEvidence:
    """One active-support mismatch revalidated against its full authored map."""

    observed: NetlistContract
    requirements: RegulatorSupportPinRoleMap
    topology_id: str
    component_reference: str
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        current = tuple(
            (current_topology, current_reference, current_issues)
            for current_topology, current_reference, current_issues in (
                regulator_support_pin_role_issues(self.requirements, self.observed)
            )
            if current_topology.casefold() == self.topology_id.casefold()
            and current_reference.casefold() == self.component_reference.casefold()
        )
        if (
            self.topology.id != self.topology_id
            or self.component.reference != self.component_reference
            or len(current) != 1
            or current[0][2] != self.issues
            or not self.issues
        ):
            raise ValueError("Regulator-support evidence must match the current map and netlist")

    @property
    def topology(self) -> RegulatorSupportTopologyRequirement:
        """Return the exact authored regulator support topology."""
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.topology_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support evidence requires one authored topology")
        return matches[0]

    @property
    def component(self) -> RegulatorSupportComponentRequirement:
        """Return the exact authored active component behind this finding."""
        matches = tuple(
            item
            for item in self.topology.components
            if item.reference.casefold() == self.component_reference.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support evidence requires one authored component")
        return matches[0]

    @property
    def map_sha256(self) -> str:
        """Return the digest of the complete project-authored support-role map."""
        return hashlib.sha256(self.requirements.model_dump_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RegulatorSupportPinNetFindingEvidence:
    """One active-support pin-net mismatch revalidated against map and netlist."""

    observed: NetlistContract
    requirements: RegulatorSupportPinNetMap
    topology_id: str
    component_reference: str
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        current = tuple(
            (current_topology, current_reference, current_issues)
            for current_topology, current_reference, current_issues in (
                regulator_support_pin_net_issues(self.requirements, self.observed)
            )
            if current_topology.casefold() == self.topology_id.casefold()
            and current_reference.casefold() == self.component_reference.casefold()
        )
        if (
            self.topology.id != self.topology_id
            or self.component.reference != self.component_reference
            or len(current) != 1
            or current[0][2] != self.issues
            or not self.issues
        ):
            raise ValueError(
                "Regulator-support net evidence must match the current map and netlist"
            )

    @property
    def topology(self) -> RegulatorSupportPinNetTopologyRequirement:
        """Return the exact authored topology behind the finding."""
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.topology_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support net evidence requires one authored topology")
        return matches[0]

    @property
    def component(self) -> RegulatorSupportNetComponentRequirement:
        """Return the exact active component behind this finding."""
        matches = tuple(
            item
            for item in self.topology.components
            if item.reference.casefold() == self.component_reference.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support net evidence requires one authored component")
        return matches[0]

    @property
    def map_sha256(self) -> str:
        """Return the digest of the complete project-authored support-net map."""
        return hashlib.sha256(self.requirements.model_dump_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RegulatorSupportPinNetCoverageFindingEvidence:
    """A source-matched active support component missing a pin-net map entry."""

    observed: NetlistContract
    role_requirements: RegulatorSupportPinRoleMap
    net_requirements: RegulatorSupportPinNetMap | None
    topology_id: str
    component_reference: str
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        current = tuple(
            (topology_id, reference, issues)
            for topology_id, reference, issues in regulator_support_pin_net_coverage_issues(
                self.role_requirements,
                self.net_requirements,
                self.observed,
            )
            if topology_id.casefold() == self.topology_id.casefold()
            and reference.casefold() == self.component_reference.casefold()
        )
        if (
            self.topology.id != self.topology_id
            or self.component.reference != self.component_reference
            or len(current) != 1
            or current[0][2] != self.issues
            or not self.issues
        ):
            raise ValueError(
                "Regulator-support pin-net coverage evidence must match the current maps and netlist"
            )

    @property
    def topology(self) -> RegulatorSupportTopologyRequirement:
        """Return the role-map topology behind this coverage finding."""
        matches = tuple(
            item
            for item in self.role_requirements.requirements
            if item.id.casefold() == self.topology_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support coverage evidence requires one role topology")
        return matches[0]

    @property
    def component(self) -> RegulatorSupportComponentRequirement:
        """Return the exact active support component behind this coverage finding."""
        matches = tuple(
            item
            for item in self.topology.components
            if item.reference.casefold() == self.component_reference.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Regulator-support coverage evidence requires one role component")
        return matches[0]

    @property
    def maps_sha256(self) -> str:
        """Return a canonical digest of the role map and optional pin-net map."""
        payload = {
            "role_map": _canonical_support_map_json(self.role_requirements),
            "pin_net_map": (
                None
                if self.net_requirements is None
                else _canonical_support_map_json(self.net_requirements)
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_support_map_json(
    requirements: RegulatorSupportPinRoleMap | RegulatorSupportPinNetMap,
) -> str:
    """Serialize authored support maps independent of topology, component, or pin order."""
    topologies = tuple(
        topology.model_copy(
            update={
                "components": tuple(
                    component.model_copy(
                        update={
                            "pins": tuple(
                                sorted(component.pins, key=lambda item: item.pin.casefold())
                            )
                        }
                    )
                    for component in sorted(
                        topology.components, key=lambda item: item.reference.casefold()
                    )
                )
            }
        )
        for topology in sorted(
            requirements.requirements,
            key=lambda item: (item.regulator_reference.casefold(), item.id.casefold()),
        )
    )
    return requirements.model_copy(update={"requirements": topologies}).model_dump_json()
