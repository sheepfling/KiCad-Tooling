"""Source-bound review of persisted per-violation PCB DRC exclusions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_exclusion_review import (
    source_bound_pcb_drc_exclusion_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_project_settings import PcbDrcExclusion, pcb_drc_exclusions
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exclusions"
RULE_ID = "pcb.drc_exclusion_present"
PROJECT_RELATIVE = "projects/controller.kicad_pro"


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
    *,
    kicad_version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=kind,
            project=PROJECT_RELATIVE,
            kicad_version=kicad_version,
        ),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_pcb_drc_exclusion_candidates(root, config, source_hashes)


def test_saved_exclusions_report_rule_key_comment_and_source_binding(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    candidates = _scan(root, config, source_hashes)

    assert tuple(item.evidence["drc_rule_key"][0] for item in candidates) == (
        "clearance",
        "unconnected_items",
    )
    assert all(item.rule_id == RULE_ID for item in candidates)
    by_rule = {item.evidence["drc_rule_key"][0]: item for item in candidates}
    unconnected = by_rule["unconnected_items"]
    marker = unconnected.evidence["serialized_marker"][0]
    marker_sha256 = hashlib.sha256(marker.encode("utf-8")).hexdigest()
    assert (
        unconnected.subject
        == f"{PROJECT_RELATIVE}#board/design_settings/drc_exclusions/{marker_sha256}"
    )
    assert "no explanatory comment" in unconnected.message
    assert unconnected.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.5",),
        "drc_rule_key": ("unconnected_items",),
        "exclusion_marker_sha256": (marker_sha256,),
        "serialized_marker": (marker,),
        "exclusion_comment": ("",),
    }
    assert "with a saved comment" in by_rule["clearance"].message
    assert by_rule["clearance"].evidence["exclusion_comment"] == (
        "Approved synthetic mounting-point clearance exception.",
    )


def test_empty_or_absent_exclusion_lists_are_valid_controls(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control.kicad_pro")
    assert _scan(root, config, source_hashes) == ()
    assert pcb_drc_exclusions('{"board":{"design_settings":{}}}') == ()
    assert pcb_drc_exclusions('{"board":{"design_settings":{"drc_exclusions":[]}}}') == ()


def test_legacy_marker_string_is_supported_without_a_comment() -> None:
    marker = "unconnected_items|500000|600000|55555555-5555-5555-5555-555555555555"
    document = json.dumps({"board": {"design_settings": {"drc_exclusions": [marker]}}})

    assert pcb_drc_exclusions(document) == (PcbDrcExclusion(marker=marker, comment=""),)


def test_exclusion_order_does_not_change_candidate_identity(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    first = _scan(root, config, source_hashes)
    document = project.read_text(encoding="utf-8")
    records = pcb_drc_exclusions(document)
    reversed_document = json.dumps(
        {
            "board": {
                "design_settings": {
                    "drc_exclusions": [
                        [record.marker, record.comment] for record in reversed(records)
                    ]
                }
            }
        }
    )
    project.write_text(reversed_document, encoding="utf-8")
    source_hashes[PROJECT_RELATIVE] = digest(project)

    second = _scan(root, config, source_hashes)

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.evidence["drc_rule_key"] for item in first) == tuple(
        item.evidence["drc_rule_key"] for item in second
    )


def test_invalid_or_duplicate_exclusion_records_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"drc_exclusions":[[],["clearance|1|2"]]}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="could not read supported PCB DRC exclusions"):
        _scan(root, config, source_hashes)

    project.write_text(
        '{"board":{"design_settings":{"drc_exclusions":['
        '["clearance|1|2","first"],["clearance|1|2","second"]]}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="must be unique"):
        _scan(root, config, source_hashes)


def test_unknown_settings_schema_fails_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"meta":{"version":3},"drc_exclusions":[]}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="schema version is not supported"):
        _scan(root, config, source_hashes)


def test_missing_hash_stale_bytes_and_duplicate_json_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    source_hashes[PROJECT_RELATIVE] = digest(project)
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)

    project.write_text(
        '{"board":{"design_settings":{"drc_exclusions":[],"drc_exclusions":[]}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        _scan(root, config, source_hashes)


@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5", "10.0.7"))
def test_supported_kicad_10_0_patch_versions_are_recorded(
    tmp_path: Path, kicad_version: str
) -> None:
    root, _, config, source_hashes = _project(tmp_path, kicad_version=kicad_version)
    candidates = _scan(root, config, source_hashes)
    assert len(candidates) == 2
    assert all(item.evidence["kicad_version"] == (kicad_version,) for item in candidates)


def test_non_pcb_and_other_minor_versions_are_out_of_scope(tmp_path: Path) -> None:
    root, _, _config, source_hashes = _project(tmp_path)
    schematic = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.SCHEMATIC))
    assert _scan(root, schematic, source_hashes) == ()
    for version in ("9.0.0", "10.1.0", "10.99.0", "11.0.0"):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT_RELATIVE, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()


def test_linked_project_settings_are_rejected(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    external = tmp_path / "external.kicad_pro"
    external.write_bytes(project.read_bytes())
    project.unlink()
    try:
        project.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="Linked repository path"):
        _scan(root, config, {PROJECT_RELATIVE: digest(external)})


def test_review_block_exact_ignore_and_off_policy_are_supported(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    candidate = _scan(root, config, source_hashes)[0]
    observed = coach(NetlistContract(components={}, nets={}))
    reviewed = evaluate(
        "synthetic-drc-exclusions",
        observed,
        DesignLintPolicy(),
        pcb_native_drc_candidates=(candidate,),
    )
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-drc-exclusions",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of DRC exceptions",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"

    ignored = evaluate(
        "synthetic-drc-exclusions",
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed exception",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )

    off = evaluate(
        "synthetic-drc-exclusions",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic policy disables this review prompt",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.mode == "off"
    assert off_finding.disposition == "RULE_OFF"
