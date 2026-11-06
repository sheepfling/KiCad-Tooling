"""Source registry for synthetic RS-485 generic-connector fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_support import tooling_checkout_root

RS485_GENERIC_CONNECTOR_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "069f999ac8917ea2e78a0e9b0613024a146288ea8cba88c225caab158c3976bb",
        "control": "a401ca5ec9bbc1ddbaece6a3522eb1af82ada57c34ce6eab235b14d85e474b42",
    }
)


def rs485_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned generic RS-485 connector fault/control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/rs485-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
