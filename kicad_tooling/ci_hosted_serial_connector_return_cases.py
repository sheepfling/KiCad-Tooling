"""Source registry for the synthetic two-pin UART return review fixture."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

SERIAL_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "1baf002bfa066a4755235fefa448430d3d2a46dff544ab9b400f07d4a4fddaaa",
    "fault": "69204e6f3a9bc0495f3255289f2aba5a16af66b425832e8427ad1d0d120c329c",
}


def serial_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned UART missing-return fault and named control."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/serial-connector-return-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
