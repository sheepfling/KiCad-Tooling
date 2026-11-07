"""Source registry for synthetic two-pin CAN connector return fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

CAN_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "b2b88fe7275b176ce214b3723d83844bc71549770ebcdfc3f278ba5792a4cc13",
    "fault": "14f85d29d81211f217d520b44057c94fd42b5249b3e243ec284238194be37618",
}


def can_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned two-pin fault and shared multiconductor control."""
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    return {
        "fault": fixture_root / "can-connector-return-native/fault.kicad_sch",
        "control": fixture_root / "can-generic-connector-native/fault.kicad_sch",
    }
