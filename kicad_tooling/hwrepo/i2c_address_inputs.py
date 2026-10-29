"""I2C address candidate inputs from native observation and authored intent."""

from __future__ import annotations

from dataclasses import dataclass

from .i2c_address_models import I2cAddressCoverageReport, I2cAddressMap
from .models import NetlistContract


@dataclass(frozen=True, slots=True)
class I2cAddressCandidateInput:
    """Keep address-map comparisons and unmapped-responder review in one theme."""

    observed: NetlistContract
    address_map: I2cAddressMap | None
    coverage: I2cAddressCoverageReport

    @classmethod
    def from_candidate_arguments(
        cls,
        observed: NetlistContract,
        address_map: I2cAddressMap | None,
        coverage: I2cAddressCoverageReport | None,
    ) -> I2cAddressCandidateInput:
        """Normalize callers without coverage to an explicit unrequested state."""
        return cls(
            observed=observed,
            address_map=address_map,
            coverage=coverage if coverage is not None else I2cAddressCoverageReport(),
        )
