"""Source-bound PCB UUID fault/control reports for hash-seed probes."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate_request
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.pcb_object_uuid_integrity import (
    duplicate_pcb_object_uuid_candidates,
)
from tests.design_lint_fixtures import coach
from tests.json_types import JsonObject

_FIXTURES = Path(__file__).parents[1] / "fixtures/design_lint/pcb-duplicate-object-uuid"
_RULE_ID = "pcb.duplicate_object_uuid"
_BOARD = "projects/synthetic/controller.kicad_pcb"


def _report(*, fault: bool) -> JsonObject:
    project_id = "synthetic-pcb-uuid-integrity"
    with TemporaryDirectory(prefix="pcb-uuid-hashseed-") as temporary:
        root = Path(temporary)
        board_path = root / _BOARD
        board_path.parent.mkdir(parents=True)
        case = "fault" if fault else "control"
        shutil.copyfile(_FIXTURES / f"{case}.kicad_pcb", board_path)
        source_hashes = {_BOARD: digest(board_path)}
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project=Path("projects/synthetic/controller.kicad_pro"),
                kicad_version="10.0.5",
            ),
        )
        candidates = duplicate_pcb_object_uuid_candidates(root, config, source_hashes)

    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = hashlib.sha256(model_json_bytes(observed)).hexdigest()
    contract_coach = coach(
        observed,
        netlist_sha256,
        project_id=project_id,
    ).model_copy(update={"source_hashes": source_hashes})
    report = evaluate_request(
        DesignLintEvaluationRequest(
            project_id=project_id,
            coach=contract_coach,
            policy=DesignLintPolicy(),
            component_map_coverage=ComponentMapCoverageInputs(),
            pcb_source_candidates=candidates,
        )
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Build stable source-bound UUID fault and unique-identity control reports."""
    return {
        "pcb_uuid_duplicate_fault": _report(fault=True),
        "pcb_uuid_duplicate_control": _report(fault=False),
    }
