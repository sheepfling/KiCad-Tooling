"""Read-only resistor-path result contracts for interface heuristics."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import MappingProxyType
from typing import cast

import pytest

from kicad_tooling.hwrepo.resistor_paths import (
    positive_power_nets,
    visible_resistor_paths,
    visible_resistor_pullups,
)
from tests.electrical_i2c_support import i2c_series_pullup_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_resistor_path_apis_return_immutable_tuple_valued_maps() -> None:
    observed = i2c_series_pullup_netlist()
    results = (
        visible_resistor_pullups(observed, include_device_r_symbol=True),
        visible_resistor_paths(observed, positive_power_nets(observed)),
    )

    for paths_by_net in results:
        assert isinstance(paths_by_net, MappingProxyType)
        assert isinstance(paths_by_net["I2C_SDA"], tuple)
        assert tuple(path.references for path in paths_by_net["I2C_SDA"]) == (("R10", "R11"),)
        with pytest.raises(TypeError):
            cast(MutableMapping[str, object], paths_by_net)["OTHER"] = ()
