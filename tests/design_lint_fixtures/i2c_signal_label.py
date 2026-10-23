"""Minimal native-netlist contracts for I2C signal-label role checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i2c_signal_label_netlist(*, reversed_labels: bool = False) -> NetlistContract:
    """Create an SDA/SCL control or crossed-label fault."""
    sda_net, scl_net = ("I2C_SCL", "I2C_SDA") if reversed_labels else ("I2C_SDA", "I2C_SCL")
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C controller", footprint="Synthetic:QFN")
        },
        nets={sda_net: ("U1.1",), scl_net: ("U1.2",)},
        component_symbols={"U1": "Synthetic:I2cController"},
        pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        component_pin_numbers={"U1": ("1", "2")},
    )


def i2c_signal_same_net_netlist() -> NetlistContract:
    """Create a synthetic I2C controller whose SDA and SCL share one net."""
    observed = i2c_signal_label_netlist()
    return observed.model_copy(update={"nets": {"I2C_SHARED": ("U1.1", "U1.2")}})
