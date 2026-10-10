"""Source-mapped RF antenna placement and keepout reports for hash-seed tests."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
)
from kicad_tooling.hwrepo.pcb_rf_antenna import pcb_rf_module_antenna_entries
from tests.pcb_rf_antenna_support import (
    area,
    netlist,
    placement,
    requirement,
    snapshot,
)


def _digest(model: BaseModel) -> str:
    return hashlib.sha256(model.model_dump_json().encode("utf-8")).hexdigest()


def antenna_report(*, fault: bool) -> dict[str, object]:
    """Serialize a moved-module/stale-keepout fault or exact geometric control."""
    antenna_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module review",
        requirements=(requirement(),),
    )
    source_netlist = netlist()
    board_placement = placement(position_nm=(1_234_100, -4_900)) if fault else placement()
    observed_board = snapshot(
        board_placement=board_placement,
        rule_areas=(area(),),
    )
    board_sha256 = hashlib.sha256(
        f"synthetic-rf-antenna-position:{board_placement.position_nm}".encode()
    ).hexdigest()
    observed_board = observed_board.model_copy(update={"board_sha256": board_sha256})

    map_sha256 = _digest(antenna_map)
    snapshot_sha256 = _digest(observed_board)
    netlist_sha256 = _digest(source_netlist)
    entries = pcb_rf_module_antenna_entries(antenna_map, source_netlist, observed_board)
    coverage = PcbRfModuleAntennaCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=map_sha256,
        board_path="projects/synthetic/synthetic.kicad_pcb",
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-pcb.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=observed_board.probe_sha256,
        kicad_version=observed_board.kicad_version,
        image=observed_board.image,
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-rf",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=source_netlist,
    )
    report = evaluate(
        "synthetic-rf",
        coach,
        DesignLintPolicy(pcb_rf_module_antenna_map=antenna_map),
        pcb_rf_module_antenna_coverage=coverage,
    )
    return {
        "requirement_sha256": map_sha256,
        "board_sha256": board_sha256,
        "snapshot_sha256": snapshot_sha256,
        "netlist_sha256": netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    return {
        "pcb_antenna_keepout_fault": antenna_report(fault=True),
        "pcb_antenna_keepout_control": antenna_report(fault=False),
    }
