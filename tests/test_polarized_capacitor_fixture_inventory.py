"""Keep native polarized-capacitor fixtures minimal and source-hash pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_polarized_capacitor import POLARIZED_CAPACITOR_FIXTURE_CASES
from kicad_tooling.hwrepo.schematic_geometry import schematic_sheet_references
from tests.design_lint_fixtures.polarized_capacitor import NATIVE_FIXTURE_SHA256

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_native_fixture_scope_is_minimal_and_hash_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/polarized-capacitor-native"
    assert {path.name for path in fixture_root.iterdir()} == {
        "README.md",
        "control.kicad_sch",
        "fault.kicad_sch",
    }
    assert set(POLARIZED_CAPACITOR_FIXTURE_CASES) == set(NATIVE_FIXTURE_SHA256)
    for case, relative in POLARIZED_CAPACITOR_FIXTURE_CASES.items():
        source = fixture_root.parent / relative
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == NATIVE_FIXTURE_SHA256[case]
        assert schematic_sheet_references(content) == ()
