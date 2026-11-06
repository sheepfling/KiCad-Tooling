"""Shared identity and reviewed-value rules for project governance records."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

from .contracts import parse_model_text, read_regular_bytes, repo_path
from .evidence import digest
from .layout import RepositoryLayoutDocument, read_repository_layout
from .model_primitives import Digest, RepositoryPath
from .models import GovernanceRecord, TeamPolicy


class Identified(Protocol):
    id: str


Record = TypeVar("Record", bound=Identified)
Catalog = TypeVar("Catalog", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class GovernanceDocumentSource:
    """Exact repository file identity for an authored governance document."""

    path: RepositoryPath
    sha256: Digest


GovernanceSourceFileState = Literal["MISSING", "UNAVAILABLE", "EVALUATED"]


@dataclass(frozen=True, slots=True)
class GovernanceSourceFileInput:
    """Observed file state and exact-byte identity for one governance input."""

    requested_path: RepositoryPath
    state: GovernanceSourceFileState
    source: GovernanceDocumentSource | None
    issue: str | None

    def __post_init__(self) -> None:
        if self.state == "EVALUATED":
            if self.source is None or self.issue is not None:
                raise ValueError("Evaluated governance files require an identity and no issue")
        elif self.source is not None or self.issue is None:
            raise ValueError("Unevaluated governance files require an issue and no identity")


@dataclass(frozen=True, slots=True)
class GovernanceCatalogDocument(Generic[Catalog]):
    """Validated catalog parsed from the exact bytes named by ``source``."""

    source: GovernanceDocumentSource
    value: Catalog


@dataclass(frozen=True, slots=True)
class GovernanceRecordLookup(Generic[Record]):
    """Operation-local read-only index; case-fold collisions stay unresolved."""

    by_id: Mapping[str, Record]
    issues: tuple[str, ...]
    ambiguous_ids: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_id", MappingProxyType(dict(self.by_id)))


@dataclass(frozen=True, slots=True)
class GovernanceCatalogIndex(Generic[Record]):
    """Typed record index bound to the catalog bytes that produced its records."""

    source: GovernanceDocumentSource
    lookup: GovernanceRecordLookup[Record]


@dataclass(frozen=True, slots=True)
class GovernanceTeamPolicyDocument:
    """Team policy parsed from its retained source identity."""

    source: GovernanceDocumentSource
    value: TeamPolicy


@dataclass(frozen=True, slots=True)
class GovernanceRecordReview:
    """Project governance review bound to the team policy and record bytes."""

    team_policy: GovernanceTeamPolicyDocument
    record_source: GovernanceDocumentSource | None
    record: GovernanceRecord | None
    state: Literal["MISSING", "UNAVAILABLE", "EVALUATED"]
    issues: tuple[str, ...]
    requested_path: str | None = None


def _read_governance_source_file(
    root: Path, value: RepositoryPath
) -> tuple[GovernanceDocumentSource, bytes]:
    """Read one stable governance file and retain the path and exact-byte digest."""
    root = root.resolve()
    path = repo_path(root, value)
    content, _ = read_regular_bytes(path)
    return (
        GovernanceDocumentSource(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        content,
    )


def capture_governance_source_file(root: Path, value: RepositoryPath) -> GovernanceSourceFileInput:
    """Capture readable, missing, and unavailable governance file states."""
    try:
        root = root.resolve()
        path = repo_path(root, value)
        source = GovernanceDocumentSource(
            path=path.relative_to(root).as_posix(),
            sha256=digest(path),
        )
    except FileNotFoundError:
        return GovernanceSourceFileInput(value, "MISSING", None, "source file is missing")
    except (OSError, ValueError) as exc:
        return GovernanceSourceFileInput(value, "UNAVAILABLE", None, str(exc))
    return GovernanceSourceFileInput(value, "EVALUATED", source, None)


def read_governance_catalog(
    root: Path, value: RepositoryPath, model: type[Catalog]
) -> GovernanceCatalogDocument[Catalog]:
    """Parse one stable catalog read and retain its repository path and digest."""
    try:
        source, content = _read_governance_source_file(root, value)
        catalog = parse_model_text(content.decode("utf-8"), model)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{value}: invalid governance catalog: {exc}") from exc
    return GovernanceCatalogDocument(source=source, value=catalog)


def read_governance_team_policy(
    root: Path,
    repository_configuration: RepositoryLayoutDocument | None = None,
) -> GovernanceTeamPolicyDocument:
    """Read team policy through a captured adapter and retain its exact source."""
    root = root.resolve()
    repository_configuration = repository_configuration or read_repository_layout(root)
    value = repository_configuration.value.layout.team_policy
    try:
        source, content = _read_governance_source_file(root, value)
        policy = parse_model_text(content.decode("utf-8"), TeamPolicy)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{value}: invalid team policy: {exc}") from exc
    return GovernanceTeamPolicyDocument(source=source, value=policy)


def require_governance_document_current(root: Path, source: GovernanceDocumentSource) -> None:
    """Require an authored governance document to retain its captured bytes."""
    root = root.resolve()
    try:
        path = repo_path(root, source.path)
        current = digest(path)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"Governance source {source.path} is unavailable during operation: {exc}"
        ) from exc
    if current != source.sha256:
        raise ValueError(f"Governance source {source.path} changed during operation")


def governance_source_file_freshness_issue(
    root: Path, captured: GovernanceSourceFileInput
) -> str | None:
    """Recheck captured bytes or the explicit absence/unavailability state."""
    if captured.source is not None:
        try:
            require_governance_document_current(root, captured.source)
        except ValueError as exc:
            return str(exc)
        return None
    current = capture_governance_source_file(root, captured.requested_path)
    if current.state != captured.state:
        return (
            f"Governance source {captured.requested_path} changed state during operation "
            f"({captured.state} to {current.state})"
        )
    return None


def governance_record_review_freshness_issues(
    root: Path, project_id: str, review: GovernanceRecordReview
) -> tuple[str, ...]:
    """Recheck the source bytes or explicit absence state captured by a record review."""
    if review.record_source is not None:
        try:
            require_governance_document_current(root, review.record_source)
        except ValueError as exc:
            return (f"project {project_id}: {exc}",)
        return ()
    if review.requested_path is None:
        return ()
    try:
        path = repo_path(root.resolve(), review.requested_path)
    except ValueError:
        current_state = "UNAVAILABLE"
    else:
        try:
            read_regular_bytes(path)
        except FileNotFoundError:
            current_state = "MISSING"
        except (OSError, ValueError):
            current_state = "UNAVAILABLE"
        else:
            current_state = "EVALUATED"
    if current_state != review.state:
        message = (
            f"project {project_id}: governance record changed state during operation "
            f"({review.state} to {current_state})"
        )
        return (message,)
    return ()


def index_governance_records(
    records: Iterable[Record], label: str
) -> GovernanceRecordLookup[Record]:
    """Build a lookup that excludes every case-insensitively ambiguous ID."""
    groups: dict[str, list[Record]] = {}
    for record in records:
        groups.setdefault(record.id.casefold(), []).append(record)
    by_id: dict[str, Record] = {}
    issues: list[str] = []
    ambiguous_ids: set[str] = set()
    for normalized, group in groups.items():
        if len(group) > 1:
            ambiguous_ids.add(normalized)
            issues.extend(f"{label}: duplicate id {record.id!r}" for record in group[1:])
            continue
        by_id[group[0].id] = group[0]
    return GovernanceRecordLookup(
        by_id=by_id,
        issues=tuple(issues),
        ambiguous_ids=frozenset(ambiguous_ids),
    )


def index_governance_catalog(
    document: GovernanceCatalogDocument[Catalog],
    records: Callable[[Catalog], Iterable[Record]],
    label: str,
) -> GovernanceCatalogIndex[Record]:
    """Index one typed catalog without detaching records from their source."""
    return GovernanceCatalogIndex(
        source=document.source,
        lookup=index_governance_records(records(document.value), label),
    )


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


def review_governance_record(
    root: Path,
    team_policy: GovernanceTeamPolicyDocument,
    value: str | None,
    identifier: str,
) -> GovernanceRecordReview:
    """Evaluate one project record against the exact retained team policy."""
    root = root.resolve()
    issues: list[str] = []
    if value is None:
        issues.append(f"project {identifier}: governance record is missing")
        return GovernanceRecordReview(team_policy, None, None, "MISSING", tuple(issues))
    try:
        repo_path(root, value)
    except ValueError as exc:
        issues.append(f"project {identifier}: governance record: {exc}")
        return GovernanceRecordReview(team_policy, None, None, "UNAVAILABLE", tuple(issues), value)
    try:
        record_source, content = _read_governance_source_file(root, value)
    except FileNotFoundError:
        issues.append(f"project {identifier}: governance record is missing")
        return GovernanceRecordReview(team_policy, None, None, "MISSING", tuple(issues), value)
    except (OSError, ValueError) as exc:
        issues.append(f"project {identifier}: invalid governance record: {exc}")
        return GovernanceRecordReview(team_policy, None, None, "UNAVAILABLE", tuple(issues), value)
    try:
        record = parse_model_text(content.decode("utf-8"), GovernanceRecord)
    except (UnicodeError, ValueError) as exc:
        issues.append(f"project {identifier}: invalid governance record: {exc}")
        return GovernanceRecordReview(
            team_policy, record_source, None, "UNAVAILABLE", tuple(issues), value
        )

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
    policy = team_policy.value
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
    return GovernanceRecordReview(
        team_policy, record_source, record, "EVALUATED", tuple(issues), value
    )


def lint_governance_record(root: Path, value: str | None, identifier: str) -> tuple[str, ...]:
    """Compatibility projection returning only governance-record issues."""
    root = root.resolve()
    if value is None:
        return (f"project {identifier}: governance record is missing",)
    try:
        path = repo_path(root, value)
    except ValueError as exc:
        return (f"project {identifier}: governance record: {exc}",)
    if not path.is_file():
        return (f"project {identifier}: governance record is missing",)
    try:
        policy = read_governance_team_policy(root)
    except (OSError, UnicodeError, ValueError) as exc:
        return (f"project {identifier}: invalid governance record: {exc}",)
    return review_governance_record(root, policy, value, identifier).issues
