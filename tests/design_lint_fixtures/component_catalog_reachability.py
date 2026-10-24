"""Synthetic component cases that make specialized component rules reachable."""

from __future__ import annotations

from tests import component_peer_pin_support as peer_pin
from tests import test_transformer_winding_same_net as transformer_windings
from tests import test_two_pin_batteries as batteries
from tests import test_two_pin_buzzers as buzzers
from tests import test_two_pin_crystals as crystals
from tests import test_two_pin_diodes as diodes
from tests import test_two_pin_ferrites as ferrites
from tests import test_two_pin_fuses as fuses
from tests import test_two_pin_leds as leds
from tests import test_two_pin_motors as motors
from tests import test_two_pin_passives as passives
from tests import test_two_pin_solar_cells as solar_cells
from tests import test_two_pin_speakers as speakers
from tests import test_two_pin_switches as switches
from tests import test_two_pin_thermocouples as thermocouples


def reachable_component_rule_ids() -> set[str]:
    """Return specialized component rule IDs emitted by their synthetic faults."""
    reports = (
        passives.lint_report(passives.passive_netlist()),
        diodes.lint_report(diodes.diode_netlist()),
        leds.lint_report(leds.led_netlist()),
        buzzers.lint_report(buzzers.buzzer_netlist()),
        speakers.lint_report(speakers.speaker_netlist()),
        batteries.lint_report(batteries.battery_netlist()),
        motors.lint_report(motors.motor_netlist()),
        solar_cells.lint_report(solar_cells.solar_cell_netlist()),
        thermocouples.lint_report(thermocouples.thermocouple_netlist()),
        transformer_windings.lint_report(transformer_windings.transformer_netlist()),
        transformer_windings.lint_report(
            transformer_windings.transformer_netlist(
                first_winding_same_net=False,
                shared_winding_groups=True,
            )
        ),
        crystals.lint_report(crystals.crystal_netlist()),
        fuses.lint_report(fuses.fuse_netlist()),
        peer_pin.lint_report(peer_pin.peer_power_output_netlist()),
        peer_pin.lint_report(
            peer_pin.peer_power_output_netlist(output_electrical_types=("output", "output"))
        ),
        peer_pin.lint_report(peer_pin.peer_signal_input_netlist()),
        peer_pin.lint_report(peer_pin.peer_bidirectional_netlist()),
        ferrites.lint_report(ferrites.ferrite_netlist()),
        switches.lint_report(switches.switch_netlist()),
    )
    return {item.rule_id for report in reports for item in report.findings}
