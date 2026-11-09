"""Typed inputs owned by the design-lint power candidate theme."""

from __future__ import annotations

from dataclasses import dataclass

from .capacitor_hold_up_models import CapacitorHoldUpMap
from .component_role_models import ComponentRoleMap
from .ic_decoupling_models import IcDecouplingMap
from .led_current_models import LedCurrentMap
from .oscillator_output_path_models import OscillatorOutputPathMap
from .power_path_models import PowerPathMap
from .power_sequence_models import PowerSequenceMap
from .regulator_passive_models import RegulatorPassiveTopologyMap
from .regulator_support_models import RegulatorSupportPinNetMap, RegulatorSupportPinRoleMap


@dataclass(frozen=True, slots=True)
class PowerCandidateInputs:
    """Authored power, role, decoupling, and sequencing requirements."""

    component_role_map: ComponentRoleMap | None
    power_path_map: PowerPathMap | None
    power_sequence_map: PowerSequenceMap | None
    oscillator_output_path_map: OscillatorOutputPathMap | None
    ic_decoupling_map: IcDecouplingMap | None
    regulator_passive_topology_map: RegulatorPassiveTopologyMap | None = None
    regulator_support_pin_role_map: RegulatorSupportPinRoleMap | None = None
    regulator_support_pin_net_map: RegulatorSupportPinNetMap | None = None
    led_current_map: LedCurrentMap | None = None
    capacitor_hold_up_map: CapacitorHoldUpMap | None = None
