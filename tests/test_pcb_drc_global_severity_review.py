"""Synthetic source-bound tests for globally ignored core PCB DRC checks."""

from __future__ import annotations

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
from kicad_tooling.hwrepo.pcb_drc_global_severity_review import (
    ignored_core_native_drc_check_candidates,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-core-drc-disabled"
RULE_ID = "pcb.core_drc_check_ignored"
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


def _scan(
    root: Path,
    config: ProjectConfig,
    source_hashes: dict[str, str],
):
    return ignored_core_native_drc_check_candidates(root, config, source_hashes)


@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_ignored_unconnected_check_creates_a_source_bound_review_candidate(
    tmp_path: Path, kicad_version: str
) -> None:
    root, project, config, source_hashes = _project(
        tmp_path,
        kicad_version=kicad_version,
    )

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == RULE_ID
    assert (
        candidate.subject
        == f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/unconnected_items"
    )
    assert "confirm that suppressing this check is intentional" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (kicad_version,),
        "check_id": ("unconnected_items",),
        "configured_severity": ("ignore",),
    }


def test_active_core_checks_and_documented_default_ignores_are_valid_controls(
    tmp_path: Path,
) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control.kicad_pro")

    assert _scan(root, config, source_hashes) == ()


def test_multiple_ignored_core_checks_are_reported_in_stable_key_order(
    tmp_path: Path,
) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"tracks_crossing":"ignore","unconnected_items":"ignore",'
        '"missing_courtyard":"ignore"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    candidates = _scan(root, config, source_hashes)

    assert tuple(item.evidence["check_id"][0] for item in candidates) == (
        "tracks_crossing",
        "unconnected_items",
    )


def test_json_key_order_does_not_change_detected_check_ids() -> None:
    first = (
        '{"board":{"design_settings":{"rule_severities":'
        '{"tracks_crossing":"ignore","unconnected_items":"ignore"}}}}'
    )
    second = (
        '{"board":{"design_settings":{"rule_severities":'
        '{"unconnected_items":"ignore","tracks_crossing":"ignore"}}}}'
    )

    from kicad_tooling.hwrepo.pcb_drc_project_settings import ignored_core_drc_check_ids

    assert ignored_core_drc_check_ids(first) == ignored_core_drc_check_ids(second)


def test_warning_severity_is_visible_and_does_not_trigger_ignore_review(
    tmp_path: Path,
) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":{"unconnected_items":"warning"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    assert _scan(root, config, source_hashes) == ()


def test_missing_source_hash_and_stale_bytes_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    source_hashes[PROJECT_RELATIVE] = digest(project)
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_duplicate_json_keys_and_invalid_severity_types_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"unconnected_items":"ignore","unconnected_items":"error"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        _scan(root, config, source_hashes)

    project.write_text(
        '{"board":{"design_settings":{"rule_severities":{"unconnected_items":1}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    with pytest.raises(ValueError, match="rule_severities"):
        _scan(root, config, source_hashes)


def test_missing_file_non_pcb_and_unsupported_major_are_out_of_scope(
    tmp_path: Path,
) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.unlink()
    assert _scan(root, config, {}) == ()
    project.write_bytes((FIXTURES / "fault.kicad_pro").read_bytes())
    assert (
        _scan(
            root,
            cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.SCHEMATIC)),
            {},
        )
        == ()
    )
    unsupported = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=PROJECT_RELATIVE,
            kicad_version="11.0.0",
        ),
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


def test_findings_support_review_block_exact_ignore_and_off_policy(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    candidate = _scan(root, config, source_hashes)[0]
    observed = coach(NetlistContract(components={}, nets={}))

    reviewed = evaluate(
        "synthetic-global-drc",
        observed,
        DesignLintPolicy(),
        pcb_native_drc_candidates=(candidate,),
    )
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-global-drc",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of suppressed core DRC checks",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    blocked_finding = next(item for item in blocked.findings if item.rule_id == RULE_ID)
    assert blocked_finding.mode == "block"
    assert blocked_finding.disposition == "OPEN"

    ignored = evaluate(
        "synthetic-global-drc",
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project reviewed this intentional DRC suppression",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"

    off = evaluate(
        "synthetic-global-drc",
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this review prompt",
                ),
            )
        ),
        pcb_native_drc_candidates=(candidate,),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.mode == "off"
    assert off_finding.disposition == "RULE_OFF"
