"""Typed expectations for digest-pinned two-wire same-net fixture lanes."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .hwrepo.design_lint_rule_types import DesignLintRuleId
from .hwrepo.model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class ExpectedPinFunction(StrictModel):
    """One exact native pin function expected from a synthetic fixture."""

    reference: Reference
    function: NonEmptyText


class ExpectedNetAssignment(StrictModel):
    """One expected net and its complete set of attached fixture pins."""

    name: NetName
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]


class SameNetCaseExpectation(StrictModel):
    """Source digest and complete lint result expected for one fault/control case."""

    source_sha256: Digest
    net_assignments: Annotated[tuple[ExpectedNetAssignment, ...], Field(min_length=1)]
    subjects: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def assignments_are_unambiguous(self) -> SameNetCaseExpectation:
        net_names = tuple(item.name.casefold() for item in self.net_assignments)
        if len(set(net_names)) != len(net_names):
            raise ValueError("Expected fixture net names must be unique")
        pins = tuple(pin.casefold() for item in self.net_assignments for pin in item.pins)
        if len(set(pins)) != len(pins):
            raise ValueError("Each expected fixture pin must belong to exactly one net")
        return self


class BusSignalPairFixtureExpectation(StrictModel):
    """Complete immutable contract for one shared bus-pair fixture runner."""

    protocol: Literal["i2c", "i3c", "rs485", "usb", "usb-c"]
    pair_name: Identifier
    rule_id: DesignLintRuleId
    fixture_directory: RepositoryPath
    pin_functions: Annotated[tuple[ExpectedPinFunction, ...], Field(min_length=1)]
    fault: SameNetCaseExpectation
    control: SameNetCaseExpectation

    @field_validator("fixture_directory")
    @classmethod
    def fixture_directory_is_portable(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\\" in value
            or path.is_absolute()
            or path.as_posix() != value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError("Fixture directory must be a portable relative path")
        return value

    @model_validator(mode="after")
    def cases_cover_exact_pin_inventory(self) -> BusSignalPairFixtureExpectation:
        references = tuple(item.reference.casefold() for item in self.pin_functions)
        if len(set(references)) != len(references):
            raise ValueError("Expected fixture pin references must be unique")
        expected_pins = set(references)
        for case in (self.fault, self.control):
            assigned_pins = {pin.casefold() for item in case.net_assignments for pin in item.pins}
            if assigned_pins != expected_pins:
                raise ValueError("Each case must assign every expected pin exactly once")
        return self
