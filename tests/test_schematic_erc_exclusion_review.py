"""Source-bound review of persisted schematic ERC exclusions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate_request
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_exclusion_review import (
    SchematicErcExclusionCandidate,
    source_bound_schematic_erc_exclusion_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    SchematicErcExclusion,
    schematic_erc_exclusion_marker_sha256,
    schematic_erc_exclusions,
)
from tests.design_lint_fixtures import coach
from tests.schematic_erc_exclusion_support import PROJECT_RELATIVE, erc_exclusion_project

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.design_lint_rule("schematic.erc_exclusion_present"),
]

RULE_ID = "schematic.erc_exclusion_present"


def _scan(root: Path, config: ProjectConfig, source_hashes: Mapping[str, str]):
    return source_bound_schematic_erc_exclusion_candidates(root, config, source_hashes)


def test_saved_exclusions_report_type_comment_and_source_binding(tmp_path: Path) -> None:
    root, project, config, source_hashes = erc_exclusion_project(tmp_path)

    candidates = _scan(root, config, source_hashes)

    assert tuple(item.evidence["erc_error_type"][0] for item in candidates) == (
        "label_not_connected",
        "pin_not_connected",
    )
    assert all(item.rule_id == RULE_ID for item in candidates)
    pin = next(
        item for item in candidates if item.evidence["erc_error_type"] == ("pin_not_connected",)
    )
    marker_hash = pin.evidence["exclusion_marker_sha256"][0]
    assert len(marker_hash) == 64
    assert pin.subject == f"{PROJECT_RELATIVE}#erc/erc_exclusions/{marker_hash}"
    assert pin.message.endswith(
        "with a saved comment; confirm that the individual exception is still intentional."
    )
    assert pin.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.5",),
        "erc_error_type": ("pin_not_connected",),
        "exclusion_marker_sha256": (marker_hash,),
        "exclusion_comment": ("Synthetic intentionally-unused test point.",),
    }
    without_comment = next(
        item for item in candidates if item.evidence["erc_error_type"] == ("label_not_connected",)
    )
    assert "no explanatory comment" in without_comment.message
    assert without_comment.evidence["exclusion_comment"] == ("",)


def test_candidate_fields_cannot_diverge_from_typed_source_evidence(tmp_path: Path) -> None:
    root, project, config, source_hashes = erc_exclusion_project(tmp_path)
    candidate = _scan(root, config, source_hashes)[0]

    assert isinstance(candidate, SchematicErcExclusionCandidate)
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.source_evidence.kicad_version == "10.0.5"
    with pytest.raises(ValueError, match="must match their source projection"):
        replace(candidate, subject=f"{candidate.subject}/stale")


def test_empty_or_absent_exclusion_lists_are_valid_controls(tmp_path: Path) -> None:
    root, _, config, source_hashes = erc_exclusion_project(tmp_path, "control.kicad_pro")
    assert _scan(root, config, source_hashes) == ()
    assert schematic_erc_exclusions("{}") == ()
    assert schematic_erc_exclusions('{"erc":{"meta":{"version":1}}}') == ()


def test_legacy_marker_strings_and_comment_pairs_are_supported() -> None:
    marker = "pin_not_connected|12000000|8000000|11111111-1111-4111-8111-111111111111"
    document = json.dumps(
        {"erc": {"meta": {"version": 0}, "erc_exclusions": [marker, [marker + "|2", "reviewed"]]}}
    )

    exclusions = schematic_erc_exclusions(document)

    assert exclusions == (
        SchematicErcExclusion(marker=marker, error_type="pin_not_connected", comment=""),
        SchematicErcExclusion(
            marker=marker + "|2", error_type="pin_not_connected", comment="reviewed"
        ),
    )
    assert (
        schematic_erc_exclusion_marker_sha256(exclusions[0])
        == hashlib.sha256(marker.encode("utf-8")).hexdigest()
    )


def test_marker_order_does_not_change_candidate_identity(tmp_path: Path) -> None:
    root, project, config, source_hashes = erc_exclusion_project(tmp_path)
    first = _scan(root, config, source_hashes)
    document = json.loads(project.read_text(encoding="utf-8"))
    document["erc"]["erc_exclusions"].reverse()
    project.write_text(json.dumps(document), encoding="utf-8")
    source_hashes[PROJECT_RELATIVE] = digest(project)

    second = _scan(root, config, source_hashes)

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.evidence["erc_error_type"] for item in first) == tuple(
        item.evidence["erc_error_type"] for item in second
    )


@pytest.mark.parametrize(
    "document",
    (
        '{"erc":{"meta":{"version":2},"erc_exclusions":[]}}',
        '{"erc":{"meta":{"version":1},"erc_exclusions":[{"marker":{},"comment":4}]}}',
        '{"erc":{"meta":{"version":1},"erc_exclusions":[{"marker":{"error_type":"x","position":{"x_nm":"1","y_nm":"2"},"items":[]}}]}}',
        '{"erc":{"meta":{"version":0},"erc_exclusions":[[]]}}',
        '{"erc":{"meta":{"version":0},"erc_exclusions":["duplicate|1","duplicate|1"]}}',
        '{"erc":{"meta":{"version":1},"erc_exclusions":[],"erc_exclusions":[]}}',
    ),
)
def test_unknown_or_malformed_exclusion_data_fails_closed(document: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        schematic_erc_exclusions(document)


def test_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = erc_exclusion_project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_only_supported_project_kinds_and_exact_kicad_minor_are_scanned(tmp_path: Path) -> None:
    root, _, config, source_hashes = erc_exclusion_project(tmp_path)
    pcb_only = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, pcb_only, source_hashes) == ()
    for version in ("9.0.0", "10.1.0", "11.0.0"):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT_RELATIVE, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()
    assert config.kind is ProjectKind.PCB


def test_review_block_ignore_and_off_policy_are_supported(tmp_path: Path) -> None:
    root, _, config, source_hashes = erc_exclusion_project(tmp_path)
    candidate = _scan(root, config, source_hashes)[0]
    observed = coach(NetlistContract(components={}, nets={}))

    def inspect(policy: DesignLintPolicy):
        return evaluate_request(
            DesignLintEvaluationRequest(
                project_id="synthetic-erc-exclusions",
                coach=observed,
                policy=policy,
                component_map_coverage=ComponentMapCoverageInputs(),
                schematic_source_candidates=(candidate,),
            )
        )

    finding = next(item for item in inspect(DesignLintPolicy()).findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
    blocked = inspect(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of ERC exclusions",
                ),
            )
        )
    )
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    ignored = inspect(
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed exception",
                ),
            )
        )
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
    off = inspect(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic policy disables this prompt",
                ),
            )
        )
    )
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
