"""Resolved bus-theme inputs from one observed native netlist."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_pairs import ComplementaryPinFunctionAliasResolution
from .can_peer_reference_scan import CanPeerReferenceScan
from .design_lint_types import Candidate
from .i2c_address_inputs import I2cAddressCandidateInput
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .i2c_pullup_inputs import I2cPullupSnifferInput
from .models import NetlistContract
from .pcb_drc_models import PcbDifferentialPairRuleMap
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .spi_participants import SpiRosterContext
from .spi_peer_reference_scan import SpiPeerReferenceScan


@dataclass(frozen=True, slots=True)
class BusCandidateInputs:
    """Keep independent I2C authorities alongside other bus observations."""

    observed: NetlistContract
    i2c_address: I2cAddressCandidateInput
    i2c_pullup: I2cPullupSnifferInput
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None
    i2c_peer_reference_scan: I2cPeerReferenceScan | None = None
    spi_roster: SpiRosterContext | None = None
    spi_peer_reference_scan: SpiPeerReferenceScan | None = None
    can_peer_reference_scan: CanPeerReferenceScan | None = None
    rs485_peer_reference_scan: Rs485PeerReferenceScan | None = None
    component_peer_findings: tuple[Candidate, ...] = ()
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None
    reviewed_connector_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for observed in (self.i2c_address.observed, self.i2c_pullup.observed):
            if observed is not self.observed and observed != self.observed:
                raise ValueError("Bus candidate inputs must share one observed native netlist")
