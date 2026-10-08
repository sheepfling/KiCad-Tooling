"""Pytest coverage for deterministic KiCad netlist parsing."""

from pathlib import Path

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.models import ContractCoachReport
from kicad_tooling.validate import read_netlist


def test_read_netlist_retains_unconnected_and_unnamed_symbol_pin_numbers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "connector-pins.xml"
    path.write_text(
        '<export><components><comp ref="J1"><value>Synthetic</value>'
        '<libsource lib="Synthetic" part="Port"/></comp></components>'
        '<libparts><libpart lib="Synthetic" part="Port"><pins>'
        '<pin num="1" name="TX" type="passive"/>'
        '<pin num="2" name="~" type="open_collector"/>'
        '<pin num="3" name="SHIELD" type="input"/>'
        "</pins></libpart></libparts><nets>"
        '<net name="TX"><node ref="J1" pin="1"/></net>'
        '<net name="unconnected-(J1-SHIELD-Pad3)"><node ref="J1" pin="3"/>'
        "</net></nets></export>",
        encoding="utf-8",
    )

    observed = read_netlist(path)

    assert observed.component_pin_numbers["J1"] == ("1", "2", "3")
    assert observed.nets == {"TX": ("J1.1",)}
    assert observed.unconnected_nets == {"unconnected-(J1-SHIELD-Pad3)": ("J1.3",)}
    assert observed.pin_electrical_types == {
        "J1.1": "passive",
        "J1.2": "open_collector",
        "J1.3": "input",
    }

    report = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="native-unconnected-roundtrip",
        observed=observed,
    )
    assert parse_model_text(report.model_dump_json(), ContractCoachReport) == report
