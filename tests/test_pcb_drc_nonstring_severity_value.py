"""Source-bound review of non-string PCB DRC severity values."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_nonstring_severity_value_review import (
    PcbDrcNonStringSeverityValueCandidate,
    source_bound_pcb_drc_nonstring_severity_value_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_project_settings import (
    PcbDrcCheckSeverity,
    configured_pcb_drc_rule_severity_settings,
    configured_warning_default_drc_check_severities,
)
from kicad_tooling.hwrepo.pcb_drc_severity_key_catalog import (
    KICAD_10_0_8_DRC_SEVERITY_KEYS,
    KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS,
    KICAD_10_0_8_DRC_SEVERITY_STRING_KEYS,
    PCB_DRC_STRING_RULE_SEVERITY_KEYS_BY_KICAD_VERSION,
)

RULE_ID = "pcb.drc_nonstring_severity_value"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-nonstring-severity-value"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
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
    return source_bound_pcb_drc_nonstring_severity_value_candidates(root, config, source_hashes)


@pytest.mark.parametrize(
    ("value", "type_name"),
    (
        (True, "boolean"),
        (7, "number"),
        (None, "null"),
        (["warning"], "array"),
        ({"mode": "warning"}, "object"),
    ),
)
def test_nonstring_known_values_create_source_bound_candidates(
    tmp_path: Path,
    value: object,
    type_name: str,
) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        json.dumps({"board": {"design_settings": {"rule_severities": {"track_dangling": value}}}}),
        encoding="utf-8",
    )
    source_hashes = {PROJECT_RELATIVE: digest(project)}

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, PcbDrcNonStringSeverityValueCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (
        f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/track_dangling"
    )
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "drc_severity_key": ("track_dangling",),
        "configured_value_type": (type_name,),
        "configured_value_json": (json.dumps(value, sort_keys=True, separators=(",", ":")),),
    }


def test_canonical_strings_on_every_key_are_quiet_controls(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path, "control.kicad_pro")
    settings = {key: "error" for key in KICAD_10_0_8_DRC_SEVERITY_STRING_KEYS}
    settings.update({key: "warning" for key in KICAD_10_0_8_DRC_SEVERITY_KEYS})
    settings.update({"legacy_no_courtyard_defined": True, "legacy_courtyards_overlap": False})
    project.write_text(
        json.dumps({"board": {"design_settings": {"rule_severities": settings}}}),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()
    assert KICAD_10_0_8_DRC_SEVERITY_STRING_KEYS == (
        KICAD_10_0_8_DRC_SEVERITY_KEYS | {"hole_near_hole"}
    )
    assert PCB_DRC_STRING_RULE_SEVERITY_KEYS_BY_KICAD_VERSION["10.0.8"] == (
        KICAD_10_0_8_DRC_SEVERITY_STRING_KEYS
    )
    legacy_boolean_keys = KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS - {"hole_near_hole"}
    assert legacy_boolean_keys <= settings.keys()
    assert not (legacy_boolean_keys & KICAD_10_0_8_DRC_SEVERITY_STRING_KEYS)


def test_typed_drc_severity_parser_remains_strict_by_default() -> None:
    document = (
        '{"board":{"design_settings":{"rule_severities":'
        '{"track_dangling":true,"via_dangling":"ignore"}}}}'
    )

    with pytest.raises(TypeError, match="must be a string"):
        configured_warning_default_drc_check_severities(document)

    assert configured_warning_default_drc_check_severities(
        document, skip_non_string_values=True
    ) == (PcbDrcCheckSeverity("via_dangling", "ignore"),)


def test_unrecognized_key_is_left_to_unknown_key_review(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":{"future_check":true}}}}',
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.7", "10.0.9", "11.0.0"))
def test_unaudited_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, version=version)

    assert _scan(root, config, source_hashes) == ()


@pytest.mark.parametrize("kind", (ProjectKind.SCHEMATIC, ProjectKind.HARNESS_INTERFACE))
def test_non_pcb_project_kinds_are_out_of_scope(tmp_path: Path, kind: ProjectKind) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=kind)

    assert _scan(root, config, source_hashes) == ()


def test_input_order_changes_do_not_change_candidate_order(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    first = {"via_dangling": True, "track_dangling": None}
    outputs = []
    for settings in (first, dict(reversed(tuple(first.items())))):
        project.write_text(
            json.dumps({"board": {"design_settings": {"rule_severities": settings}}}),
            encoding="utf-8",
        )
        candidates = _scan(root, config, {PROJECT_RELATIVE: digest(project)})
        outputs.append(tuple(item.subject for item in candidates))

    assert (
        outputs[0]
        == outputs[1]
        == (
            f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/track_dangling",
            f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/via_dangling",
        )
    )


def test_candidate_rejects_fields_that_do_not_project_from_source() -> None:
    setting = configured_pcb_drc_rule_severity_settings(
        '{"board":{"design_settings":{"rule_severities":{"track_dangling":true}}}}'
    )[0]
    source = SimpleNamespace(
        source_path=PROJECT_RELATIVE,
        source_sha256="a" * 64,
        kicad_version="10.0.8",
        project_kind=ProjectKind.PCB,
        configured_setting=setting,
    )
    candidate = PcbDrcNonStringSeverityValueCandidate.from_source_evidence(source)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, message="forged")


def test_settings_source_hash_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)
