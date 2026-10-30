"""Project-authored voltage-test context, limits, and source-bound review."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel

RequirementState = Literal["CURRENT", "MISSING", "INVALID", "NOT_SELECTED"]


class VoltageCapture(StrictModel):
    schema_version: Literal["1"] = "1"
    kind: NonEmptyText = "voltage_envelope"
    project_id: Identifier
    test_id: Identifier
    source_csv: RepositoryPath
    source_sha256: Digest
    channel: NonEmptyText
    unit: NonEmptyText
    conditions: Mapping[Identifier, NonEmptyText] = Field(min_length=1)
    captured_at: NonEmptyText
    instrument: NonEmptyText
    recorded_origin: Literal["bench", "field", "unknown"] = "unknown"


class VoltageLimit(StrictModel):
    minimum_v: Decimal | None = None
    maximum_v: Decimal | None = None

    @model_validator(mode="after")
    def finite_ordered(self) -> VoltageLimit:
        if self.minimum_v is None and self.maximum_v is None:
            raise ValueError("Voltage limit needs a minimum or maximum")
        if any(
            value is not None and not value.is_finite()
            for value in (self.minimum_v, self.maximum_v)
        ):
            raise ValueError("Voltage limits must be finite")
        if (
            self.minimum_v is not None
            and self.maximum_v is not None
            and self.minimum_v > self.maximum_v
        ):
            raise ValueError("Voltage minimum exceeds maximum")
        return self


class VoltageRequirement(StrictModel):
    schema_version: Literal["1"] = "1"
    kind: NonEmptyText = "voltage_envelope"
    project_id: Identifier
    test_id: Identifier
    channel: NonEmptyText
    unit: NonEmptyText
    conditions: Mapping[Identifier, NonEmptyText] = Field(min_length=1)
    limit: VoltageLimit | None = None
    basis: NonEmptyText


class VoltageViolation(StrictModel):
    sample_index: int = Field(ge=0)
    time_seconds: Decimal
    value_v: Decimal


class PhysicalVoltageReviewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["PHYSICAL_VOLTAGE_REVIEW"] = "PHYSICAL_VOLTAGE_REVIEW"
    build_authorized: Literal[False] = False
    status: Literal[
        "PASS", "FAIL", "NO_LIMIT", "UNIT_MISMATCH", "CONDITION_MISMATCH", "STALE", "UNSUPPORTED"
    ]
    project_id: Identifier
    measured_receipt: RepositoryPath
    measured_receipt_sha256: Digest
    capture_path: RepositoryPath
    capture_sha256: Digest
    requirement_path: RepositoryPath | None = None
    requirement_sha256: Digest | None = None
    requirement_state: RequirementState
    capture: VoltageCapture
    requirement: VoltageRequirement | None = None
    source_current: bool
    source_sha256: Digest
    samples: int = 0
    measured_unit: NonEmptyText | None = None
    observed_min: Decimal | None = None
    observed_max: Decimal | None = None
    violation_count: int = 0
    first_violation: VoltageViolation | None = None
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
