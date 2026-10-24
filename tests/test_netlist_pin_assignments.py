"""Regressions for shared deterministic reverse pin/net projection."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.netlist_pin_assignments import netlist_pin_net_index


def test_index_casefolds_pins_and_preserves_all_exact_net_assignments() -> None:
    observed = NetlistContract(
        components={},
        nets={"z_NET": ("U1.1",), "A_NET": ("u1.1", "J1.1")},
    )

    assert netlist_pin_net_index(observed) == {
        "u1.1": {"A_NET", "z_NET"},
        "j1.1": {"A_NET"},
    }
