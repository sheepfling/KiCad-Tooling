"""Compatibility exports for protocol-specific deterministic bus checks."""

from __future__ import annotations

__all__ = (
    "CanPeerAssignmentDivergence",
    "CanTerminationGap",
    "ComplementaryLineGap",
    "ComplementaryPinFunctionAliasResolution",
    "DirectResistor",
    "I2cLowEquivalentResistance",
    "I2cMultiplePullupRailFamilies",
    "I2cPullupGap",
    "SpiChipSelectBiasGap",
    "UnconnectedInterfacePin",
    "VisiblePullupPath",
    "can_buses_without_local_termination",
    "can_peer_assignment_divergences",
    "can_termination_checks",
    "complementary_signal_gaps",
    "direct_resistors",
    "i2c_buses_with_low_equivalent_pullup_resistance",
    "i2c_buses_with_multiple_pullup_rail_families",
    "i2c_buses_without_local_pullups",
    "i2c_pullup_checks",
    "i2c_pullup_heuristic_coverage",
    "i2c_signal_role",
    "is_active_low_chip_select_function",
    "resistance_ohms",
    "resolve_complementary_pin_function_aliases",
    "spi_active_low_chip_selects_without_pullups",
    "spi_checks",
    "unconnected_interface_pins",
    "usb_c_checks",
    "usb_c_vbus_capacitance_check",
    "usb_data_function_identity",
    "usb_data_function_side",
)

from .bus_signal_pairs import (
    ComplementaryLineGap,
    ComplementaryPinFunctionAliasResolution,
    complementary_signal_gaps,
    resolve_complementary_pin_function_aliases,
    usb_data_function_identity,
    usb_data_function_side,
)
from .bus_signal_roles import (
    UnconnectedInterfacePin,
    i2c_signal_role,
    is_active_low_chip_select_function,
    unconnected_interface_pins,
)
from .can_peer_heuristics import (
    CanPeerAssignmentDivergence,
    can_peer_assignment_divergences,
)
from .can_termination_contract import (
    can_termination_checks,
)
from .can_termination_heuristics import (
    CanTerminationGap,
    can_buses_without_local_termination,
)
from .i2c_pullup_contract import (
    i2c_pullup_checks,
)
from .i2c_pullup_heuristics import (
    I2cLowEquivalentResistance,
    I2cMultiplePullupRailFamilies,
    I2cPullupGap,
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
    i2c_pullup_heuristic_coverage,
)
from .resistor_paths import (
    DirectResistor,
    VisiblePullupPath,
    direct_resistors,
    resistance_ohms,
)
from .spi_bias_heuristics import (
    SpiChipSelectBiasGap,
    spi_active_low_chip_selects_without_pullups,
)
from .spi_contract import (
    spi_checks,
)
from .usb_c_contract import (
    usb_c_checks,
)
from .usb_c_vbus import (
    usb_c_vbus_capacitance_check,
)
