"""Hierarchical schematic UUID reports for hash-seed determinism checks."""

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
from kicad_tooling.hwrepo.schematic_source_integrity import (
    duplicate_schematic_object_uuid_candidates,
)
from tests.design_lint_fixtures import coach
from tests.json_types import JsonObject

_FIXTURES = (
    Path(__file__).parents[1] / "fixtures/design_lint/schematic-duplicate-object-uuid-across-files"
)
_SOURCES = (
    "projects/synthetic/kicad/controller.kicad_sch",
    "projects/synthetic/kicad/channel-a.kicad_sch",
    "projects/synthetic/kicad/channel-b.kicad_sch",
)
_RULE_ID = "schematic.duplicate_object_uuid"


def _report(*, fault: bool) -> JsonObject:
    project_id = "synthetic-schematic-uuid-cross-file"
    with TemporaryDirectory(prefix="schematic-uuid-hashseed-") as temporary:
        root = Path(temporary)
        project_directory = root / "projects/synthetic/kicad"
        project_directory.mkdir(parents=True)
        shutil.copyfile(_FIXTURES / "root.kicad_sch", root / _SOURCES[0])
        shutil.copyfile(_FIXTURES / "channel-a.kicad_sch", root / _SOURCES[1])
        channel_b = "channel-b-fault.kicad_sch" if fault else "channel-b-control.kicad_sch"
        shutil.copyfile(_FIXTURES / channel_b, root / _SOURCES[2])
        source_hashes = {source: digest(root / source) for source in _SOURCES}
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project=Path("projects/synthetic/kicad/controller.kicad_pro"),
                kicad_version="10.0.5",
            ),
        )
        candidates = duplicate_schematic_object_uuid_candidates(root, config, source_hashes)

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
            schematic_source_candidates=candidates,
        )
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Build source-bound cross-file UUID fault and distinct-ID control reports."""
    return {
        "schematic_uuid_cross_file_fault": _report(fault=True),
        "schematic_uuid_cross_file_control": _report(fault=False),
    }
