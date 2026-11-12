"""Source-bound review of non-string schematic ERC severity values."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_nonstring_severity_value_review import (
    SchematicErcNonStringSeverityValueCandidate,
    source_bound_schematic_erc_nonstring_severity_value_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
    configured_schematic_erc_rule_severity_settings,
)

RULE_ID = "schematic.erc_nonstring_severity_value"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-nonstring-severity"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault-boolean.kicad_pro",
    *,
    version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_schematic_erc_nonstring_severity_value_candidates(
        root, config, source_hashes
    )


@pytest.mark.parametrize(
    ("fixture", "type_name", "canonical_value"),
    (
        ("fault-boolean.kicad_pro", "boolean", "true"),
        ("fault-number.kicad_pro", "number", "7"),
        ("fault-null.kicad_pro", "null", "null"),
        ("fault-array.kicad_pro", "array", "[]"),
        ("fault-object.kicad_pro", "object", '{"mode":"warning"}'),
    ),
)
def test_nonstring_values_create_source_bound_candidates(
    tmp_path: Path,
    fixture: str,
    type_name: str,
    canonical_value: str,
) -> None:
    root, project, config, source_hashes = _project(tmp_path, fixture)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcNonStringSeverityValueCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected"
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "erc_rule_key": ("pin_not_connected",),
        "configured_value_type": (type_name,),
        "configured_value_json": (canonical_value,),
    }


def test_unknown_key_with_nonstring_value_is_also_reviewed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path, "fault-unknown-key.kicad_pro")

    (candidate,) = _scan(root, config, source_hashes)

    assert candidate.evidence["source_sha256"] == (digest(project),)
    assert candidate.evidence["erc_rule_key"] == ("future_rule",)
    assert candidate.evidence["configured_value_type"] == ("object",)


@pytest.mark.parametrize("severity", ("error", "warning", "ignore", "warnnig"))
def test_string_values_are_outside_this_rule(tmp_path: Path, severity: str) -> None:
    root, project, config, _ = _project(tmp_path, "control.kicad_pro")
    project.write_text(
        json.dumps(
            {
                "erc": {
                    "meta": {"version": 0},
                    "rule_severities": {"pin_not_connected": severity},
                }
            }
        ),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


def test_settings_parser_preserves_json_types_and_existing_strict_string_api() -> None:
    document = (
        '{"erc":{"meta":{"version":0},"rule_severities":'
        '{"future_rule":{"mode":"warning"},"pin_not_connected":true}}}'
    )

    settings = configured_schematic_erc_rule_severity_settings(document)
    assert tuple((item.rule_key, item.configured_value_json) for item in settings) == (
        ("future_rule", '{"mode":"warning"}'),
        ("pin_not_connected", "true"),
    )
    with pytest.raises(TypeError, match="must be a string"):
        configured_schematic_erc_rule_severities(document)
    assert configured_schematic_erc_rule_severities(document, skip_nonstring_values=True) == ()


def test_parser_can_skip_nonstrings_without_losing_valid_strings() -> None:
    document = (
        '{"erc":{"meta":{"version":0},"rule_severities":'
        '{"pin_not_connected":true,"wire_dangling":"warning"}}}'
    )

    assert configured_schematic_erc_rule_severities(document, skip_nonstring_values=True) == (
        SchematicErcRuleSeverity("wire_dangling", "warning"),
    )


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.9", "11.0.0"))
def test_unaudited_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, version=version)

    assert _scan(root, config, source_hashes) == ()


def test_non_schematic_capable_project_kind_is_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=ProjectKind.PCB_ONLY)

    assert _scan(root, config, source_hashes) == ()


def test_source_hash_is_required_current_and_candidate_fields_are_bound(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    (candidate,) = _scan(root, config, source_hashes)

    project.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")


def test_candidate_order_is_stable_when_setting_order_changes(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    first = {"wire_dangling": [], "pin_not_connected": True}
    results = []
    for settings in (first, dict(reversed(tuple(first.items())))):
        project.write_text(
            json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": settings}}),
            encoding="utf-8",
        )
        candidates = _scan(root, config, {PROJECT_RELATIVE: digest(project)})
        results.append(
            tuple((item.subject, item.evidence["configured_value_json"]) for item in candidates)
        )

    assert results[0] == results[1]
    assert tuple(item[0].rsplit("/", 1)[-1] for item in results[0]) == (
        "pin_not_connected",
        "wire_dangling",
    )
