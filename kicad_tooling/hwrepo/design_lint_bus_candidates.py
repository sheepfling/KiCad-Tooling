"""Coordinate theme-specific bus and signal-pair candidate translators."""

from __future__ import annotations

from .bus_signal_pairs import ComplementaryPinFunctionAliasResolution
from .can_peer_reference_scan import CanPeerReferenceScan
from .design_lint_can_candidates import can_candidates
from .design_lint_i2c_candidates import (
    i2c_address_candidates,
    i2c_peer_reference_candidates,
    i2c_pullup_candidates,
    i2c_responder_coverage_candidates,
)
from .design_lint_rs485_candidates import rs485_peer_reference_candidates
from .design_lint_signal_pair_candidates import (
    complementary_signal_candidates,
    named_differential_pair_candidates,
)
from .design_lint_spi_candidates import spi_bias_candidates, spi_peer_reference_candidates
from .design_lint_types import Candidate
from .design_lint_unconnected_interface_candidates import unconnected_interface_candidates
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
)
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract
from .pcb_drc_models import PcbDifferentialPairRuleMap
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .spi_peer_reference_scan import SpiPeerReferenceScan


def bus_candidates(
    observed: NetlistContract,
    *,
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    i2c_peer_reference_scan: I2cPeerReferenceScan | None = None,
    spi_peer_reference_scan: SpiPeerReferenceScan | None = None,
    can_peer_reference_scan: CanPeerReferenceScan | None = None,
    rs485_peer_reference_scan: Rs485PeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
) -> tuple[Candidate, ...]:
    """Coordinate bus and pair checks while preserving their stable output order."""
    return (
        *i2c_pullup_candidates(observed, i2c_pullup_heuristic_coverage),
        *i2c_peer_reference_candidates(
            observed,
            i2c_peer_reference_scan,
            component_peer_findings,
        ),
        *spi_peer_reference_candidates(
            observed,
            spi_peer_reference_scan,
            component_peer_findings,
        ),
        *spi_bias_candidates(observed),
        *unconnected_interface_candidates(observed),
        *can_candidates(observed, can_peer_reference_scan, component_peer_findings),
        *(
            rs485_peer_reference_candidates(rs485_peer_reference_scan, component_peer_findings)
            if rs485_peer_reference_scan is not None
            else ()
        ),
        *complementary_signal_candidates(observed, complementary_alias_resolution),
        *named_differential_pair_candidates(observed, pcb_differential_pair_rule_map),
        *i2c_address_candidates(i2c_address_coverage),
        *i2c_responder_coverage_candidates(observed, i2c_address_map),
    )
