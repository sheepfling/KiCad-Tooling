"""Execution coverage records for authored mapped topology checks."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonEmptyText, NonNegativeCount, StrictModel

MappedTopologyRuleId = Literal[
    "bus.usb_data_path_mismatch",
    "power.mapped_series_path_mismatch",
    "power.mapped_sequence_dependency_mismatch",
    "oscillator.output_load_path_mismatch",
]
MappedTopologyRuleMode = Literal["review", "block", "off"]


class DesignLintMappedCheckRun(StrictModel):
    """Source-bound execution receipt for one optional mapped topology check."""

    rule_id: MappedTopologyRuleId
    status: Literal["NOT_CONFIGURED", "EVALUATED", "BLOCKED"]
    mode: MappedTopologyRuleMode
    map_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    requirement_count: NonNegativeCount = 0
    finding_count: NonNegativeCount = 0
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def execution_matches_map_state(self) -> DesignLintMappedCheckRun:
        if self.status == "NOT_CONFIGURED" and (
            self.map_sha256 is not None
            or self.requirement_count != 0
            or self.finding_count != 0
            or self.reason is None
        ):
            raise ValueError("Unconfigured mapped checks need a reason and zero map counts")
        if self.status == "EVALUATED" and (
            self.map_sha256 is None
            or self.netlist_sha256 is None
            or self.requirement_count == 0
            or self.reason is not None
        ):
            raise ValueError("Evaluated mapped checks need source hashes and authored entries")
        if self.status == "BLOCKED" and (
            self.map_sha256 is None or self.requirement_count == 0 or self.reason is None
        ):
            raise ValueError("Blocked mapped checks need a configured map and blocking reason")
        return self
