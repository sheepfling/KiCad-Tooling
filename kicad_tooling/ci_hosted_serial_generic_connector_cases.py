"""Source registry for synthetic generic-connector UART native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

SERIAL_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "da296b82788c0db25161152488375adab6b06a42c34e73ed332a8452d8084418",
    "fault": "718423c9b69dc7e42233700246ce111731b64c8f63d253e4ca1c4d92d2520dbc",
}


def serial_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned UART connector fault and named control sources."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/serial-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
