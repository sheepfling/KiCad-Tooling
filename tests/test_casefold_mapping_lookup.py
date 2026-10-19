"""Exact case-insensitive lookup shared by project mapping services."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.casefold_mapping_lookup import lookup_unique_casefold

pytestmark = pytest.mark.design_lint


def test_lookup_returns_the_single_case_insensitive_match() -> None:
    assert lookup_unique_casefold({"U1": "mapped"}, "u1") == "mapped"


def test_lookup_rejects_missing_and_ambiguous_matches() -> None:
    assert lookup_unique_casefold({"U1": "mapped"}, "U2") is None
    assert lookup_unique_casefold({"U1": "first", "u1": "second"}, "U1") is None
