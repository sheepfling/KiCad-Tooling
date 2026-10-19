"""Project-owned design-lint policy and its shared typed requirements."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .component_role_models import ComponentRoleMap
from .connector_return_distribution_models import ConnectorReturnDistributionMap
from .crystal_network_models import CrystalNetworkMap
from .design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from .external_protection_models import ExternalProtectionMap
from .i2c_address_models import I2cAddressMap
from .ic_decoupling_models import IcDecouplingMap
from .model_primitives import StrictModel
from .pcb_decoupling_models import PcbDecouplingMap
from .pcb_drc_models import PcbDifferentialPairRuleMap, PcbSignalPathRuleMap
from .pcb_keepout_models import PcbKeepoutMap
from .pcb_protection_path_models import PcbProtectionPathMap
from .pcb_reference_plane_models import PcbReferencePlaneMap
from .pcb_required_fitted_reference_models import PcbRequiredFittedReferenceMap
from .pcb_rf_antenna_models import PcbRfModuleAntennaMap
from .pcb_switching_loop_models import PcbSwitchingLoopMap
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceMap
from .pcb_track_width_models import PcbTrackWidthMap
from .power_path_models import PowerPathMap
from .power_sequence_models import PowerSequenceMap
from .rc_filter_models import RcFilterMap
from .regulator_feedback_models import RegulatorFeedbackMap
from .signal_pair_models import ComplementaryPinFunctionAliasMap
from .stm32_pin_map_models import Stm32CubeMxPinMap
from .usb_data_path_models import UsbDataPathMap


class DesignLintPolicy(StrictModel):
    """Project-owned review decisions; no observed netlist values become requirements."""

    schema_version: Literal["1"] = "1"
    rules: tuple[DesignLintRuleOverride, ...] = ()
    ignores: tuple[DesignLintIgnore, ...] = ()
    component_role_map: ComponentRoleMap | None = None
    complementary_pin_function_alias_map: ComplementaryPinFunctionAliasMap | None = None
    stm32_pin_maps: tuple[Stm32CubeMxPinMap, ...] = ()
    i2c_address_map: I2cAddressMap | None = None
    external_protection_map: ExternalProtectionMap | None = None
    usb_data_path_map: UsbDataPathMap | None = None
    power_path_map: PowerPathMap | None = None
    power_sequence_map: PowerSequenceMap | None = None
    ic_decoupling_map: IcDecouplingMap | None = None
    crystal_network_map: CrystalNetworkMap | None = None
    regulator_feedback_map: RegulatorFeedbackMap | None = None
    rc_filter_map: RcFilterMap | None = None
    connector_return_distribution_map: ConnectorReturnDistributionMap | None = None
    pcb_decoupling_map: PcbDecouplingMap | None = None
    pcb_protection_path_map: PcbProtectionPathMap | None = None
    pcb_track_width_map: PcbTrackWidthMap | None = None
    pcb_reference_plane_map: PcbReferencePlaneMap | None = None
    pcb_switching_loop_map: PcbSwitchingLoopMap | None = None
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None
    pcb_signal_path_rule_map: PcbSignalPathRuleMap | None = None
    pcb_keepout_map: PcbKeepoutMap | None = None
    pcb_rf_module_antenna_map: PcbRfModuleAntennaMap | None = None
    pcb_touch_pad_clearance_map: PcbTouchPadClearanceMap | None = None
    pcb_required_fitted_reference_map: PcbRequiredFittedReferenceMap | None = None

    @model_validator(mode="after")
    def unique_decisions(self) -> DesignLintPolicy:
        if len({item.rule_id for item in self.rules}) != len(self.rules):
            raise ValueError("design_lint rule overrides must be unique")
        if len({item.fingerprint for item in self.ignores}) != len(self.ignores):
            raise ValueError("design_lint ignores must have unique fingerprints")
        if len({item.id.casefold() for item in self.stm32_pin_maps}) != len(self.stm32_pin_maps):
            raise ValueError("STM32 CubeMX pin-map IDs must be unique")
        if len({item.reference.casefold() for item in self.stm32_pin_maps}) != len(
            self.stm32_pin_maps
        ):
            raise ValueError("An MCU reference can appear in only one CubeMX pin map")
        return self
