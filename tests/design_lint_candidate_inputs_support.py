"""Build minimal complete candidate bundles for focused scanner tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from kicad_tooling.hwrepo.design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
    PcbCandidateInputs,
    UsbDataPathCandidateInputs,
)
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.design_lint_control_inputs import ControlCandidateInputs
from kicad_tooling.hwrepo.design_lint_peer_inputs import PeerCandidateInputs
from kicad_tooling.hwrepo.design_lint_power_inputs import PowerCandidateInputs
from kicad_tooling.hwrepo.i2c_address_inputs import I2cAddressCandidateInput
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap


def candidate_inputs(
    observed: NetlistContract,
    *,
    usb_map: UsbDataPathMap | None = None,
) -> DesignLintCandidateInputs:
    """Return an otherwise-empty candidate bundle around one observed netlist."""
    return DesignLintCandidateInputs(
        observed=observed,
        catalog=rule_catalog(),
        schematic_geometry=None,
        reviewed_connector_references=(),
        connector=ConnectorCandidateInputs(
            coverage=None,
            return_distribution=None,
            stateful_contact_map=None,
            power_output_review_enabled=True,
        ),
        component=ComponentCandidateInputs(
            peer_pin_assignment_scans=None,
            peer_power_output_review_enabled=True,
        ),
        control=ControlCandidateInputs.from_legacy_arguments(observed, None),
        power=PowerCandidateInputs(
            component_role_map=None,
            power_path_map=None,
            power_sequence_map=None,
            oscillator_output_path_map=None,
            ic_decoupling_map=None,
        ),
        bus=BusCandidateInputs(
            observed=observed,
            i2c_address=I2cAddressCandidateInput.from_candidate_arguments(observed, None, None),
            i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(observed, None),
        ),
        peer=PeerCandidateInputs(
            digital_voltage_context=None,
            digital_voltage_scan=None,
            usb_reference_scan=None,
            serial_reference_scan=None,
            serial_roster=None,
            usb_c_port_roster=None,
        ),
        mapped=MappedCandidateInputs(
            external_protection=None,
            crystal_network=None,
            regulator_feedback=None,
            rc_filter=None,
        ),
        pcb=PcbCandidateInputs(
            component_inventory=None,
            decoupling=None,
            protection_path=None,
            track_width=None,
            reference_plane=None,
            switching_loop=None,
            differential_pair=None,
            signal_path=None,
            keepout=None,
            rf_antenna=None,
            touch_pad_clearance=None,
            stm32_pin_map=None,
        ),
        usb_data_path=UsbDataPathCandidateInputs(authored_map=usb_map),
    )
