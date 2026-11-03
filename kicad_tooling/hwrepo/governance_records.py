"""Shared identity and reviewed-value rules for project governance records."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, TypeVar

from .contracts import read_model, repo_path
from .layout import layout
from .models import GovernanceRecord, TeamPolicy


class Identified(Protocol):
    id: str


Record = TypeVar("Record", bound=Identified)


def records_by_id(
    records: Iterable[Record], label: str
) -> tuple[dict[str, Record], tuple[str, ...]]:
    result: dict[str, Record] = {}
    issues: list[str] = []
    casefolded: set[str] = set()
    for record in records:
        if record.id.casefold() in casefolded:
            issues.append(f"{label}: duplicate id {record.id!r}")
        casefolded.add(record.id.casefold())
        result[record.id] = record
    return result, tuple(issues)


def reviewed_value(value: str) -> bool:
    """Reject empty and template/training placeholders in production records."""
    if not value.strip():
        return False
    normalized: str = value.casefold().replace("-", " ").replace("_", " ")
    return not any(
        marker in normalized
        for marker in (
            "replace with",
            "unspecified",
            "do not purchase",
            "training",
            "example.invalid",
            "unknown",
            "your name",
            "todo",
        )
    )


def lint_governance_record(root: Path, value: str | None, identifier: str) -> tuple[str, ...]:
    """Require a real multi-role governance record for production projects."""
    issues: list[str] = []
    if value is None:
        issues.append(f"project {identifier}: governance record is missing")
        return tuple(issues)
    try:
        path = repo_path(root, value)
    except ValueError as exc:
        issues.append(f"project {identifier}: governance record: {exc}")
        return tuple(issues)
    if not path.is_file():
        issues.append(f"project {identifier}: governance record is missing")
        return tuple(issues)
    try:
        record = read_model(path, GovernanceRecord)
        policy = read_model(repo_path(root, layout(root).team_policy), TeamPolicy)
    except (OSError, ValueError) as exc:
        issues.append(f"project {identifier}: invalid governance record: {exc}")
        return tuple(issues)
    if not reviewed_value(record.branch):
        issues.append(f"project {identifier}: governance record needs a protected branch")
    if not record.required_status_checks or any(
        not reviewed_value(check) for check in record.required_status_checks
    ):
        issues.append(
            f"project {identifier}: governance record needs reviewed required_status_checks"
        )
    people: set[str] = set()
    for field, assigned in (
        ("authors", record.authors),
        ("reviewers", record.reviewers),
        ("integrators", record.integrators),
    ):
        if not assigned or any(not reviewed_value(person) for person in assigned):
            issues.append(f"project {identifier}: governance record needs reviewed {field}")
            continue
        people.update(person.casefold() for person in assigned)
    if len(people) < policy.minimum_actors:
        issues.append(
            f"project {identifier}: governance record needs {policy.minimum_actors} distinct actors"
        )
    if policy.independent_review and (
        {person.casefold() for person in record.authors}
        & {person.casefold() for person in record.reviewers}
    ):
        issues.append(f"project {identifier}: reviewers must be independent of authors")
    if not set(policy.required_status_checks) <= set(record.required_status_checks):
        issues.append(f"project {identifier}: governance record omits team-required status checks")
    for field, assigned in (
        ("release_authorities", record.release_authorities),
        ("branch_protection_evidence", record.branch_protection_evidence),
        ("branch_protection_verified_at", (record.branch_protection_verified_at,)),
    ):
        valid = bool(assigned) and all(reviewed_value(item) for item in assigned)
        if not valid:
            issues.append(f"project {identifier}: governance record needs reviewed {field}")
    return tuple(issues)
