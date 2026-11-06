"""Source identity and ambiguity rules for governance catalog indexes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.governance_records import (
    GovernanceCatalogIndex,
    index_governance_catalog,
    read_governance_catalog,
    read_governance_team_policy,
    review_governance_record,
)
from kicad_tooling.hwrepo.layout import read_repository_layout
from kicad_tooling.hwrepo.models import GovernanceRecord, TeamPolicy
from kicad_tooling.hwrepo.part_catalog_models import PartRecord, PartsCatalog, PartStatus


def _part(identifier: str) -> PartRecord:
    return PartRecord(
        id=identifier,
        revision="A",
        description="Synthetic test part",
        part_class="passive",
        unit="each",
        manufacturer="Example manufacturer",
        mpn="EXAMPLE-1",
        datasheet_url="https://example.com/datasheet.pdf",
        lifecycle="active",
        status=PartStatus.TRAINING,
    )


def _index(root: Path, parts: tuple[PartRecord, ...]) -> GovernanceCatalogIndex[PartRecord]:
    catalog_path = root / "catalog/parts.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    write_model(catalog_path, PartsCatalog(schema_version="1", parts=parts))
    document = read_governance_catalog(root, "catalog/parts.json", PartsCatalog)
    return index_governance_catalog(document, lambda catalog: catalog.parts, "parts catalog")


def test_catalog_index_is_bound_to_the_exact_stable_source_and_read_only(tmp_path: Path) -> None:
    part = _part("C-1")

    index = _index(tmp_path, (part,))

    source = tmp_path / "catalog/parts.json"
    assert index.source.path == "catalog/parts.json"
    assert index.source.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert index.lookup.by_id == {"C-1": part}
    assert index.lookup.issues == ()
    with pytest.raises(TypeError):
        index.lookup.by_id["C-2"] = part  # type: ignore[index]


def test_casefold_duplicate_ids_are_reported_and_excluded_from_the_lookup(
    tmp_path: Path,
) -> None:
    index = _index(tmp_path, (_part("Part-A"), _part("PART-a")))

    assert index.lookup.by_id == {}
    assert index.lookup.ambiguous_ids == frozenset({"part-a"})
    assert index.lookup.issues == ("parts catalog: duplicate id 'PART-a'",)


def test_governance_record_review_uses_the_captured_policy_and_binds_both_sources(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "catalog/team-policy.json"
    policy_path.parent.mkdir()
    original_policy = TeamPolicy(rationale="Synthetic two-person governance policy")
    write_model(policy_path, original_policy)
    original_policy_bytes = policy_path.read_bytes()
    record = GovernanceRecord(
        branch="main",
        required_status_checks=("Template acceptance",),
        authors=("author-A",),
        reviewers=("reviewer-B",),
        integrators=("author-A",),
        release_authorities=("author-A",),
        branch_protection_evidence=("synthetic-policy-record",),
        branch_protection_verified_at="2026-11-05",
    )
    record_path = tmp_path / "governance.json"
    write_model(record_path, record)

    captured_policy = read_governance_team_policy(tmp_path)
    write_model(
        policy_path,
        original_policy.model_copy(update={"minimum_actors": 3}),
    )

    review = review_governance_record(
        tmp_path,
        captured_policy,
        "governance.json",
        "board-a",
    )

    assert review.state == "EVALUATED"
    assert review.team_policy is captured_policy
    assert review.team_policy.source.path == "catalog/team-policy.json"
    assert review.team_policy.source.sha256 == hashlib.sha256(original_policy_bytes).hexdigest()
    assert review.record_source is not None
    assert review.record_source.path == "governance.json"
    assert review.record_source.sha256 == hashlib.sha256(record_path.read_bytes()).hexdigest()
    assert review.record == record
    assert not any("3 distinct actors" in issue for issue in review.issues)

    current_policy = read_governance_team_policy(tmp_path)
    current_review = review_governance_record(
        tmp_path,
        current_policy,
        "governance.json",
        "board-a",
    )
    assert current_policy.source.sha256 != captured_policy.source.sha256
    assert any("needs 3 distinct actors" in issue for issue in current_review.issues)


def test_team_policy_path_comes_from_the_captured_repository_configuration(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    policy_a = TeamPolicy(rationale="Synthetic policy selected by captured adapter")
    policy_b = TeamPolicy(
        rationale="Synthetic policy selected by a later adapter",
        minimum_actors=3,
    )
    write_model(catalog / "team-policy-a.json", policy_a)
    write_model(catalog / "team-policy-b.json", policy_b)
    adapter = tmp_path / "kicad-tooling.toml"
    adapter.write_text(
        'schema_version = "1"\n[layout]\nteam_policy = "catalog/team-policy-a.json"\n',
        encoding="utf-8",
    )
    captured_configuration = read_repository_layout(tmp_path)
    captured_policy = read_governance_team_policy(tmp_path, captured_configuration)

    adapter.write_text(
        'schema_version = "1"\n[layout]\nteam_policy = "catalog/team-policy-b.json"\n',
        encoding="utf-8",
    )
    policy_from_captured_route = read_governance_team_policy(
        tmp_path,
        captured_configuration,
    )
    policy_from_current_route = read_governance_team_policy(tmp_path)

    assert policy_from_captured_route == captured_policy
    assert policy_from_captured_route.value == policy_a
    assert policy_from_captured_route.source.path == "catalog/team-policy-a.json"
    assert policy_from_current_route.value == policy_b
    assert policy_from_current_route.source.path == "catalog/team-policy-b.json"


def test_governance_record_review_distinguishes_missing_and_unavailable_inputs(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "catalog/team-policy.json"
    policy_path.parent.mkdir()
    write_model(policy_path, TeamPolicy(rationale="Synthetic governance policy"))
    policy = read_governance_team_policy(tmp_path)

    missing = review_governance_record(tmp_path, policy, None, "board-a")
    assert missing.state == "MISSING"
    assert missing.record_source is None
    assert missing.record is None

    invalid_path = tmp_path / "governance.json"
    invalid_bytes = b"not a governance record"
    invalid_path.write_bytes(invalid_bytes)
    unavailable = review_governance_record(
        tmp_path,
        policy,
        "governance.json",
        "board-a",
    )
    assert unavailable.state == "UNAVAILABLE"
    assert unavailable.record is None
    assert unavailable.record_source is not None
    assert unavailable.record_source.sha256 == hashlib.sha256(invalid_bytes).hexdigest()
    assert any("invalid governance record" in issue for issue in unavailable.issues)
