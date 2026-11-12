"""Source-bound comparison of saved PCB DRC exclusions and native reports."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    ProjectConfig,
    ProjectKind,
    ValidationSummary,
)
from kicad_tooling.hwrepo.native_drc_findings import parse_native_drc
from kicad_tooling.hwrepo.pcb_drc_exclusion_native import (
    match_pcb_drc_exclusions,
    native_pcb_drc_report_matches,
    source_bound_pcb_drc_exclusion_matches,
)
from kicad_tooling.hwrepo.pcb_drc_exclusion_review import (
    source_bound_pcb_drc_exclusion_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_project_settings import PcbDrcExclusion, pcb_drc_exclusions

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]

RULE_ID = "pcb.drc_exclusion_present"
VERSION = "10.0.8"
FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exclusion-native"
PROJECT_RELATIVE = "projects/board.kicad_pro"


def _report_for(exclusions: tuple[PcbDrcExclusion, ...]) -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for exclusion in exclusions:
        fields = exclusion.marker.split("|")
        if len(fields) < 5:
            continue
        violations.append(
            {
                "excluded": True,
                "type": fields[0],
                "severity": "error",
                "description": "Synthetic exclusion match.",
                "comment": exclusion.comment,
                "items": [
                    {
                        "description": "Synthetic board item.",
                        "pos": {"x": 10.0, "y": 0.5},
                        "uuid": item_id,
                    }
                    for item_id in fields[3:]
                ],
            }
        )
    return {
        "$schema": "https://schemas.kicad.org/drc.v1.json",
        "kicad_version": VERSION,
        "source": "board.kicad_pcb",
        "coordinate_units": "mm",
        "included_severities": ["error", "warning", "exclusion"],
        "violations": violations,
    }


def _project(
    tmp_path: Path,
    *,
    settings_fixture: str,
    excluded_markers: tuple[str, ...] | None = None,
    include_report: bool = True,
) -> tuple[Path, ProjectConfig, dict[str, str], Path, tuple[PcbDrcExclusion, ...]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    settings_text = (FIXTURE_ROOT / settings_fixture).read_text(encoding="utf-8")
    exclusions = pcb_drc_exclusions(settings_text)
    if excluded_markers is not None:
        exclusions_to_report = tuple(
            item
            for item in exclusions
            if not any(item.marker.endswith(marker_suffix) for marker_suffix in excluded_markers)
        )
    else:
        exclusions_to_report = exclusions
    project.write_text(settings_text, encoding="utf-8")
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=PROJECT_RELATIVE,
            kicad_version=VERSION,
        ),
    )
    source_hashes = {PROJECT_RELATIVE: digest(project)}
    native_summary = root / "build/native"
    native_summary.mkdir(parents=True)
    report_path = native_summary / "drc.json"
    if include_report:
        report_path.write_text(json.dumps(_report_for(exclusions_to_report)), encoding="utf-8")
    summary = ValidationSummary(
        timestamp_utc="2026-11-11T00:00:00Z",
        checked_commit="LOCAL_UNBOUND",
        project_id="synthetic-exclusion-project",
        project_kind=ProjectKind.PCB,
        checks={"drc": CheckEvidence(status="PASS", returncode=0)},
        status="PASS",
        artifacts_sha256={"drc.json": digest(report_path)} if include_report else {},
    )
    write_model(native_summary / "summary.json", summary)
    return root, config, source_hashes, native_summary, exclusions


@pytest.mark.design_lint_rule(RULE_ID)
def test_source_bound_lint_localizes_unmatched_saved_marker(tmp_path: Path) -> None:
    root, config, source_hashes, native_summary, exclusions = _project(
        tmp_path,
        settings_fixture="stale.kicad_pro",
        excluded_markers=("00000000-0000-0000-0000-0000000000ff",),
    )

    candidates = source_bound_pcb_drc_exclusion_candidates(
        root,
        config,
        source_hashes,
        native_summary=native_summary,
    )
    by_marker = {item.evidence["serialized_marker"][0]: item for item in candidates}
    stale = next(item for marker, item in by_marker.items() if marker.endswith("0000000000ff"))
    matched = next(item for marker, item in by_marker.items() if marker.endswith("000000000002"))

    assert stale.evidence["native_match_status"] == ("UNMATCHED",)
    assert stale.evidence["native_drc_report_sha256"] == (digest(native_summary / "drc.json"),)
    assert "review whether this saved marker is stale" in stale.message
    assert matched.evidence["native_match_status"] == ("MATCHED",)
    assert "contains a matching excluded violation" in matched.message
    assert len(exclusions) == 2


@pytest.mark.design_lint_rule(RULE_ID)
def test_exact_current_native_matches_remain_distinct_from_missing_report(tmp_path: Path) -> None:
    root, config, source_hashes, native_summary, exclusions = _project(
        tmp_path,
        settings_fixture="fault.kicad_pro",
    )

    statuses = source_bound_pcb_drc_exclusion_matches(
        native_summary,
        exclusions,
        expected_kicad_version=VERSION,
    )
    candidates_without_report = source_bound_pcb_drc_exclusion_candidates(
        root, config, source_hashes
    )

    assert {item.status for item in statuses} == {"MATCHED"}
    assert {item.evidence["native_match_status"] for item in candidates_without_report} == {
        ("UNAVAILABLE",)
    }
    assert all("match is unavailable" in item.message for item in candidates_without_report)


@pytest.mark.design_lint_rule(RULE_ID)
def test_absent_native_drc_report_is_unavailable_not_a_clean_match(tmp_path: Path) -> None:
    _root, _config, _hashes, native_summary, exclusions = _project(
        tmp_path,
        settings_fixture="fault.kicad_pro",
        include_report=False,
    )

    statuses = source_bound_pcb_drc_exclusion_matches(
        native_summary,
        exclusions,
        expected_kicad_version=VERSION,
    )

    assert {item.status for item in statuses} == {"UNAVAILABLE"}


@pytest.mark.design_lint_rule(RULE_ID)
def test_partial_duplicate_marker_identity_is_reported_as_ambiguous() -> None:
    first = "clearance|10000000|500000|00000000-0000-0000-0000-000000000001|00000000-0000-0000-0000-000000000002"
    second = "clearance|11000000|500000|00000000-0000-0000-0000-000000000001|00000000-0000-0000-0000-000000000002"
    exclusions = (
        PcbDrcExclusion(marker=first, comment="same"),
        PcbDrcExclusion(marker=second, comment="same"),
    )
    report = parse_native_drc(_report_for(exclusions[:1]))

    matches = match_pcb_drc_exclusions(
        exclusions,
        report,
        expected_kicad_version=VERSION,
        report_sha256="a" * 64,
    )

    assert tuple(item.status for item in matches) == ("AMBIGUOUS", "AMBIGUOUS")


@pytest.mark.design_lint_rule(RULE_ID)
def test_excluded_native_record_without_item_uuids_is_unavailable() -> None:
    exclusion = PcbDrcExclusion(
        marker=(
            "clearance|10000000|500000|00000000-0000-0000-0000-000000000001|"
            "00000000-0000-0000-0000-000000000002"
        ),
        comment="same",
    )
    document = _report_for(())
    document["violations"] = [
        {
            "excluded": True,
            "type": "clearance",
            "severity": "error",
            "description": "Native exclusion without comparable item identities.",
            "comment": "same",
            "items": [{"description": "Item without UUID.", "pos": {"x": 10, "y": 0.5}}],
        }
    ]

    matches = match_pcb_drc_exclusions(
        (exclusion,),
        parse_native_drc(document),
        expected_kicad_version=VERSION,
        report_sha256="a" * 64,
    )

    assert matches[0].status == "UNAVAILABLE"


@pytest.mark.design_lint_rule(RULE_ID)
def test_native_report_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    _root, _config, _hashes, native_summary, exclusions = _project(
        tmp_path,
        settings_fixture="fault.kicad_pro",
    )
    report_path = native_summary / "drc.json"
    report_path.write_text(report_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    assert not native_pcb_drc_report_matches(native_summary, "0" * 64)
    with pytest.raises(ValueError, match="differs from its validation-summary artifact hash"):
        source_bound_pcb_drc_exclusion_matches(
            native_summary,
            exclusions,
            expected_kicad_version=VERSION,
        )
