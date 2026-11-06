"""Typed outcomes for electrical analysis, setup, and input inventory."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, PlainSerializer, field_serializer, model_validator

from .command_evidence_models import CommandEvidence
from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)
from .source_state_models import (
    SerializedPathDigestInventory,
    SourceHashInventory,
    SourceState,
)

ElectricalInputBindingRole = Literal[
    "design-source",
    "project-manifest",
    "project-checks",
    "electrical-requirements",
    "simulation-model",
]


def serialize_electrical_command_inventory(
    value: Mapping[str, CommandEvidence],
) -> dict[str, CommandEvidence]:
    return dict(value)


ElectricalCommandInventory: TypeAlias = Annotated[
    Mapping[str, CommandEvidence],
    PlainSerializer(
        serialize_electrical_command_inventory,
        return_type=dict[str, CommandEvidence],
        when_used="always",
    ),
]


class ElectricalInputDigest(StrictModel):
    """One retained digest with each reason it participates in analysis."""

    source_path: RepositoryPath
    source_sha256: Digest
    roles: tuple[ElectricalInputBindingRole, ...]

    @model_validator(mode="after")
    def unique_roles(self) -> ElectricalInputDigest:
        if not self.roles or len(self.roles) != len(set(self.roles)):
            raise ValueError("Electrical input roles must be non-empty and unique")
        return self


class BoundElectricalInputs(StrictModel):
    """Immutable path, digest, and role inventory admitted for one analysis."""

    entries: tuple[ElectricalInputDigest, ...]

    @model_validator(mode="after")
    def unique_paths(self) -> BoundElectricalInputs:
        paths = tuple(entry.source_path for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("Electrical input paths must be unique")
        return self

    @property
    def all_sha256(self) -> SourceHashInventory:
        return MappingProxyType({entry.source_path: entry.source_sha256 for entry in self.entries})

    @property
    def source_sha256(self) -> SourceHashInventory:
        return self._hashes_for_role("design-source")

    @property
    def model_sha256(self) -> SourceHashInventory:
        return self._hashes_for_role("simulation-model")

    def _hashes_for_role(self, role: ElectricalInputBindingRole) -> SourceHashInventory:
        return MappingProxyType(
            {
                entry.source_path: entry.source_sha256
                for entry in self.entries
                if role in entry.roles
            }
        )


class ElectricalCheck(StrictModel):
    id: NonEmptyText
    status: Literal["PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE", "NOT_CONFIGURED"]
    detail: NonEmptyText
    observed: FiniteMeasure | None = None
    unit: str | None = None


class ElectricalAnalysisReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_ANALYSIS"] = "ELECTRICAL_ANALYSIS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    source: SourceState | None = None
    status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    run_directory: str = ""
    input_sha256: SerializedPathDigestInventory = Field(default_factory=dict)
    artifacts_sha256: SerializedPathDigestInventory = Field(default_factory=dict)
    commands: ElectricalCommandInventory = Field(default_factory=dict)
    checks: tuple[ElectricalCheck, ...]
    limits: tuple[str, ...] = (
        "Grounding covers declared schematic pins; copper return paths and physical bonds need review.",
        "PCB return paths report native pad/zone connectivity and declared net ties; they do not prove manufactured continuity or first-article acceptance.",
        "Pin relationships compare schematic nets; net ties and physical continuity need separate review.",
        (
            "I2C pull-up ranges compare direct resistors, exact mapped series chains, and mapped array channels; "
            "optional authored rail-to-input voltage checks compare declared limits and exact pin identity, "
            "but do not verify source values, transients, array internals, or off-board networks."
        ),
        (
            "Optional I2C resistor-window checks use project-authored rail, low-level, sink-current, "
            "bus-capacitance and rise-time inputs with an ideal 30%-to-70% RC model; they do not include "
            "component tolerances, nonlinear or active pull-ups, off-board loading, or measured waveforms."
        ),
        (
            "CAN checks compare declared bus pins, local direct/split paths, DNP options, and any mapped "
            "split midpoint capacitor's nominal value and pins; external hardware, physical bus-end placement, "
            "and capacitor placement, derating, impedance, and EMC need separate evidence."
        ),
        (
            "USB-C checks compare declared CC/VBUS/GND pin assignments, fitted Rp/Rd resistors, exact "
            "controller/protection identity, any authored VBUS component/net map, and an explicitly mapped "
            "nominal port-side VBUS capacitance range; it does not verify capacitor derating, tolerance, "
            "dynamic behavior, device conduction, or PCB/contact continuity, while controller behavior, "
            "PD and protection performance need separate evidence."
        ),
        (
            "Direct serial voltage checks compare authored guaranteed output ranges with receiver thresholds "
            "and absolute limits; cited sources, operating conditions, transients, and device behavior are "
            "not independently validated."
        ),
        (
            "Component voltage-rating checks compare exact mapped part identity and pin/net assignments, "
            "a project-authored maximum stress envelope, a datasheet working rating, and a project-selected "
            "utilization limit; the sources and stress derivation are not independently validated."
        ),
        "Simulation results apply only to the reviewed models, cases, timestep and frequency grid.",
        "Power budgets use simultaneous worst-case loads and engineer-supplied derated path ratings.",
        "Physical startup, thermal behavior, RF/EMC and manufacturing acceptance remain unverified.",
        (
            "Test-access contracts check exact schematic pins and separately check PCB footprint/pad, "
            "net and outer-mask declarations; probe clearance, nearby obstructions, covers and "
            "manufacturing test coverage remain unverified."
        ),
    )

    @model_validator(mode="after")
    def freeze_report_indexes(self) -> ElectricalAnalysisReport:
        object.__setattr__(self, "input_sha256", MappingProxyType(dict(self.input_sha256)))
        object.__setattr__(self, "artifacts_sha256", MappingProxyType(dict(self.artifacts_sha256)))
        object.__setattr__(self, "commands", MappingProxyType(dict(self.commands)))
        return self


class ElectricalSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[ElectricalAnalysisReport, ...]


class ElectricalSetupReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["CREATED"] = "CREATED"
    project_id: Identifier
    contract: RepositoryPath
    changed: tuple[RepositoryPath, ...]
    next_actions: tuple[NonEmptyText, ...]


class ElectricalInputInventory(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["UNREVIEWED"] = "UNREVIEWED"
    build_authorized: Literal[False] = False
    project_id: Identifier
    run_directory: NonEmptyText
    source_sha256: Mapping[RepositoryPath, Digest]
    model_sha256: Mapping[RepositoryPath, Digest]
    next_actions: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def freeze_hash_inventories(self) -> ElectricalInputInventory:
        object.__setattr__(self, "source_sha256", MappingProxyType(dict(self.source_sha256)))
        object.__setattr__(self, "model_sha256", MappingProxyType(dict(self.model_sha256)))
        return self

    @field_serializer("source_sha256", "model_sha256", when_used="json")
    def serialize_hash_inventories(
        self, value: SourceHashInventory
    ) -> dict[RepositoryPath, Digest]:
        return dict(value)
