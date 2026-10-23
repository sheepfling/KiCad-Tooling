"""Source-bound courtyard-edge DRC reports for hash-seed tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ContractCoachReport,
    NetlistContract,
    ProjectConfig,
    ProjectKind,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_drc_source_evidence import source_inventory_sha256
from kicad_tooling.hwrepo.pcb_mechanical_edge_clearance import (
    mechanical_edge_rule_coverage_candidates,
)
from kicad_tooling.hwrepo.pcb_mechanical_edge_models import (
    PcbMechanicalEdgeClearanceMap,
    PcbMechanicalEdgeClearanceRequirement,
)
from kicad_tooling.validate import hashes

_PROJECT_ID = "synthetic-mechanical-edge-clearance"
_PROJECT_RELATIVE = "projects/synthetic-mechanical-edge-clearance/board.kicad_pro"
_BOARD_RELATIVE = "projects/synthetic-mechanical-edge-clearance/board.kicad_pcb"
_RULES_RELATIVE = "projects/synthetic-mechanical-edge-clearance/board.kicad_dru"
_KICAD_VERSION = "10.0.5"
_EXACT_RULE = """(version 1)
(rule "front-mechanical-board-edge-clearance"
  (layer "F.Courtyard")
  (constraint physical_clearance (min 1.5mm))
  (condition "B.Layer == 'Edge.Cuts'"))
"""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def mechanical_edge_report(*, fault: bool) -> dict[str, object]:
    """Build a source-hashed rule-coverage fault or exact-coverage control."""
    with tempfile.TemporaryDirectory(prefix="mechanical-edge-hashseed-") as temporary:
        root = Path(temporary)
        project_directory = root / "projects/synthetic-mechanical-edge-clearance"
        native_directory = root / "build/native"
        project_directory.mkdir(parents=True)
        native_directory.mkdir(parents=True)

        project_bytes = b'{"fixture":"synthetic-mechanical-edge-clearance"}\n'
        board_bytes = b"(kicad_pcb (version 20241229) (generator pcbnew))\n"
        rule_source = _EXACT_RULE.replace("1.5mm", "1.0mm", 1) if fault else _EXACT_RULE
        (root / _PROJECT_RELATIVE).write_bytes(project_bytes)
        (root / _BOARD_RELATIVE).write_bytes(board_bytes)
        (root / _RULES_RELATIVE).write_text(rule_source, encoding="utf-8")

        drc_path = native_directory / "drc.json"
        drc_relative = "build/native/drc.json"
        drc_bytes = json.dumps(
            {
                "fixture": "synthetic-only; KiCad was not invoked",
                "kicad_version": _KICAD_VERSION,
                "source": "board.kicad_pcb",
                "ignored_checks": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        drc_path.write_bytes(drc_bytes)

        command = CommandEvidence(
            argv=(
                "kicad-cli",
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--output",
                drc_relative,
                _BOARD_RELATIVE,
            ),
            started_utc="2026-10-23T00:00:00Z",
            returncode=0,
        )
        command_path = native_directory / "drc.command.json"
        command_bytes = command.model_dump_json().encode("utf-8")
        command_path.write_bytes(command_bytes)
        summary = ValidationSummary(
            timestamp_utc="2026-10-23T00:00:00Z",
            checked_commit="synthetic-source-commit",
            project_id=_PROJECT_ID,
            project_kind=ProjectKind.PCB,
            checks={"drc": CheckEvidence(status="PASS", returncode=0, findings=0)},
            status="PASS",
            artifacts_sha256={
                "drc.json": _sha256(drc_bytes),
                "drc.command.json": _sha256(command_bytes),
            },
        )
        summary_path = native_directory / "summary.json"
        summary_path.write_text(summary.model_dump_json(), encoding="utf-8")

        config = ProjectConfig.model_construct(
            kind=ProjectKind.PCB,
            project=_PROJECT_RELATIVE,
            source_roots=("projects/synthetic-mechanical-edge-clearance",),
            kicad_version=_KICAD_VERSION,
        )
        source_hashes = hashes(root, config.source_roots)
        requirement_map = PcbMechanicalEdgeClearanceMap(
            basis="Synthetic reviewed connector-body clearance requirement",
            requirements=(
                PcbMechanicalEdgeClearanceRequirement(
                    id="front-edge",
                    basis="Synthetic mechanical drawing",
                    courtyard_layer="F.Courtyard",
                    rule_name="front-mechanical-board-edge-clearance",
                    minimum_clearance_nm=1_500_000,
                ),
            ),
        )
        observed = NetlistContract(components={}, nets={})
        netlist_sha256 = _sha256(model_json_bytes(observed))
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=_PROJECT_ID,
            source_hashes=source_hashes,
            netlist_sha256=netlist_sha256,
            observed=observed,
        )
        policy = DesignLintPolicy(pcb_mechanical_edge_clearance_map=requirement_map)
        candidates = mechanical_edge_rule_coverage_candidates(
            root,
            config,
            policy,
            source_hashes,
            native_directory,
        )
        report = evaluate(
            _PROJECT_ID,
            coach,
            policy,
            pcb_dru_rule_candidates=candidates,
        )

        return {
            "requirement_sha256": _sha256(requirement_map.model_dump_json().encode("utf-8")),
            "source_inventory_sha256": source_inventory_sha256(source_hashes),
            "project_sha256": source_hashes[_PROJECT_RELATIVE],
            "board_sha256": source_hashes[_BOARD_RELATIVE],
            "rules_sha256": source_hashes[_RULES_RELATIVE],
            "native_summary_sha256": _sha256(summary_path.read_bytes()),
            "native_drc_sha256": _sha256(drc_path.read_bytes()),
            "netlist_sha256": netlist_sha256,
            "report": report.model_dump(mode="json"),
        }


def report_cases() -> dict[str, object]:
    """Return a weak-rule fault and exact-rule coverage control."""
    return {
        "pcb_mechanical_edge_coverage_fault": mechanical_edge_report(fault=True),
        "pcb_mechanical_edge_coverage_control": mechanical_edge_report(fault=False),
    }
