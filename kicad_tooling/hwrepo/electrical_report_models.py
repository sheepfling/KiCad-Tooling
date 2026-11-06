"""Typed outcomes for electrical analysis, setup, and input inventory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .command_evidence_models import CommandEvidence
from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)
from .source_state_models import SourceState


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
    input_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
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
        (
            "Energy-storage hold-up checks use an exact fitted capacitor and project-authored minimum "
            "effective-capacitance fraction, constant-current load, voltage window, and duration; "
            "they do not model ESR, leakage, load transients, charge current, or PCB continuity."
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
