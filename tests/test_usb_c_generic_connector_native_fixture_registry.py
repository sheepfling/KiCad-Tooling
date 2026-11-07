"""Keep native USB-C generic connector sources hash-pinned and local."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_c_generic_connector_cases import (
    USB_C_GENERIC_CONNECTOR_SOURCE_HASHES,
    usb_c_generic_connector_fixture_sources,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]
RULE_ID = "bus.usb_c_generic_connector_cc_pair_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_source_registry_is_hash_pinned_and_tooling_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/usb-c-generic-connector-native"
    sources = usb_c_generic_connector_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {
        case: hashlib.sha256(path.read_bytes()).hexdigest() for case, path in sources.items()
    } == USB_C_GENERIC_CONNECTOR_SOURCE_HASHES
