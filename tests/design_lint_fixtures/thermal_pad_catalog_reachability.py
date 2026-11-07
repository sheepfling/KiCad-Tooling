"""Reachability cases for mapped and unscoped PCB thermal-pad lint rules."""

from __future__ import annotations

import hashlib

import tests.test_capacitor_hold_up as capacitor_hold_up
import tests.test_pcb_thermal_pad_scope as thermal_pad_scope
import tests.test_spi_connector_return_review as spi_connector_return
from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256
from kicad_tooling.hwrepo.pcb_thermal_via_models import (
    PcbThermalViaCoverageReport,
    PcbThermalViaMap,
)
from kicad_tooling.hwrepo.pcb_thermal_vias import pcb_thermal_via_entries
from tests.pcb_thermal_vias_support import requirement, snapshot


def thermal_pad_catalog_rule_ids() -> set[str]:
    """Exercise existing omitted routes and both new thermal-pad candidates."""
    observed = thermal_pad_scope.observed_netlist()
    authored = PcbThermalViaMap(
        basis="Synthetic reachability map",
        requirements=(
            requirement(pad="U1.1", minimum=2),
            requirement(pad="U1.9").model_copy(update={"id": "u1-scope-pad"}),
        ),
    )
    native = snapshot(((10_000, 0, "F.Cu", "In1.Cu", True),))
    entries = pcb_thermal_via_entries(authored, native)
    snapshot_sha256 = hashlib.sha256(native.model_dump_json().encode("utf-8")).hexdigest()
    report = PcbThermalViaCoverageReport(
        status="INCOMPLETE",
        mode="review",
        map_sha256=map_sha256(authored),
        board_path="synthetic/thermal-pad.kicad_pcb",
        board_sha256=native.board_sha256,
        snapshot_path="build/design-lint/thermal-pad-snapshot.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=native.probe_sha256,
        kicad_version=native.kicad_version,
        image=native.image,
        netlist_sha256="d" * 64,
        entries=entries,
    )
    findings = candidates(
        observed,
        pcb_thermal_via_coverage=report,
        pcb_thermal_via_map=authored,
        is_pcb_project=True,
    )
    return {
        *capacitor_hold_up.catalog_reachable_rule_ids(),
        *(item.rule_id for item in spi_connector_return._report().findings),
        *(item.rule_id for item in findings),
    }
