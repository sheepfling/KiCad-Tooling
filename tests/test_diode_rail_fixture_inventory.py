"""Keep diode rail native fixtures minimal and source-hash pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_diode_rail_orientation import DIODE_RAIL_FIXTURE_CASES
from kicad_tooling.hwrepo.schematic_geometry import schematic_sheet_references
from tests.design_lint_fixtures.diode_rail_orientation import NATIVE_FIXTURE_SHA256

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_native_fixture_scope_is_minimal_and_hash_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/diode-rail-orientation-native"
    assert {path.name for path in fixture_root.iterdir()} == {
        "README.md",
        "control.kicad_sch",
        "fault.kicad_sch",
        "fault-return.kicad_sch",
    }
    assert set(DIODE_RAIL_FIXTURE_CASES) == set(NATIVE_FIXTURE_SHA256)
    for case, relative in DIODE_RAIL_FIXTURE_CASES.items():
        source = fixture_root.parent / relative
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == NATIVE_FIXTURE_SHA256[case]
        assert schematic_sheet_references(content) == ()
