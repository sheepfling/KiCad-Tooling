"""Project-required PCB fitted-reference reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_required_fitted_reference_checks import (
    required_fitted_reference_map_sha256,
)
from kicad_tooling.hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
)
from tests.design_lint_fixtures.pcb_component_inventory import netlist, snapshot

FOOTPRINT = "Synthetic:Probe_Module"


def required_fitted_report(*, dnp: bool) -> dict[str, object]:
    """Serialize a required-but-DNP fault or exact-fitted control."""
    requirements = PcbRequiredFittedReferenceMap(
        basis="Synthetic approved base assembly",
        requirements=(
            PcbRequiredFittedReference(
                reference="U1",
                footprint=FOOTPRINT,
                basis="must be fitted in the base assembly",
            ),
        ),
    )
    observed = netlist(
        components={"U1": FOOTPRINT},
        dnp=("U1",) if dnp else (),
    )
    board = snapshot(
        "U1",
        schema_version="13",
        footprint_by_reference={"U1": FOOTPRINT},
        dnp_by_reference={"U1": dnp},
    )
    netlist_sha256 = sha256(model_json_bytes(observed)).hexdigest()
    board_sha256 = sha256(f"synthetic-required-fitted-reference:{dnp}".encode()).hexdigest()
    board = board.model_copy(update={"board_sha256": board_sha256})
    snapshot_sha256 = sha256(model_json_bytes(board)).hexdigest()
    coverage = evaluate_native_component_inventory_coverage(
        observed,
        board,
        mode="off",
        netlist_sha256=netlist_sha256,
        board_path="projects/synthetic-required-fitted-reference/board.kicad_pcb",
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-required-fitted-reference.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=board.probe_sha256,
        required_fitted_reference_map=requirements,
        required_fitted_reference_mode="block",
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-required-fitted-reference",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=observed,
    )
    report = evaluate(
        "synthetic-required-fitted-reference",
        coach,
        DesignLintPolicy(pcb_required_fitted_reference_map=requirements),
        pcb_component_inventory_coverage=coverage,
    )
    return {
        "requirement_sha256": required_fitted_reference_map_sha256(requirements),
        "board_sha256": board_sha256,
        "snapshot_sha256": snapshot_sha256,
        "netlist_sha256": netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    """Return a both-DNP fault and a fitted requirement control."""
    return {
        "pcb_required_fitted_reference_dnp_fault": required_fitted_report(dnp=True),
        "pcb_required_fitted_reference_fitted_control": required_fitted_report(dnp=False),
    }
