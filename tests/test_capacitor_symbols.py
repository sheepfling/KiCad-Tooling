"""Recognition tests for shared native capacitor-symbol screening."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.capacitor_symbols import is_capacitor_symbol

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.parametrize(
    "symbol",
    (
        "Device:C",
        "Device:C_Small",
        "Device:C_Polarized",
        "Device:CP",
        "Device:CP_Small",
        "Vendor:BulkCapacitor",
        "vendor:CAPACITOR",
        "C",
        "CP_Small",
    ),
)
def test_recognizes_bounded_capacitor_symbol_names(symbol: str) -> None:
    assert is_capacitor_symbol(symbol)


@pytest.mark.parametrize(
    "symbol",
    (
        "",
        "Device:Connector_Generic",
        "Device:Crystal",
        "Vendor:Cap",
        "Device:Circuit",
        ":Device:C",
        "Device:C:Hidden",
    ),
)
def test_rejects_non_capacitor_or_malformed_symbol_names(symbol: str) -> None:
    assert not is_capacitor_symbol(symbol)
