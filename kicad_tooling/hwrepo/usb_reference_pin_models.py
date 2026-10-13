"""Shared exact USB endpoint reference-pin requirements."""

from __future__ import annotations

from pydantic import field_validator

from .model_primitives import NetName, Reference, StrictModel


class UsbReferencePinRequirement(StrictModel):
    """One source-reviewed USB endpoint reference pin and expected native net."""

    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB reference pin mappings must use COMPONENT.PIN form")
        return value
