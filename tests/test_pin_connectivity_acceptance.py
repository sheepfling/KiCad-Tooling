"""Fail-closed connector pin requirements using tooling-owned netlist fixtures."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.electrical import pin_relationship_checks
from kicad_tooling.hwrepo.models import PinConnectivityAnalysis, PinRelationshipRule
from kicad_tooling.validate import read_netlist


def export(component: str, *, nets: str = "") -> str:
    return (
        "<export><components>"
        f"{component}"
        "</components><libparts>"
        '<libpart lib="Synthetic" part="Port"><pins>'
        '<pin num="1" name="SIGNAL" type="passive"/>'
        '<pin num="2" name="RESERVED" type="passive"/>'
        "</pins></libpart></libparts>"
        f"<nets>{nets}</nets></export>"
    )


def test_unconnected_requirement_requires_symbol_pin_inventory(tmp_path: Path) -> None:
    requirement = PinConnectivityAnalysis(
        basis="Synthetic approved connector pin disposition",
        rules=(
            PinRelationshipRule(
                id="reserved-pin",
                basis="Pin 2 is intentionally unused on this assembly",
                topology="unconnected",
                pins=("J1.2",),
            ),
        ),
    )
    declared_component = (
        '<comp ref="J1"><value>Synthetic port</value>'
        '<libsource lib="Synthetic" part="Port"/>'
        '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
        "</comp>"
    )
    missing_inventory_component = '<comp ref="J1"><value>Synthetic port</value></comp>'
    netlist_path = tmp_path / "netlist.xml"

    netlist_path.write_text(export(declared_component), encoding="utf-8")
    valid = pin_relationship_checks(requirement, read_netlist(netlist_path))[0]
    assert valid.status == "PASS"

    connected_net = '<net name="SIGNAL"><node ref="J1" pin="2"/></net>'
    netlist_path.write_text(export(declared_component, nets=connected_net), encoding="utf-8")
    connected = pin_relationship_checks(requirement, read_netlist(netlist_path))[0]
    assert connected.status == "FAIL"
    assert "J1.2" in connected.detail

    netlist_path.write_text(export(missing_inventory_component), encoding="utf-8")
    missing = pin_relationship_checks(requirement, read_netlist(netlist_path))[0]
    assert missing.status == "FAIL"
    assert "missing symbol pin inventory=['J1']" in missing.detail
