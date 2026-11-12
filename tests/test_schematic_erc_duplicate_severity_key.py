"""Source-bound review of repeated saved ERC severity keys."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_duplicate_severity_key_review import (
    SchematicErcDuplicateSeverityKeyCandidate,
    source_bound_schematic_erc_duplicate_severity_key_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    configured_schematic_erc_duplicate_rule_severity_settings,
    configured_schematic_erc_rule_severities,
)

RULE_ID = "schematic.erc_duplicate_severity_key"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-duplicate-severity"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str,
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
        SimpleNamespace(kind=kind, project=Path(PROJECT_RELATIVE), kicad_version=version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_schematic_erc_duplicate_severity_key_candidates(root, config, source_hashes)


@pytest.mark.parametrize(
    ("fixture", "expected_values"),
    (
        ("fault-ignore-last.kicad_pro", ('"warning"', '"ignore"')),
        ("fault-warning-last.kicad_pro", ('"ignore"', '"warning"')),
    ),
)
def test_duplicate_known_key_preserves_source_order_and_hash(
    tmp_path: Path,
    fixture: str,
    expected_values: tuple[str, ...],
) -> None:
    root, project, config, source_hashes = _project(tmp_path, fixture)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcDuplicateSeverityKeyCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected"
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "erc_rule_key": ("pin_not_connected",),
        "configured_values_json": expected_values,
        "occurrence_count": ("2",),
    }


def test_unknown_duplicate_and_equal_duplicate_values_are_still_visible(tmp_path: Path) -> None:
    unknown_root, _, unknown_config, unknown_hashes = _project(
        tmp_path / "unknown", "fault-unknown-duplicate.kicad_pro"
    )
    (unknown,) = _scan(unknown_root, unknown_config, unknown_hashes)
    assert unknown.evidence["erc_rule_key"] == ("future_rule",)
    assert unknown.evidence["configured_values_json"] == ('"warning"', '"ignore"')

    same_root, _, same_config, same_hashes = _project(
        tmp_path / "same", "fault-same-value-duplicate.kicad_pro"
    )
    (same,) = _scan(same_root, same_config, same_hashes)
    assert same.evidence["configured_values_json"] == ('"warning"', '"warning"')


def test_unique_severity_map_is_quiet(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control-unique.kicad_pro")
    assert _scan(root, config, source_hashes) == ()


def test_duplicate_json_keys_outside_severity_map_remain_strict(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control-duplicate-outside-map.kicad_pro")

    with pytest.raises(ValueError, match="Duplicate JSON key at other"):
        _scan(root, config, source_hashes)


def test_raw_duplicate_reader_preserves_entries_without_changing_existing_api() -> None:
    document = (FIXTURES / "fault-ignore-last.kicad_pro").read_text(encoding="utf-8")

    duplicates = configured_schematic_erc_duplicate_rule_severity_settings(document)

    assert len(duplicates) == 1
    assert duplicates[0].rule_key == "pin_not_connected"
    assert duplicates[0].configured_values_json == ('"warning"', '"ignore"')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        configured_schematic_erc_rule_severities(document)
    assert (
        configured_schematic_erc_rule_severities(
            document,
            allow_duplicate_severity_keys=True,
        )[0].severity
        == "ignore"
    )


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.9", "11.0.0"))
def test_unaudited_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(
        tmp_path, "fault-ignore-last.kicad_pro", version=version
    )

    assert _scan(root, config, source_hashes) == ()


def test_non_schematic_capable_project_kind_is_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(
        tmp_path, "fault-ignore-last.kicad_pro", kind=ProjectKind.PCB_ONLY
    )

    assert _scan(root, config, source_hashes) == ()


def test_source_hash_must_be_present_and_current_and_fields_are_derived(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path, "fault-ignore-last.kicad_pro")
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")

    project.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)


def test_repeated_scan_is_deterministic(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "fault-warning-last.kicad_pro")

    assert _scan(root, config, source_hashes) == _scan(root, config, source_hashes)
