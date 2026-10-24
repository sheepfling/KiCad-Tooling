"""Native fault/control case catalog for two-pin component lint."""

from __future__ import annotations

TWO_PIN_COMPONENT_FIXTURE_CASES: dict[str, tuple[str, str, set[str]]] = {
    "same-net-passive": (
        "two-pin-components/same-net.kicad_sch",
        "component.two_pin_passive_same_net",
        {"R1 (10k resistor) has both pins on one net"},
    ),
    "distinct-nets-passive": (
        "two-pin-components/distinct-nets.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-varistor": (
        "two-pin-varistors/same-net-varistor.kicad_sch",
        "component.two_pin_passive_same_net",
        {"RV1 (230V MOV varistor) has both pins on one net"},
    ),
    "distinct-nets-varistor": (
        "two-pin-varistors/distinct-nets-varistor.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor": (
        "two-pin-thermistors/same-net-thermistor.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k NTC thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor": (
        "two-pin-thermistors/distinct-nets-thermistor.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ptc": (
        "two-pin-thermistors/same-net-thermistor-ptc.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k PTC thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ptc": (
        "two-pin-thermistors/distinct-nets-thermistor-ptc.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-us": (
        "two-pin-thermistors/same-net-thermistor-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-us": (
        "two-pin-thermistors/distinct-nets-thermistor-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ntc-us": (
        "two-pin-thermistors/same-net-thermistor-ntc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k NTC US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ntc-us": (
        "two-pin-thermistors/distinct-nets-thermistor-ntc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ptc-us": (
        "two-pin-thermistors/same-net-thermistor-ptc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k PTC US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ptc-us": (
        "two-pin-thermistors/distinct-nets-thermistor-ptc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-mapped-capacitor": (
        "two-pin-components/custom-capacitor-same-net.kicad_sch",
        "component.two_pin_passive_same_net",
        {"C1 (100nF capacitor) has both pins on one net"},
    ),
    "distinct-nets-mapped-capacitor": (
        "cohort-power-pin-dc/custom-capacitor-role-control.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-diode": (
        "two-pin-components/same-net-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        {"D1 (1N4148 diode) has both pins on one net"},
    ),
    "distinct-nets-diode": (
        "two-pin-components/distinct-nets-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        set(),
    ),
    "same-net-led": (
        "two-pin-leds/same-net-led.kicad_sch",
        "component.two_pin_led_same_net",
        {"D1: both LED terminals share LED_TIED"},
    ),
    "distinct-nets-led": (
        "two-pin-leds/distinct-nets-led.kicad_sch",
        "component.two_pin_led_same_net",
        set(),
    ),
    "same-net-mapped-led": (
        "two-pin-leds/mapped-same-net-led.kicad_sch",
        "component.two_pin_led_same_net",
        {"D1: both LED terminals share LED_TIED"},
    ),
    "distinct-nets-mapped-led": (
        "two-pin-leds/mapped-distinct-nets-led.kicad_sch",
        "component.two_pin_led_same_net",
        set(),
    ),
    "same-net-buzzer": (
        "two-pin-buzzers/same-net-buzzer.kicad_sch",
        "component.two_pin_buzzer_same_net",
        {"BZ1: both buzzer terminals share BUZZER_TIED"},
    ),
    "distinct-nets-buzzer": (
        "two-pin-buzzers/distinct-nets-buzzer.kicad_sch",
        "component.two_pin_buzzer_same_net",
        set(),
    ),
    "same-net-speaker": (
        "two-pin-speakers/same-net-speaker.kicad_sch",
        "component.two_pin_speaker_same_net",
        {"LS1: both speaker terminals share SPEAKER_TIED"},
    ),
    "distinct-nets-speaker": (
        "two-pin-speakers/distinct-nets-speaker.kicad_sch",
        "component.two_pin_speaker_same_net",
        set(),
    ),
    "same-net-battery": (
        "two-pin-batteries/same-net-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        {"BT1: both battery terminals share BATTERY_TIED"},
    ),
    "distinct-nets-battery": (
        "two-pin-batteries/distinct-nets-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        set(),
    ),
    "same-net-mapped-battery": (
        "two-pin-batteries/mapped-same-net-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        {"BT1: both battery terminals share BATTERY_TIED"},
    ),
    "distinct-nets-mapped-battery": (
        "two-pin-batteries/mapped-distinct-nets-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        set(),
    ),
    "same-net-motor": (
        "two-pin-motors/same-net-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        {"M1: both motor terminals share MOTOR_TIED"},
    ),
    "distinct-nets-motor": (
        "two-pin-motors/distinct-nets-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        set(),
    ),
    "same-net-mapped-motor": (
        "two-pin-motors/mapped-same-net-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        {"M1: both motor terminals share MOTOR_TIED"},
    ),
    "distinct-nets-mapped-motor": (
        "two-pin-motors/mapped-distinct-nets-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        set(),
    ),
    "same-net-solar-cell": (
        "two-pin-solar-cells/same-net-solar-cell.kicad_sch",
        "component.two_pin_solar_cell_same_net",
        {"BT1: both solar-cell terminals share SOLAR_CELL_TIED"},
    ),
    "distinct-nets-solar-cell": (
        "two-pin-solar-cells/distinct-nets-solar-cell.kicad_sch",
        "component.two_pin_solar_cell_same_net",
        set(),
    ),
    "same-net-thermocouples": (
        "two-pin-thermocouples/same-net-thermocouples.kicad_sch",
        "component.two_pin_thermocouple_same_net",
        {
            "TC1: both thermocouple leads share TC1_TIED",
            "TC2: both thermocouple leads share TC2_TIED",
            "TC3: both thermocouple leads share TC3_TIED",
        },
    ),
    "distinct-nets-thermocouples": (
        "two-pin-thermocouples/distinct-nets-thermocouples.kicad_sch",
        "component.two_pin_thermocouple_same_net",
        set(),
    ),
    "same-net-crystal": (
        "two-pin-crystals/same-net-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        {"Y1 (16 MHz crystal) has both pins on one net"},
    ),
    "distinct-nets-crystal": (
        "two-pin-crystals/distinct-nets-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        set(),
    ),
    "same-net-fuse": (
        "two-pin-fuses/same-net-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A fuse) has both pins on one net"},
    ),
    "distinct-nets-fuse": (
        "two-pin-fuses/distinct-nets-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-polyfuse": (
        "two-pin-fuses/same-net-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A polyfuse) has both pins on one net"},
    ),
    "distinct-nets-polyfuse": (
        "two-pin-fuses/distinct-nets-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-ferrite": (
        "two-pin-ferrites/same-net-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        {"FB1 (600R@100MHz ferrite_bead) has both pins on one net"},
    ),
    "distinct-nets-ferrite": (
        "two-pin-ferrites/distinct-nets-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        set(),
    ),
    "same-net-switch": (
        "two-pin-switches/same-net-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        {"SW1 (Synthetic SPST switch) has both pins on one net"},
    ),
    "distinct-nets-switch": (
        "two-pin-switches/distinct-nets-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        set(),
    ),
}

TWO_PIN_COMPONENT_CANDIDATE_KINDS: dict[str, frozenset[str]] = {
    "component.two_pin_passive_same_net": frozenset(
        {"resistor", "capacitor", "inductor", "varistor", "thermistor"}
    ),
    "component.two_pin_diode_same_net": frozenset({"diode"}),
    "component.two_pin_led_same_net": frozenset({"led"}),
    "component.two_pin_buzzer_same_net": frozenset({"buzzer"}),
    "component.two_pin_speaker_same_net": frozenset({"speaker"}),
    "component.two_pin_battery_same_net": frozenset({"battery"}),
    "component.two_pin_motor_same_net": frozenset({"motor"}),
    "component.two_pin_solar_cell_same_net": frozenset({"solar_cell"}),
    "component.two_pin_thermocouple_same_net": frozenset({"thermocouple"}),
    "component.two_pin_crystal_same_net": frozenset({"crystal"}),
    "component.two_pin_fuse_same_net": frozenset({"fuse", "polyfuse"}),
    "component.two_pin_ferrite_same_net": frozenset({"ferrite_bead"}),
    "component.two_pin_switch_same_net": frozenset({"switch"}),
}


def two_pin_component_fixture_cases_for_rules(
    rule_ids: tuple[str, ...] | None,
) -> dict[str, tuple[str, str, set[str]]]:
    """Select native fault/control fixtures for rule-scoped gates."""
    if rule_ids is None:
        return dict(TWO_PIN_COMPONENT_FIXTURE_CASES)

    requested = frozenset(rule_ids)
    known = frozenset(rule_id for _, rule_id, _ in TWO_PIN_COMPONENT_FIXTURE_CASES.values())
    unknown = requested - known
    if unknown:
        raise ValueError(f"Unknown two-pin component rule IDs: {sorted(unknown)}")
    if not requested:
        raise ValueError("At least one two-pin component rule ID is required")

    selected = {
        name: case for name, case in TWO_PIN_COMPONENT_FIXTURE_CASES.items() if case[1] in requested
    }
    if not selected:
        raise ValueError(f"No native fixture cases found for rules: {sorted(requested)}")
    return selected
