"""Source-bound review of invalid saved schematic ERC severity strings."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_ERC_SEVERITY_TOOLCHAINS
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_invalid_severity_value_review import (
    SchematicErcInvalidSeverityValueCandidate,
    source_bound_schematic_erc_invalid_severity_value_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    configured_schematic_erc_rule_severities,
)

RULE_ID = "schematic.erc_invalid_severity_value"
AUDITED_KICAD_VERSIONS = tuple(version for version, _ in KICAD_10_ERC_SEVERITY_TOOLCHAINS)
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-invalid-severity"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


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
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_schematic_erc_invalid_severity_value_candidates(root, config, source_hashes)


@pytest.mark.parametrize("version", AUDITED_KICAD_VERSIONS)
def test_recognized_key_with_invalid_string_creates_source_bound_review(
    tmp_path: Path, version: str
) -> None:
    root, project, config, source_hashes = _project(tmp_path, kicad_version=version)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcInvalidSeverityValueCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected"
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (version,),
        "erc_rule_key": ("pin_not_connected",),
        "configured_severity": ("warnnig",),
    }
    assert "does not recognize ERC severity 'warnnig'" in candidate.message


@pytest.mark.parametrize("severity", ("error", "warning", "ignore"))
def test_canonical_severity_strings_are_valid_controls(tmp_path: Path, severity: str) -> None:
    root, project, config, _ = _project(tmp_path, fixture="control.kicad_pro")
    project.write_text(
        json.dumps(
            {"erc": {"meta": {"version": 0}, "rule_severities": {"pin_not_connected": severity}}}
        ),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


def test_unknown_key_with_invalid_string_belongs_to_unknown_key_rule(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    project.write_text(
        json.dumps(
            {"erc": {"meta": {"version": 0}, "rule_severities": {"future_rule": "warnnig"}}}
        ),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


def test_parser_keeps_strict_default_and_can_retain_invalid_strings() -> None:
    document = (FIXTURES / "fault.kicad_pro").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="not supported"):
        configured_schematic_erc_rule_severities(document)

    (severity,) = configured_schematic_erc_rule_severities(
        document, allow_unrecognized_severity_strings=True
    )
    assert severity.rule_key == "pin_not_connected"
    assert severity.severity == "warnnig"


def test_unsupported_versions_and_non_schematic_kinds_are_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    for version in ("9.0.0", "10.0.3", "10.0.9", "11.0.0"):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT_RELATIVE, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()
    unsupported_kind = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, unsupported_kind, source_hashes) == ()
    assert config.kind is ProjectKind.PCB


def test_source_hash_is_required_and_candidate_fields_are_bound(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")


def test_key_source_order_does_not_change_candidate_order(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    first = {"pin_not_connected": "warnnig", "wire_dangling": "errror"}
    second = dict(reversed(tuple(first.items())))
    observed = []
    for values in (first, second):
        project.write_text(
            json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": values}}),
            encoding="utf-8",
        )
        observed.append(
            tuple(
                (candidate.subject, candidate.evidence["configured_severity"])
                for candidate in _scan(root, config, {PROJECT_RELATIVE: digest(project)})
            )
        )

    assert observed[0] == observed[1]
    assert tuple(item[1] for item in observed[0]) == (("warnnig",), ("errror",))
