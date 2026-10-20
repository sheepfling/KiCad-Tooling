"""Project-authored oscillator-output path requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import ElectricalPositive, Identifier, NonEmptyText, Reference, StrictModel


class OscillatorOutputLoadRequirement(StrictModel):
    """One exact fitted load pin on an oscillator output path."""

    reference: Identifier
    pin: Reference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText | None = None
    expected_part_id: Identifier | None = None

    @model_validator(mode="after")
    def pin_belongs_to_declared_load(self) -> OscillatorOutputLoadRequirement:
        if not self.pin.casefold().startswith(f"{self.reference}.".casefold()):
            raise ValueError("Oscillator output load pin must belong to its declared component")
        return self


class OscillatorOutputSeriesResistorRequirement(StrictModel):
    """One reviewed series resistor with an authored nominal value range."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier | None = None
    output_side_pin: Reference
    load_side_pin: Reference
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive

    @model_validator(mode="after")
    def exact_resistor_sides_and_ordered_range(
        self,
    ) -> OscillatorOutputSeriesResistorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(
            not pin.casefold().startswith(prefix)
            for pin in (self.output_side_pin, self.load_side_pin)
        ):
            raise ValueError("Oscillator series-resistor pins must belong to that resistor")
        if self.output_side_pin.casefold() == self.load_side_pin.casefold():
            raise ValueError("Oscillator series-resistor pins must be distinct")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("Oscillator series-resistor value range is reversed")
        return self


class OscillatorOutputPathRequirement(StrictModel):
    """Exact direct or resistor-mediated topology for one module output."""

    id: Identifier
    basis: NonEmptyText
    oscillator_reference: Identifier
    expected_oscillator_value: NonEmptyText
    expected_oscillator_symbol: NonEmptyText
    expected_oscillator_footprint: NonEmptyText
    expected_oscillator_part_id: Identifier | None = None
    output_pin: Reference
    topology: Literal["direct", "series"]
    load_pins: Annotated[tuple[OscillatorOutputLoadRequirement, ...], Field(min_length=1)]
    series_resistor: OscillatorOutputSeriesResistorRequirement | None = None

    @model_validator(mode="after")
    def complete_exact_path(self) -> OscillatorOutputPathRequirement:
        if not self.output_pin.casefold().startswith(f"{self.oscillator_reference}.".casefold()):
            raise ValueError("Oscillator output pin must belong to its declared module")
        if self.topology == "series" and self.series_resistor is None:
            raise ValueError("Series oscillator output topology requires a mapped resistor")
        if self.topology == "direct" and self.series_resistor is not None:
            raise ValueError("Direct oscillator output topology cannot declare a series resistor")
        pins = [self.output_pin, *(item.pin for item in self.load_pins)]
        if self.series_resistor is not None:
            pins.extend((self.series_resistor.output_side_pin, self.series_resistor.load_side_pin))
            if self.series_resistor.reference.casefold() == self.oscillator_reference.casefold():
                raise ValueError("Oscillator module and series resistor references must differ")
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Oscillator output path pins must be unique")
        if len({item.pin.casefold() for item in self.load_pins}) != len(self.load_pins):
            raise ValueError("Oscillator output load pins must be unique")
        return self


class OscillatorOutputPathMap(StrictModel):
    """Reviewed scope for deterministic oscillator output topology checks."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    paths: Annotated[tuple[OscillatorOutputPathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_path_ids_and_outputs(self) -> OscillatorOutputPathMap:
        if len({item.id.casefold() for item in self.paths}) != len(self.paths):
            raise ValueError("Oscillator output path IDs must be unique")
        outputs = {
            (item.oscillator_reference.casefold(), item.output_pin.casefold())
            for item in self.paths
        }
        if len(outputs) != len(self.paths):
            raise ValueError("An oscillator output pin can appear in only one mapped path")
        return self
