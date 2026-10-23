"""Typed coverage evidence for reviewed I2C pull-up voltage limits."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class I2cPullupVoltageCoverageEntry(StrictModel):
    """Coverage for one fitted I2C endpoint line with a visible local pull-up."""

    status: Literal["COVERED", "OPEN"]
    bus_id: Identifier | None = None
    sda_net: NetName
    scl_net: NetName
    line: Literal["SDA", "SCL"]
    signal_net: NetName
    pullup_rails: tuple[NetName, ...]
    endpoint_pins: tuple[Reference, ...]
    covered_input_pins: tuple[Reference, ...] = ()
    missing_input_pins: tuple[Reference, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def endpoint_scope_is_consistent(self) -> I2cPullupVoltageCoverageEntry:
        if self.sda_net.casefold() == self.scl_net.casefold():
            raise ValueError("I2C voltage coverage requires distinct SDA and SCL nets")
        expected_signal_net = self.sda_net if self.line == "SDA" else self.scl_net
        if self.signal_net.casefold() != expected_signal_net.casefold():
            raise ValueError("I2C voltage coverage line must match its signal net")
        for values, label in (
            (self.pullup_rails, "pull-up rails"),
            (self.endpoint_pins, "endpoint pins"),
            (self.covered_input_pins, "covered pins"),
            (self.missing_input_pins, "missing pins"),
        ):
            if len({value.casefold() for value in values}) != len(values):
                raise ValueError(f"I2C voltage coverage {label} must be unique")
        if not self.pullup_rails or not self.endpoint_pins:
            raise ValueError("I2C voltage coverage needs a visible rail and fitted endpoint")
        endpoint_keys = {pin.casefold() for pin in self.endpoint_pins}
        covered_keys = {pin.casefold() for pin in self.covered_input_pins}
        missing_keys = {pin.casefold() for pin in self.missing_input_pins}
        if covered_keys - endpoint_keys or missing_keys - endpoint_keys:
            raise ValueError("I2C voltage coverage pin sets must be observed endpoints")
        if covered_keys & missing_keys or covered_keys | missing_keys != endpoint_keys:
            raise ValueError("I2C voltage coverage must partition every observed endpoint")
        if self.status == "COVERED" and (self.bus_id is None or self.issues or missing_keys):
            raise ValueError("Covered I2C voltage entries need a complete authored input map")
        if self.status == "OPEN" and not self.issues:
            raise ValueError("Open I2C voltage entries must explain missing coverage")
        return self
