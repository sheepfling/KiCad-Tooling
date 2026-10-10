"""Source-bound synthetic PCB DRC rule-coverage reports for hash-seed tests."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    PcbDifferentialPairRuleCoverageReport,
)
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from kicad_tooling.hwrepo.pcb_drc_source_evidence import source_inventory_sha256
from tests.test_pcb_drc_coverage import FIXTURES, pair_map, rules_text


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_model(value: BaseModel) -> str:
    return _digest_bytes(value.model_dump_json().encode("utf-8"))


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def differential_pair_rule_report(*, fault: bool) -> dict[str, object]:
    """Serialize an exact native-rule coverage control and one mismatched bound."""
    requirement_map = pair_map()
    native_rules = rules_text()
    if fault:
        native_rules = native_rules.replace("(max 0.5mm)", "(max 0.45mm)", 1)

    project_path = "projects/synthetic/differential-pair.kicad_pro"
    rules_path = "projects/synthetic/differential-pair.kicad_dru"
    board_path = "projects/synthetic/differential-pair.kicad_pcb"
    project_bytes = b'{"fixture":"synthetic","id":"differential-pair"}\n'
    rules_bytes = native_rules.encode("utf-8")
    board_bytes = (FIXTURES / "control.kicad_pcb").read_bytes()
    source_hashes = {
        project_path: _digest_bytes(project_bytes),
        rules_path: _digest_bytes(rules_bytes),
        board_path: _digest_bytes(board_bytes),
    }

    native_drc_path = "build/synthetic/differential-pair/drc.json"
    native_summary_path = "build/synthetic/differential-pair/summary.json"
    native_drc_bytes = _json_bytes(
        {
            "fixture": "synthetic-only",
            "kicad_version": "10.0.5",
            "rules_sha256": source_hashes[rules_path],
            "source": board_path,
            "ignored_checks": [],
        }
    )
    native_drc_sha256 = _digest_bytes(native_drc_bytes)
    native_summary_bytes = _json_bytes(
        {
            "fixture": "synthetic-only",
            "kicad_version": "10.0.5",
            "project_sha256": source_hashes[project_path],
            "drc_path": native_drc_path,
            "drc_sha256": native_drc_sha256,
        }
    )

    (entry,) = compare_native_rules(requirement_map, native_rules, frozenset())
    coverage = PcbDifferentialPairRuleCoverageReport(
        status="COMPLETE" if entry.status == "COMPLETE" else "INCOMPLETE",
        mode="review",
        map_sha256=_digest_model(requirement_map),
        source_inventory_sha256=source_inventory_sha256(source_hashes),
        project_path=project_path,
        project_sha256=source_hashes[project_path],
        rules_path=rules_path,
        rules_sha256=source_hashes[rules_path],
        board_path=board_path,
        board_sha256=source_hashes[board_path],
        native_summary_path=native_summary_path,
        native_summary_sha256=_digest_bytes(native_summary_bytes),
        native_drc_path=native_drc_path,
        native_drc_sha256=native_drc_sha256,
        kicad_version="10.0.5",
        image="synthetic fixture metadata; KiCad was not run",
        entries=(entry,),
    )

    observed = NetlistContract(
        components={},
        nets={"USB_D_P": ("J1.1",), "USB_D_N": ("J1.2",)},
    )
    netlist_sha256 = _digest_model(observed)
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-differential-pair",
        source_hashes=source_hashes,
        netlist_sha256=netlist_sha256,
        observed=observed,
    )
    report = evaluate(
        "synthetic-differential-pair",
        coach,
        DesignLintPolicy(pcb_differential_pair_rule_map=requirement_map),
        pcb_differential_pair_coverage=coverage,
    )
    return {
        "requirement_sha256": coverage.map_sha256,
        "source_inventory_sha256": coverage.source_inventory_sha256,
        "project_sha256": coverage.project_sha256,
        "rules_sha256": coverage.rules_sha256,
        "board_sha256": coverage.board_sha256,
        "native_summary_sha256": coverage.native_summary_sha256,
        "native_drc_sha256": coverage.native_drc_sha256,
        "netlist_sha256": netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    return {
        "pcb_differential_pair_rule_fault": differential_pair_rule_report(fault=True),
        "pcb_differential_pair_rule_control": differential_pair_rule_report(fault=False),
    }
