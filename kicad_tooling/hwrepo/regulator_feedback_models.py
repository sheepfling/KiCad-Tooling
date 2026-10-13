"""Typed project requirements for regulator feedback checks."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    ResistorReference,
    StrictModel,
)


class RegulatorDividerResistorRequirement(StrictModel):
    """One explicitly mapped side of a conventional regulator feedback divider."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    feedback_pin: Reference
    rail_pin: Reference
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive

    @model_validator(mode="after")
    def local_distinct_pins_and_ordered_range(self) -> RegulatorDividerResistorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not pin.casefold().startswith(prefix) for pin in (self.feedback_pin, self.rail_pin)):
            raise ValueError("Regulator divider pins must belong to their declared resistor")
        if self.feedback_pin.casefold() == self.rail_pin.casefold():
            raise ValueError("Regulator divider feedback and rail pins must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("Regulator divider nominal resistance range is reversed")
        return self


class RegulatorFeedbackRequirement(StrictModel):
    """Reviewed identity, pin map, reference range, and output range for one regulator."""

    id: Identifier
    regulator_reference: Identifier
    expected_regulator_value: NonEmptyText
    expected_regulator_symbol: NonEmptyText
    expected_regulator_footprint: NonEmptyText
    output_pin: Reference
    expected_output_pin_function: NonEmptyText
    feedback_pin: Reference
    expected_feedback_pin_function: NonEmptyText
    output_net: NetName
    reference_net: NetName
    upper_resistor: RegulatorDividerResistorRequirement
    lower_resistor: RegulatorDividerResistorRequirement
    minimum_feedback_reference_voltage_v: ElectricalPositive
    maximum_feedback_reference_voltage_v: ElectricalPositive
    minimum_target_output_voltage_v: ElectricalPositive
    maximum_target_output_voltage_v: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def conventional_divider_is_complete(self) -> RegulatorFeedbackRequirement:
        prefix = f"{self.regulator_reference}.".casefold()
        if any(
            not pin.casefold().startswith(prefix) for pin in (self.output_pin, self.feedback_pin)
        ):
            raise ValueError("Regulator output and feedback pins must belong to the regulator")
        if self.output_pin.casefold() == self.feedback_pin.casefold():
            raise ValueError("Regulator output and feedback pins must differ")
        references = (
            self.regulator_reference,
            self.upper_resistor.reference,
            self.lower_resistor.reference,
        )
        if len({reference.casefold() for reference in references}) != len(references):
            raise ValueError("Regulator and divider component references must be unique")
        pins = (
            self.output_pin,
            self.feedback_pin,
            self.upper_resistor.feedback_pin,
            self.upper_resistor.rail_pin,
            self.lower_resistor.feedback_pin,
            self.lower_resistor.rail_pin,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Regulator feedback pin mappings must be unique")
        if self.output_net.casefold() == self.reference_net.casefold():
            raise ValueError("Regulator output and reference nets must differ")
        if self.minimum_feedback_reference_voltage_v > self.maximum_feedback_reference_voltage_v:
            raise ValueError("Regulator feedback-reference voltage range is reversed")
        if self.minimum_target_output_voltage_v > self.maximum_target_output_voltage_v:
            raise ValueError("Regulator target output voltage range is reversed")
        return self


class RegulatorFeedbackMap(StrictModel):
    """Project-authored scope for deterministic adjustable-regulator checks."""

    basis: NonEmptyText
    regulators: Annotated[tuple[RegulatorFeedbackRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_regulators_and_components(self) -> RegulatorFeedbackMap:
        if len({item.id.casefold() for item in self.regulators}) != len(self.regulators):
            raise ValueError("Regulator feedback IDs must be unique")
        all_components = [
            reference.casefold()
            for item in self.regulators
            for reference in (
                item.regulator_reference,
                item.upper_resistor.reference,
                item.lower_resistor.reference,
            )
        ]
        if len(set(all_components)) != len(all_components):
            raise ValueError("A component can belong to only one regulator feedback map")
        return self
