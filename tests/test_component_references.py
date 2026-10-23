"""Bounded component-reference convention tests."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_references import is_capacitor_reference


@pytest.mark.parametrize("reference", ("C1", "CUSB2", "c3", "CABC42"))
def test_recognizes_bounded_capacitor_references(reference: str) -> None:
    assert is_capacitor_reference(reference)


@pytest.mark.parametrize("reference", ("C", "C-1", "C1A", "CCAP", "U1"))
def test_rejects_noncapacitor_or_malformed_references(reference: str) -> None:
    assert not is_capacitor_reference(reference)
