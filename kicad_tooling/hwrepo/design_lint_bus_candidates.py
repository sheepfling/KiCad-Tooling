"""Coordinate theme-specific bus and signal-pair candidate translators."""

from __future__ import annotations

from .bus_signal_pairs import ComplementaryPinFunctionAliasResolution
from .design_lint_can_candidates import can_candidates
from .design_lint_i2c_candidates import (
    i2c_address_candidates,
    i2c_pullup_candidates,
    i2c_responder_coverage_candidates,
)
from .design_lint_signal_pair_candidates import (
    complementary_signal_candidates,
    named_differential_pair_candidates,
)
from .design_lint_spi_candidates import spi_bias_candidates
from .design_lint_types import Candidate
from .design_lint_unconnected_interface_candidates import unconnected_interface_candidates
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
)
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract
from .pcb_drc_models import PcbDifferentialPairRuleMap


def bus_candidates(
    observed: NetlistContract,
    *,
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
) -> tuple[Candidate, ...]:
    """Coordinate bus and pair checks while preserving their stable output order."""
    return (
        *i2c_pullup_candidates(observed, i2c_pullup_heuristic_coverage),
        *spi_bias_candidates(observed),
        *unconnected_interface_candidates(observed),
        *can_candidates(observed),
        *complementary_signal_candidates(observed, complementary_alias_resolution),
        *named_differential_pair_candidates(observed, pcb_differential_pair_rule_map),
        *i2c_address_candidates(i2c_address_coverage),
        *i2c_responder_coverage_candidates(observed, i2c_address_map),
    )
