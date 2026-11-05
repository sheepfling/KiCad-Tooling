"""Regressions for named-rail component pin-function indexes."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import MappingProxyType
from typing import cast, get_type_hints

import pytest

from kicad_tooling.hwrepo.component_named_rail_terminal import (
    ComponentPinFunctionIndex,
    native_pin_function_index,
    normalized_pin_function_index,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


def test_pin_function_indexes_preserve_their_distinct_normalization_contracts() -> None:
    observed = NetlistContract(
        components={},
        nets={},
        pin_functions={"Q1.2": " Base ", "Q1.3": "Emitter"},
    )

    native = native_pin_function_index(observed)
    normalized = normalized_pin_function_index(observed)

    for indexer in (native_pin_function_index, normalized_pin_function_index):
        assert get_type_hints(indexer, include_extras=True)["return"] == (ComponentPinFunctionIndex)
    assert native == {"q1.2": "Base", "q1.3": "Emitter"}
    assert normalized == {"q1.2": "base", "q1.3": "emitter"}
    assert isinstance(native, MappingProxyType)
    assert isinstance(normalized, MappingProxyType)
    with pytest.raises(TypeError):
        cast(MutableMapping[str, str], native)["q1.4"] = "Collector"
    with pytest.raises(TypeError):
        cast(MutableMapping[str, str], normalized)["q1.4"] = "collector"


def test_empty_pin_function_indexes_are_also_read_only() -> None:
    observed = NetlistContract(components={}, nets={})

    for indexer in (native_pin_function_index, normalized_pin_function_index):
        index = indexer(observed)
        assert isinstance(index, MappingProxyType)
        assert not index
        with pytest.raises(TypeError):
            cast(MutableMapping[str, str], index)["q1.2"] = "base"
