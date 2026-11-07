"""Source registry for synthetic two-contact RS-485 return fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

RS485_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "fbdb566de8cb39214c7182b2eec433360b11e48b5b8325ace0484567f5f77a80",
    "fault": "7e4b41a4a9d10ed6358f93effccbca56758fea534e59fc4885450244fafa7886",
}


def rs485_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned two-contact fault and named-role control."""
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    return {
        "fault": fixture_root / "rs485-connector-return-native/fault.kicad_sch",
        "control": fixture_root / "rs485-connector-return-native/control.kicad_sch",
    }
