"""Typed source-bound coverage inputs for PCB candidate translation."""

from __future__ import annotations

from dataclasses import dataclass

from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport, PcbSignalPathRuleCoverageReport
from .pcb_keepout_models import PcbKeepoutCoverageReport
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .stm32_pin_map_models import Stm32PinMapCoverageReport


@dataclass(frozen=True, slots=True)
class PcbCandidateInputs:
    """Native PCB measurement and authored requirement coverage."""

    component_inventory: PcbComponentInventoryCoverageReport | None
    decoupling: PcbDecouplingCoverageReport | None
    protection_path: PcbProtectionPathCoverageReport | None
    track_width: PcbTrackWidthCoverageReport | None
    reference_plane: PcbReferencePlaneCoverageReport | None
    switching_loop: PcbSwitchingLoopCoverageReport | None
    differential_pair: PcbDifferentialPairRuleCoverageReport | None
    signal_path: PcbSignalPathRuleCoverageReport | None
    keepout: PcbKeepoutCoverageReport | None
    rf_antenna: PcbRfModuleAntennaCoverageReport | None
    touch_pad_clearance: PcbTouchPadClearanceCoverageReport | None
    stm32_pin_map: Stm32PinMapCoverageReport | None
