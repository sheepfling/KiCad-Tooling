"""Keep native generic USB connector fixtures source-hash pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_generic_connector_cases import (
    USB_GENERIC_CONNECTOR_SOURCE_HASHES,
    usb_generic_connector_fixture_sources,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id="bus.usb_generic_connector_phy_pair_review")
def test_native_source_registry_is_hash_pinned_and_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/usb-generic-connector-native"
    sources = usb_generic_connector_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {
        case: hashlib.sha256(path.read_bytes()).hexdigest() for case, path in sources.items()
    } == USB_GENERIC_CONNECTOR_SOURCE_HASHES
