"""Source-bound review when an ERC patch catalog is not audited."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_catalog_coverage import (
    SchematicErcCatalogCoverageCandidate,
    source_bound_schematic_erc_catalog_coverage_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import ERC_RULE_KEYS_BY_KICAD_VERSION

RULE_ID = "schematic.erc_catalog_unverified"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-global-severity"
OWNER = (
    "kicad_tooling/hwrepo/schematic_erc_catalog_coverage.py#"
    "source_bound_schematic_erc_catalog_coverage_candidates"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    *,
    version: str,
    fixture: str = "unknown.kicad_pro",
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
    return source_bound_schematic_erc_catalog_coverage_candidates(root, config, source_hashes)


@pytest.mark.parametrize("version", ("10.0.1", "10.0.2", "10.0.3", "10.0.4", "10.0.9", "11.0.0"))
def test_unverified_patch_with_explicit_overrides_creates_source_bound_review(
    tmp_path: Path, version: str
) -> None:
    root, project, config, source_hashes = _project(tmp_path, version=version)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcCatalogCoverageCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/catalog"
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (version,),
        "erc_rule_key": (
            "future_rule",
            "pin_not_conected",
            "pin_not_connected",
            "vendor_future_key",
        ),
        "configured_severity": ("warning", "ignore", "error", "error"),
    }
    assert "could not be checked" in candidate.message


@pytest.mark.parametrize("version", tuple(ERC_RULE_KEYS_BY_KICAD_VERSION))
def test_audited_patches_are_valid_controls(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, version=version)

    assert _scan(root, config, source_hashes) == ()


def test_no_override_entries_and_non_schematic_projects_are_quiet(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path, version="10.0.3")
    project.write_text(
        json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": {}}}),
        encoding="utf-8",
    )
    source_hashes = {PROJECT_RELATIVE: digest(project)}
    assert _scan(root, config, source_hashes) == ()

    pcb_only = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, pcb_only, source_hashes) == ()


def test_settings_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path, version="10.0.3")
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_candidate_fields_cannot_diverge_from_source_evidence(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, version="10.0.3")
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, message="false clean")


def test_override_source_order_does_not_change_review_summary(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path, version="10.0.3")
    entries = (("second_rule", "warning"), ("first_rule", "ignore"))
    observed: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for order in (entries, tuple(reversed(entries))):
        project.write_text(
            json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": dict(order)}}),
            encoding="utf-8",
        )
        (candidate,) = _scan(root, config, {PROJECT_RELATIVE: digest(project)})
        observed.append(
            (
                candidate.message,
                candidate.evidence["erc_rule_key"],
                candidate.evidence["configured_severity"],
            )
        )

    assert observed[0] == observed[1]


@pytest.mark.architecture
def test_rule_catalog_has_a_focused_schematic_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "schematic"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
