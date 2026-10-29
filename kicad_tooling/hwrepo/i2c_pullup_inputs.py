"""Stable typed inputs for I2C pull-up theme evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract


@dataclass(frozen=True, slots=True)
class I2cPullupSnifferInput:
    """Native observed topology and source-bound project intent for I2C review."""

    observed: NetlistContract
    coverage: I2cPullupHeuristicCoverage

    @classmethod
    def from_legacy_arguments(
        cls,
        observed: NetlistContract,
        coverage: I2cPullupHeuristicCoverage | None,
    ) -> I2cPullupSnifferInput:
        """Normalize pre-typed callers to an explicit not-configured state."""
        return cls(
            observed=observed,
            coverage=coverage or I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
        )
