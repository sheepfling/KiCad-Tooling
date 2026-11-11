"""Source-bound review of unknown saved schematic ERC severity keys."""

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
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    ERC_RULE_KEYS_BY_KICAD_VERSION,
)
from kicad_tooling.hwrepo.schematic_erc_unknown_rule_key_review import (
    SchematicErcUnknownRuleKeyCandidate,
    source_bound_schematic_erc_unknown_rule_key_candidates,
)

RULE_ID = "schematic.erc_unknown_rule_key"
AUDITED_KICAD_VERSIONS = (
    "10.0.0",
    "10.0.1",
    "10.0.2",
    "10.0.4",
    "10.0.5",
    "10.0.6",
    "10.0.7",
    "10.0.8",
)
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-global-severity"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "unknown.kicad_pro",
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
    return source_bound_schematic_erc_unknown_rule_key_candidates(root, config, source_hashes)


def test_known_key_catalog_is_closed_to_audited_patches() -> None:
    assert set(ERC_RULE_KEYS_BY_KICAD_VERSION) == set(AUDITED_KICAD_VERSIONS)
    baseline = ERC_RULE_KEYS_BY_KICAD_VERSION["10.0.0"]
    for version in ("10.0.1", "10.0.2", "10.0.4", "10.0.5", "10.0.6"):
        assert ERC_RULE_KEYS_BY_KICAD_VERSION[version] == baseline
    expanded = baseline | {"same_local_global_power"}
    for version in ("10.0.7", "10.0.8"):
        assert ERC_RULE_KEYS_BY_KICAD_VERSION[version] == expanded
    assert len(baseline) == 46
    assert len(expanded) == 47


def test_native_matrix_covers_each_audited_patch_with_a_pinned_image() -> None:
    versions = tuple(version for version, _image in KICAD_10_ERC_SEVERITY_TOOLCHAINS)
    images = tuple(image for _version, image in KICAD_10_ERC_SEVERITY_TOOLCHAINS)

    assert versions == AUDITED_KICAD_VERSIONS
    assert len(images) == len(set(images))
    assert all(
        f"ghcr.io/kicad/kicad:{version}@sha256:" in image
        for version, image in zip(versions, images, strict=True)
    )


@pytest.mark.parametrize("version", AUDITED_KICAD_VERSIONS)
def test_unknown_keys_at_each_severity_create_source_bound_review_candidates(
    tmp_path: Path, version: str
) -> None:
    root, project, config, source_hashes = _project(tmp_path, kicad_version=version)

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 3
    typed_candidates = tuple(
        item for item in candidates if isinstance(item, SchematicErcUnknownRuleKeyCandidate)
    )
    assert len(typed_candidates) == 3
    assert tuple(item.source_evidence.configured_rule.rule_key for item in typed_candidates) == (
        "future_rule",
        "pin_not_conected",
        "vendor_future_key",
    )
    expected_severity = {
        "future_rule": "warning",
        "pin_not_conected": "ignore",
        "vendor_future_key": "error",
    }
    for candidate in typed_candidates:
        key = candidate.source_evidence.configured_rule.rule_key
        assert candidate.rule_id == RULE_ID
        assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/{key}"
        assert candidate.evidence == {
            "source_path": (PROJECT_RELATIVE,),
            "source_sha256": (digest(project),),
            "kicad_version": (version,),
            "erc_rule_key": (key,),
            "configured_severity": (expected_severity[key],),
        }
        assert "may not affect native ERC" in candidate.message


@pytest.mark.parametrize("version", AUDITED_KICAD_VERSIONS)
@pytest.mark.parametrize("severity", ("error", "warning", "ignore"))
def test_every_known_key_is_a_valid_control_at_each_severity(
    tmp_path: Path, version: str, severity: str
) -> None:
    root, project, config, _ = _project(tmp_path, kicad_version=version)
    configured = {key: severity for key in ERC_RULE_KEYS_BY_KICAD_VERSION[version]}
    project.write_text(
        json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": configured}}),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


def test_unsupported_versions_and_non_schematic_kinds_are_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    for version in (
        "9.0.0",
        "10.0.3",
        "10.0.9",
        "11.0.0",
    ):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT_RELATIVE, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()
    pcb_only = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, pcb_only, source_hashes) == ()
    assert config.kind is ProjectKind.PCB


def test_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_candidate_fields_cannot_diverge_from_source_settings(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)[:1]

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")


def test_source_order_does_not_change_candidate_order_or_subjects(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    entries = (
        ("second_unknown", "warning"),
        ("first_unknown", "ignore"),
        ("pin_not_connected", "error"),
    )
    observed: list[tuple[tuple[str, str], ...]] = []
    for order in (entries, tuple(reversed(entries))):
        document = json.dumps({"erc": {"meta": {"version": 0}, "rule_severities": dict(order)}})
        project.write_text(document, encoding="utf-8")
        candidates = _scan(root, config, {PROJECT_RELATIVE: digest(project)})
        observed.append(
            tuple(
                (item.subject, item.source_evidence.configured_rule.rule_key)
                for item in candidates
                if isinstance(item, SchematicErcUnknownRuleKeyCandidate)
            )
        )

    assert observed[0] == observed[1]
