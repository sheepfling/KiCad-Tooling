"""Digest-pinned native fixture adapter for I2C SDA/SCL same-net review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def i2c_sda_scl_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports and I2C same-net review evidence."""
    if (version, image) not in I2C_NATIVE_TOOLCHAINS:
        raise ValueError(f"I2C same-net fixtures do not cover KiCad {version} with this image")
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="i2c",
        rule_id="bus.i2c_sda_scl_same_net",
        fixture_directory="i2c-sda-scl-same-net",
        source_hashes={
            "fault": "e45583f123b62fe0769d19e5ffd08200510b9abb44afb97d6a8fc269ed3e84b6",
            "control": "a6ef0cf9ed06fe027c53a4d57624b0a72d244de75e1266b8df0ded924e378681",
        },
        expected_pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        expected_nets={
            "fault": {"I2C_SHARED": ("U1.1", "U1.2")},
            "control": {"I2C_SDA": ("U1.1",), "I2C_SCL": ("U1.2",)},
        },
        expected_subjects={
            "fault": ("U1: I2C SDA/SCL pins share I2C_SHARED",),
            "control": (),
        },
    )
