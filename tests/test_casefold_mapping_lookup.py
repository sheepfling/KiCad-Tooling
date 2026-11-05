"""Exact case-insensitive lookup shared by project mapping services."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import MappingProxyType
from typing import cast

import pytest

from kicad_tooling.hwrepo.casefold_mapping_lookup import (
    casefolded_unique_index,
    lookup_unique_casefold,
)

pytestmark = pytest.mark.design_lint


def test_lookup_returns_the_single_case_insensitive_match() -> None:
    assert lookup_unique_casefold({"U1": "mapped"}, "u1") == "mapped"


def test_lookup_rejects_missing_and_ambiguous_matches() -> None:
    assert lookup_unique_casefold({"U1": "mapped"}, "U2") is None
    assert lookup_unique_casefold({"U1": "first", "u1": "second"}, "U1") is None


@pytest.mark.interface_lint
def test_casefolded_unique_index_is_read_only_and_normalizes_unique_keys() -> None:
    index = casefolded_unique_index({"J1": "connector", "U1": "phy"})

    assert index == {"j1": "connector", "u1": "phy"}
    assert isinstance(index, MappingProxyType)
    with pytest.raises(TypeError):
        cast(MutableMapping[str, str], index)["u2"] = "other"


@pytest.mark.interface_lint
def test_casefolded_unique_index_drops_every_ambiguous_spelling() -> None:
    index = casefolded_unique_index({"J1": "connector", "U1": "first phy", "u1": "second phy"})

    assert index == {"j1": "connector"}
    assert "u1" not in index
