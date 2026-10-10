"""Pcb Power report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
)
from tests.design_lint_fixtures.pcb_signal_path import (
    design_lint_report as pcb_signal_path_lint_report,
)
from tests.design_lint_fixtures.pcb_switching_loop import (
    design_lint_report as pcb_switching_loop_lint_report,
)
from tests.pcb_decoupling_support import coverage_report as pcb_decoupling_coverage_report
from tests.pcb_decoupling_support import mapping as pcb_decoupling_mapping
from tests.pcb_decoupling_support import requirement as pcb_decoupling_requirement
from tests.pcb_decoupling_support import snapshot as pcb_decoupling_snapshot
from tests.power_sequence_support import lint_report as power_sequence_lint_report
from tests.power_sequence_support import power_sequence_map, power_sequence_netlist
from tests.test_pcb_keepouts import design_lint_report as pcb_keepout_lint_report
from tests.test_pcb_reference_plane_lint import (
    design_lint_report as pcb_reference_plane_lint_report,
)
from tests.test_power_paths import lint_report as power_path_lint_report
from tests.test_power_paths import power_path_map, power_path_netlist


def pcb_decoupling_lint_report(*, capacitor_distance_nm: int) -> dict[str, object]:
    """Serialize the mapped PCB decoupling boundary through the shared linter."""
    mapped = pcb_decoupling_mapping(pcb_decoupling_requirement(maximum_um=100))
    snapshot = pcb_decoupling_snapshot(distances_nm={"C1": capacitor_distance_nm})
    coverage = pcb_decoupling_coverage_report(mapped, snapshot)
    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-pcb-decoupling-distance-boundary",
        coach(observed, netlist_sha256),
        DesignLintPolicy(pcb_decoupling_map=mapped),
        pcb_decoupling_coverage=coverage,
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    return {
        "pcb_decoupling_distance_fault": pcb_decoupling_lint_report(capacitor_distance_nm=100001),
        "pcb_decoupling_distance_control": pcb_decoupling_lint_report(capacitor_distance_nm=100000),
        "pcb_signal_path_fault": pcb_signal_path_lint_report(fault=True).model_dump(mode="json"),
        "pcb_signal_path_control": pcb_signal_path_lint_report(fault=False).model_dump(mode="json"),
        "pcb_keepout_fault": pcb_keepout_lint_report(fault=True).model_dump(mode="json"),
        "pcb_keepout_control": pcb_keepout_lint_report(fault=False).model_dump(mode="json"),
        "pcb_reference_plane_fault": pcb_reference_plane_lint_report(fault=True).model_dump(
            mode="json"
        ),
        "pcb_reference_plane_control": pcb_reference_plane_lint_report(fault=False).model_dump(
            mode="json"
        ),
        "pcb_switching_loop_route_ambiguity": pcb_switching_loop_lint_report(
            ambiguous_route=True
        ).model_dump(mode="json"),
        "pcb_switching_loop_unique_trace": pcb_switching_loop_lint_report(
            ambiguous_route=False
        ).model_dump(mode="json"),
        "mapped_power_path_fault": power_path_lint_report(
            power_path_netlist(fault="open-element"), power_path_map()
        ).model_dump(mode="json"),
        "mapped_power_path_control": power_path_lint_report(
            power_path_netlist(), power_path_map()
        ).model_dump(mode="json"),
        "mapped_power_sequence_fault": power_sequence_lint_report(
            power_sequence_netlist(fault="open-enable"), power_sequence_map()
        ).model_dump(mode="json"),
        "mapped_power_sequence_control": power_sequence_lint_report(
            power_sequence_netlist(), power_sequence_map()
        ).model_dump(mode="json"),
    }
