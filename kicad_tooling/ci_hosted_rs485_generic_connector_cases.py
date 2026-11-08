"""Source registry for synthetic RS-485 generic-connector fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_support import tooling_checkout_root

RS485_GENERIC_CONNECTOR_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "f02d67f4dc6f8e4cef05cadb35f76775eeb3bbd8ed8f79a9cc40234d6d0fc9d8",
        "control": "e4c3fb8385e5967599117d4eac47dbd98a8f37db0e32778cf9e1499bfe038503",
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
