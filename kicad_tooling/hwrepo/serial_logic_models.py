"""Project-authored UART endpoint logic and fixture requirements."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator, model_validator

from .model_primitives import FiniteMeasure, NetName, NonEmptyText, Reference, StrictModel


class SerialPinNetRequirement(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("Serial pin mappings must use COMPONENT.PIN form")
        return value


class SerialLogicOutputLimits(StrictModel):
    """Guaranteed logic-output ranges copied from a reviewed device source."""

    low_minimum_v: FiniteMeasure
    low_maximum_v: FiniteMeasure
    high_minimum_v: FiniteMeasure
    high_maximum_v: FiniteMeasure
    source: NonEmptyText
    conditions: NonEmptyText

    @model_validator(mode="after")
    def ordered_logic_output_ranges(self) -> SerialLogicOutputLimits:
        if not (
            self.low_minimum_v <= self.low_maximum_v < self.high_minimum_v <= self.high_maximum_v
        ):
            raise ValueError("Serial output voltage ranges must be ordered and non-overlapping")
        return self


class SerialLogicInputLimits(StrictModel):
    """Logic receiver thresholds and absolute input limits from a reviewed source."""

    absolute_minimum_v: FiniteMeasure
    low_maximum_v: FiniteMeasure
    high_minimum_v: FiniteMeasure
    absolute_maximum_v: FiniteMeasure
    source: NonEmptyText
    conditions: NonEmptyText

    @model_validator(mode="after")
    def ordered_logic_input_ranges(self) -> SerialLogicInputLimits:
        if not (
            self.absolute_minimum_v
            <= self.low_maximum_v
            < self.high_minimum_v
            <= self.absolute_maximum_v
        ):
            raise ValueError("Serial input absolute limits and logic thresholds must be ordered")
        return self


class SerialLogicLimits(StrictModel):
    """Reviewed electrical limits for UART TX and RX pins."""

    output: SerialLogicOutputLimits
    input: SerialLogicInputLimits


class SerialLabelFixtureExpectedNets(StrictModel):
    """Exact expected signal assignments for the synthetic serial-label lane."""

    rx: Annotated[tuple[Reference, ...], Field(alias="UART.0.RX", min_length=1)]
    tx: Annotated[tuple[Reference, ...], Field(alias="UART.0.TX", min_length=1)]

    @model_validator(mode="after")
    def pins_are_not_shared(self) -> SerialLabelFixtureExpectedNets:
        if set(self.rx) & set(self.tx):
            raise ValueError("UART RX and TX expected-net fixture pins must be distinct")
        return self
