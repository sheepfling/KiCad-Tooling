"""Source registry for synthetic generic-connector CAN native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

CAN_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault": "b2b88fe7275b176ce214b3723d83844bc71549770ebcdfc3f278ba5792a4cc13",
    "control": "2706180c46a92b65bf3055050873e8d9104d43bf88d04b1131cd826ffde818da",
}


def can_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/can-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
