"""Shared validation primitives for typed repository and lint models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

FiniteMeasure = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeMeasure = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ElectricalPositive = Annotated[float, Field(gt=0, allow_inf_nan=False)]

Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", min_length=1),
]

ResistorReference = Annotated[
    str,
    StringConstraints(pattern=r"^R[A-Z]*[0-9]+$", min_length=2, to_upper=True),
]

Stm32PortPin = Annotated[str, StringConstraints(pattern=r"^P[A-Z][0-9]+$")]

Stm32SymbolPin = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]+$")]

Reference = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*$", min_length=1),
]

Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]

NativePcbUuid = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
]

GitCommit = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")]

RepositoryPath = Annotated[str, StringConstraints(min_length=1)]

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

NetName = Annotated[str, StringConstraints(min_length=1)]

UsbDataPortGroup = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]

TemplateVersion = Annotated[str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]

PositiveCount = Annotated[int, Field(gt=0)]

NonNegativeCount = Annotated[int, Field(ge=0)]

PositiveMeasure = Annotated[float, Field(gt=0)]

CapacitancePf = Annotated[float, Field(gt=0, allow_inf_nan=False)]

NonNegativeCapacitancePf = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class StrictModel(BaseModel):
    """Immutable model with exact fields and no coercion at serialized-data boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_assignment=True,
        populate_by_name=True,
    )
