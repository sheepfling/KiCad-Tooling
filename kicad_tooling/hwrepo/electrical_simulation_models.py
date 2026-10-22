"""Typed contracts for project-authored electrical budgets and simulator cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .model_primitives import (
    Digest,
    ElectricalPositive,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    NonNegativeMeasure,
    RepositoryPath,
    StrictModel,
)

# Electrical analysis uses explicit engineering limits and model-review bindings.
SpiceExpression = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_().,+*/ ^-]+$", min_length=1),
]


class PowerLoad(StrictModel):
    id: Identifier
    basis: NonEmptyText
    steady_a: NonNegativeMeasure
    startup_a: NonNegativeMeasure
    startup_s: NonNegativeMeasure


class PowerRail(StrictModel):
    id: Identifier
    basis: NonEmptyText
    voltage_v: ElectricalPositive
    continuous_limit_a: ElectricalPositive
    peak_limit_a: ElectricalPositive
    peak_duration_limit_s: ElectricalPositive
    loads: Annotated[tuple[PowerLoad, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_loads(self) -> PowerRail:
        if len({load.id for load in self.loads}) != len(self.loads):
            raise ValueError("Load IDs must be unique within a rail")
        if self.peak_limit_a < self.continuous_limit_a:
            raise ValueError("Peak rating cannot be below continuous rating")
        return self


class SimulationMeasure(StrictModel):
    id: Identifier
    expression: SpiceExpression
    statistic: Literal["min", "max", "avg", "rms", "pp"]
    unit: Literal["V", "A", "W", "dB", "rad", "ratio"]
    start: NonNegativeMeasure
    stop: ElectricalPositive
    minimum: FiniteMeasure | None = None
    maximum: FiniteMeasure | None = None

    @model_validator(mode="after")
    def bounded_window(self) -> SimulationMeasure:
        if self.stop <= self.start:
            raise ValueError("Measurement stop must exceed start")
        if self.minimum is None and self.maximum is None:
            raise ValueError("A measurement needs at least one acceptance limit")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Measurement minimum exceeds maximum")
        return self


class SimulationModel(StrictModel):
    id: Identifier
    basis: NonEmptyText
    deck: RepositoryPath
    # All paths are repository-relative. Includes must be explicitly inventoried.
    model_sha256: Mapping[RepositoryPath, Digest]
    source_sha256: Mapping[RepositoryPath, Digest]
    measures: Annotated[tuple[SimulationMeasure, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def complete_model_binding(self) -> SimulationModel:
        if self.deck not in self.model_sha256 or not self.source_sha256:
            raise ValueError("Bind the deck, all model dependencies, and reviewed design sources")
        if len({item.id for item in self.measures}) != len(self.measures):
            raise ValueError("Measurement IDs must be unique")
        return self


class TransientAnalysis(SimulationModel):
    analysis: Literal["tran"] = "tran"
    step_s: ElectricalPositive
    stop_s: ElectricalPositive

    @model_validator(mode="after")
    def transient_windows(self) -> TransientAnalysis:
        if self.step_s >= self.stop_s:
            raise ValueError("Transient step must be smaller than stop")
        for measure in self.measures:
            if measure.stop > self.stop_s or measure.stop - measure.start < self.step_s:
                raise ValueError(
                    "Transient measurement window is outside the run or below its step"
                )
        return self


class FrequencyAnalysis(SimulationModel):
    analysis: Literal["ac"] = "ac"
    start_hz: ElectricalPositive
    stop_hz: ElectricalPositive
    points_per_decade: Annotated[int, Field(ge=10, le=10000)] = 100

    @model_validator(mode="after")
    def frequency_windows(self) -> FrequencyAnalysis:
        if self.stop_hz <= self.start_hz:
            raise ValueError("Frequency stop must exceed start")
        for measure in self.measures:
            if measure.start < self.start_hz or measure.stop > self.stop_hz:
                raise ValueError("Frequency measurement window is outside the sweep")
        return self


class PowerAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    rails: Annotated[tuple[PowerRail, ...], Field(min_length=1)]
    startup: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]
    steady_state: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_rails(self) -> PowerAnalysis:
        if len({rail.id for rail in self.rails}) != len(self.rails):
            raise ValueError("Power rail IDs must be unique")
        for case in self.startup:
            if not any(m.unit == "A" and m.statistic == "max" for m in case.measures):
                raise ValueError("Every startup case needs a peak current limit")
        for case in self.steady_state:
            if not all(
                any(m.unit == unit and m.statistic == "avg" for m in case.measures)
                for unit in ("A", "W")
            ):
                raise ValueError("Every steady-state case needs average current and power limits")
        return self


class HighFrequencyAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    frequency_hz: ElectricalPositive
    rise_time_s: ElectricalPositive
    sweeps: Annotated[tuple[FrequencyAnalysis, ...], Field(min_length=1)]
    waveforms: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def waveform_resolution(self) -> HighFrequencyAnalysis:
        for case in self.waveforms:
            if case.step_s > min(self.rise_time_s / 10, 1 / (20 * self.frequency_hz)):
                raise ValueError(
                    "Waveform step needs at least 10 samples per rise and 20 per cycle"
                )
            if case.stop_s < 2 / self.frequency_hz:
                raise ValueError("Waveform run must cover at least two nominal cycles")
        return self
