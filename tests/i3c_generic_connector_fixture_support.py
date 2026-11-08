"""Local hash-pinned sources for the native I3C connector regression."""

from __future__ import annotations

from pathlib import Path

I3C_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault.kicad_sch": "1e82e432628aa3813bfb5a3d99bb195d7e060d3db2a5eb225d4c30c3a8d26d56",
    "control.kicad_sch": "1fdf183e04d63df0eca2c65ec61fa2f3b173b9bfe8fb6febe071b3fa82015a1f",
}


def i3c_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned fault/control schematic paths."""
    fixture_root = Path(__file__).parent / "fixtures/design_lint/i3c-generic-connector-native"
    return {Path(name).stem: fixture_root / name for name in I3C_GENERIC_CONNECTOR_SOURCE_HASHES}
