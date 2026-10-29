"""Digest-pinned native fixtures for open SPI clock pins."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog

_SOURCE_HASHES = {
    "control": "cf9cf52926767b8d4a3ba311bec79f669d95a2d3fc4865cdc895ab7b48c9e738",
    "fault": "bd2d07d875ef4b580a8d378dfc92d757c4a856b4ce76b5f2167810184fe0f214",
}


def spi_unconnected_clock_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native fault/control exports and evaluate the default-off review rule."""
    if (version, image) not in SPI_NATIVE_TOOLCHAINS:
        raise ValueError(f"SPI open-clock fixtures do not cover KiCad {version}")
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="spi",
        feature="unconnected-clock",
        rule_id="bus.spi_unconnected_clock_pin",
        fixture_directory="spi-unconnected-clock-native",
        source_hashes=_SOURCE_HASHES,
        expected_nets={
            "control": {"SPI_MOSI": ("U1.2",), "SPI_SCK": ("U1.1",)},
            "fault": {"SPI_MOSI": ("U1.2",)},
        },
        expected_subjects={"control": (), "fault": ("U1.1: SCK",)},
        expected_pin_functions={"U1.1": "SCK", "U1.2": "MOSI"},
        stage_prefix_override="spi-unconnected-clock-fixture",
    )
