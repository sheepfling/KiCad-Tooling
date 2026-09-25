"""Read-only GitHub controls audit with explicit API and team-evidence limits."""
from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar, cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, ValidationError

from ..lint_registry import reviewed_value
from .contracts import read_model, repo_path
from .models import GovernanceRecord, HostedGovernanceCheck, HostedGovernanceReport, TeamPolicy

REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OWNER_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OWNER_HANDLE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)?$")
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
AuditStatus = Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]


@dataclass(frozen=True)
class ApiError(Exception):
    endpoint: str
    detail: str
    status_code: int | None = None

    def __str__(self) -> str:
        return f"{self.endpoint}: {self.detail}"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


TApiModel = TypeVar("TApiModel", bound=ApiModel)


class RepoView(ApiModel):
    nameWithOwner: str


class Repository(ApiModel):
    full_name: str
    default_branch: str


class RequiredCheck(ApiModel):
    context: str


class RuleParameters(ApiModel):
    required_status_checks: list[RequiredCheck] | None = None
    strict_required_status_checks_policy: bool | None = None
    required_approving_review_count: int | None = None
    dismiss_stale_reviews_on_push: bool | None = None
    require_code_owner_review: bool | None = None


class BranchRule(ApiModel):
    type: str
    parameters: RuleParameters | None = None


class ReviewProtection(ApiModel):
    required_approving_review_count: int | None = None
    dismiss_stale_reviews: bool | None = None
    require_code_owner_reviews: bool | None = None


class StatusProtection(ApiModel):
    strict: bool | None = None
    contexts: list[str] | None = None
    checks: list[RequiredCheck] | None = None


class EnabledValue(ApiModel):
    enabled: bool


class BranchProtection(ApiModel):
    required_pull_request_reviews: ReviewProtection | None = None
    required_status_checks: StatusProtection | None = None
    allow_force_pushes: EnabledValue | None = None


class RepositoryContent(ApiModel):
    type: str
    encoding: str | None = None
    content: str | None = None
    size: int | None = None


class CodeownersError(ApiModel):
    line: int
    kind: str


class CodeownersErrors(ApiModel):
    errors: list[CodeownersError]


@dataclass(frozen=True)
class Facts:
    source: str
    available: bool
    protected: bool | None = None
    pull_request: bool | None = None
    approvals: int | None = None
    stale_reviews: bool | None = None
    code_owner_review: bool | None = None
    up_to_date: bool | None = None
    force_push_blocked: bool | None = None
    required_checks: frozenset[str] | None = None
    error: str | None = None


def _gh(root: Path, *args: str) -> object:
    """Run only read operations; never include tokens or mutation verbs in argv."""
    command = ("gh", *args)
    endpoint = " ".join(args)
    if args != ("repo", "view", "--json", "nameWithOwner") and not (
        args and args[0] == "api" and args[-1].startswith("repos/")
        and all(option in {"--paginate", "--slurp"} for option in args[1:-1])
    ):
        raise ApiError(endpoint, "Only read-only repository queries are supported")
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                check=False, timeout=25)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApiError(endpoint, str(exc)) from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "gh returned an error"
        match = re.search(r"HTTP (\d{3})", result.stderr)
        raise ApiError(endpoint, detail, int(match.group(1)) if match else None)
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ApiError(endpoint, f"invalid JSON: {exc}") from exc


def _model(value: object, kind: type[TApiModel], source: str) -> TApiModel:
    try:
        return kind.model_validate(value, strict=True)
    except ValidationError as exc:
        raise ApiError(source, f"unexpected API response: {exc.errors()[0]['msg']}") from exc


def _branch_rules(root: Path, repository: str, branch: str) -> Facts:
    endpoint = f"repos/{repository}/rules/branches/{quote(branch, safe='')}?per_page=100"
    try:
        pages = _gh(root, "api", "--paginate", "--slurp", endpoint)
        if not isinstance(pages, list) or any(not isinstance(page, list)
                                               for page in cast(list[object], pages)):
            raise ApiError(endpoint, "unexpected paginated rules response")
        values = [value for page in cast(list[list[object]], pages) for value in page]
        rules = tuple(_model(value, BranchRule, endpoint) for value in values)
    except ApiError as exc:
        return Facts(source=endpoint, available=False, error=str(exc))
    pull_rules = [rule for rule in rules if rule.type == "pull_request"]
    status_rules = [rule for rule in rules if rule.type == "required_status_checks"]
    approvals = [rule.parameters.required_approving_review_count for rule in pull_rules
                 if rule.parameters is not None]
    checks = [check.context for rule in status_rules if rule.parameters is not None
              for check in (rule.parameters.required_status_checks or ())]
    incomplete_pull = any(rule.parameters is None or
                          rule.parameters.required_approving_review_count is None
                          for rule in pull_rules)
    incomplete_checks = any(rule.parameters is None or
                            rule.parameters.required_status_checks is None
                            for rule in status_rules)

    def rule_bool(field: str, selected: list[BranchRule]) -> bool | None:
        values = [getattr(rule.parameters, field) if rule.parameters is not None else None
                  for rule in selected]
        if True in values:
            return True
        return None if None in values else False

    return Facts(
        source=endpoint, available=True, protected=bool(rules),
        pull_request=bool(pull_rules),
        approvals=None if incomplete_pull else max((value for value in approvals if value is not None), default=0),
        stale_reviews=rule_bool("dismiss_stale_reviews_on_push", pull_rules),
        code_owner_review=rule_bool("require_code_owner_review", pull_rules),
        up_to_date=rule_bool("strict_required_status_checks_policy", status_rules),
        force_push_blocked=any(rule.type == "non_fast_forward" for rule in rules),
        required_checks=None if incomplete_checks else frozenset(checks),
    )


def _legacy_protection(root: Path, repository: str, branch: str) -> Facts:
    endpoint = f"repos/{repository}/branches/{quote(branch, safe='')}/protection"
    try:
        protection = _model(_gh(root, "api", endpoint), BranchProtection, endpoint)
    except ApiError as exc:
        # GitHub can return 404 for either no rule or insufficient Administration:read.
        return Facts(source=endpoint, available=False, error=str(exc))
    assert isinstance(protection, BranchProtection)
    review = protection.required_pull_request_reviews
    status = protection.required_status_checks
    return Facts(
        source=endpoint, available=True, protected=True,
        pull_request=review is not None,
        approvals=(0 if review is None else review.required_approving_review_count),
        stale_reviews=(False if review is None else review.dismiss_stale_reviews),
        code_owner_review=(False if review is None else review.require_code_owner_reviews),
        up_to_date=(False if status is None else status.strict),
        force_push_blocked=(None if protection.allow_force_pushes is None else
                            not protection.allow_force_pushes.enabled),
        required_checks=(frozenset() if status is None else
                         frozenset((*(() if status.contexts is None else status.contexts),
                                    *(check.context for check in (status.checks or ()))))) if
                         status is None or status.contexts is not None or status.checks is not None
                         else None,
    )


def _combined_bool(rules: Facts, protection: Facts, name: str) -> bool | None:
    values = (getattr(rules, name), getattr(protection, name))
    if True in values:
        return True
    return False if values == (False, False) else None


def _combined_count(rules: Facts, protection: Facts, minimum: int) -> int | None:
    values = (rules.approvals, protection.approvals)
    known = [value for value in values if value is not None]
    if any(value >= minimum for value in known):
        return max(known)
    return max(known) if len(known) == 2 else None


def _check(id: str, expected: str, observed: str, status: AuditStatus, source: str | None,
           next_action: str | None = None) -> HostedGovernanceCheck:
    return HostedGovernanceCheck(id=id, expected=expected, observed=observed,
                                 status=status, source=source, next_action=next_action)


def _overall(checks: tuple[HostedGovernanceCheck, ...] | list[HostedGovernanceCheck]) -> AuditStatus:
    if any(check.status == "NEEDS_SETUP" for check in checks):
        return "NEEDS_SETUP"
    if any(check.status == "UNKNOWN" for check in checks):
        return "UNKNOWN"
    return "PASS"


def _setting(id: str, expected: str, value: bool | None, source: str,
             action: str) -> HostedGovernanceCheck:
    return _check(id, expected, "yes" if value is True else "no" if value is False else
                  "API evidence incomplete", "PASS" if value is True else
                  "NEEDS_SETUP" if value is False else "UNKNOWN", source,
                  None if value is True else action)


def _codeowners(root: Path, repository: str, branch: str) -> tuple[HostedGovernanceCheck, tuple[str, ...]]:
    ref = quote(branch, safe="")
    for path in CODEOWNERS_PATHS:
        endpoint = f"repos/{repository}/contents/{path}?ref={ref}"
        try:
            item = _model(_gh(root, "api", endpoint), RepositoryContent, endpoint)
        except ApiError as exc:
            if exc.status_code == 404:
                continue
            # An unreadable higher-priority file could override any lower-priority one.
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          str(exc), "UNKNOWN", endpoint,
                          "Grant Contents:read or inspect the default branch directly."), ()
        assert isinstance(item, RepositoryContent)
        if item.size is not None and item.size >= 3 * 1024 * 1024:
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"{path} exceeds GitHub's 3 MB loading limit", "NEEDS_SETUP", endpoint,
                          "Reduce CODEOWNERS below 3 MB."), ()
        if item.type != "file" or item.encoding != "base64" or item.content is None:
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"{path} could not be decoded", "UNKNOWN", endpoint,
                          "Inspect CODEOWNERS on the default branch."), ()
        try:
            lines = base64.b64decode("".join(item.content.split()), validate=True).decode("utf-8").splitlines()
        except (ValueError, UnicodeError) as exc:
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"{path}: {exc}", "UNKNOWN", endpoint,
                          "Repair or inspect CODEOWNERS encoding."), ()
        owners_set: set[str] = set()
        for number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 2 or any(
                not (OWNER_HANDLE.fullmatch(owner) or OWNER_EMAIL.fullmatch(owner))
                for owner in fields[1:]
            ):
                return _check("codeowners_file", "Active CODEOWNERS on default branch",
                              f"{path} line {number} has a missing or malformed owner entry",
                              "NEEDS_SETUP", endpoint,
                              "Repair the named CODEOWNERS entry and rerun the audit."), ()
            owners_set.update(fields[1:])
        owners = tuple(sorted(owners_set))
        if not owners or any("YOUR-" in owner.upper() or "REPLACE" in owner.upper()
                             for owner in owners):
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"{path} has no reviewed owner entries", "NEEDS_SETUP", endpoint,
                          "Populate CODEOWNERS with real user or team handles."), owners
        errors_endpoint = f"repos/{repository}/codeowners/errors?ref={ref}"
        try:
            errors = _model(_gh(root, "api", errors_endpoint), CodeownersErrors, errors_endpoint)
        except ApiError as exc:
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"Cannot verify CODEOWNERS syntax: {exc}", "UNKNOWN", errors_endpoint,
                          "Grant Contents:read or inspect GitHub's CODEOWNERS errors on the default branch."), ()
        if errors.errors:
            examples = ", ".join(f"line {error.line}: {error.kind}" for error in errors.errors[:3])
            return _check("codeowners_file", "Active CODEOWNERS on default branch",
                          f"{path} has {len(errors.errors)} GitHub CODEOWNERS error(s): {examples}",
                          "NEEDS_SETUP", errors_endpoint,
                          "Repair GitHub's reported CODEOWNERS errors and rerun the audit."), ()
        return _check("codeowners_file", "Active CODEOWNERS on default branch",
                      f"{path} declares {len(owners)} owner entry/entries; GitHub reports no syntax errors",
                      "PASS", f"{endpoint}; {errors_endpoint}"), owners
    # A successful root listing establishes Contents:read before interpreting 404s as absence.
    endpoint = f"repos/{repository}/contents?ref={ref}"
    try:
        listing = _gh(root, "api", endpoint)
        if not isinstance(listing, list):
            raise ApiError(endpoint, "unexpected contents listing")
    except ApiError as exc:
        return _check("codeowners_file", "Active CODEOWNERS on default branch",
                      str(exc), "UNKNOWN", endpoint,
                      "Grant Contents:read or inspect the default branch directly."), ()
    return _check("codeowners_file", "Active CODEOWNERS on default branch",
                  "No CODEOWNERS in .github/, root, or docs/", "NEEDS_SETUP", endpoint,
                  "Add CODEOWNERS with real reviewers before requiring owner review."), ()


def audit(root: Path, repository: str | None = None, record_path: str | None = None) -> HostedGovernanceReport:
    """Compare live default-branch controls with local policy; never mutate GitHub."""
    root = root.resolve()
    try:
        policy = read_model(repo_path(root, "catalog/team-policy.json"), TeamPolicy)
        record = (None if record_path is None else
                  read_model(repo_path(root, record_path), GovernanceRecord))
    except (OSError, ValueError) as exc:
        return HostedGovernanceReport(status="NEEDS_SETUP", hosted_controls_status="NEEDS_SETUP", checks=(
            _check("local_policy", "Readable team policy and optional governance record",
                   str(exc), "NEEDS_SETUP", None,
                   "Repair the named local policy or governance record."),
        ))
    if repository is None:
        try:
            view = _model(_gh(root, "repo", "view", "--json", "nameWithOwner"),
                          RepoView, "gh repo view")
            assert isinstance(view, RepoView)
            repository = view.nameWithOwner
        except ApiError as exc:
            return HostedGovernanceReport(status="UNKNOWN", hosted_controls_status="UNKNOWN", checks=(
                _check("repository_api", "Readable GitHub repository", str(exc), "UNKNOWN",
                       "gh repo view", "Authenticate gh or pass --repo OWNER/REPO."),
            ))
    if not REPOSITORY_NAME.fullmatch(repository):
        return HostedGovernanceReport(status="NEEDS_SETUP", hosted_controls_status="NEEDS_SETUP",
            repository=repository,
            checks=(_check("repository_name", "OWNER/REPO", repository, "NEEDS_SETUP",
                           None, "Pass --repo OWNER/REPO."),))
    endpoint = f"repos/{repository}"
    try:
        metadata = _model(_gh(root, "api", endpoint), Repository, endpoint)
        assert isinstance(metadata, Repository)
    except ApiError as exc:
        return HostedGovernanceReport(status="UNKNOWN", hosted_controls_status="UNKNOWN",
            repository=repository,
            checks=(_check("repository_api", "Readable GitHub repository", str(exc),
                           "UNKNOWN", endpoint, "Check gh authentication and repository access."),))
    repository = metadata.full_name
    branch = metadata.default_branch
    rules = _branch_rules(root, repository, branch)
    protection = _legacy_protection(root, repository, branch)
    source = f"{rules.source}; {protection.source}"
    checks: list[HostedGovernanceCheck] = [
        _check("default_branch", "GitHub default branch identified", branch, "PASS", endpoint),
        _setting("branch_protected", "Active branch rules or legacy protection",
                 _combined_bool(rules, protection, "protected"), source,
                 "Configure protection for the default branch; grant Administration:read if legacy settings are hidden."),
        _setting("pull_requests_required", "Pull requests required for covered actors",
                 _combined_bool(rules, protection, "pull_request"), source,
                 "Require pull requests for the default branch."),
    ]
    required = tuple(dict.fromkeys((*policy.required_status_checks,
                                    *(() if record is None else record.required_status_checks))))
    known_checks: set[str] = set()
    for observed_checks in (rules.required_checks, protection.required_checks):
        if observed_checks is not None:
            known_checks.update(observed_checks)
    missing_checks = sorted(set(required) - known_checks)
    checks_complete = rules.required_checks is not None and protection.required_checks is not None
    checks.append(_check(
        "required_checks", ", ".join(required),
        ", ".join(sorted(known_checks)) or "none observed",
        "PASS" if not missing_checks else "NEEDS_SETUP" if checks_complete else "UNKNOWN",
        source,
        None if not missing_checks else f"Require exact check name(s): {', '.join(missing_checks)}.",
    ))
    approval_minimum = 1 if policy.independent_review else 0
    approval_count = _combined_count(rules, protection, approval_minimum)
    checks.append(_check(
        "approvals", f"At least {approval_minimum} approval(s) per pull request",
        str(approval_count) if approval_count is not None else "API evidence incomplete",
        "PASS" if approval_count is not None and approval_count >= approval_minimum else
        "NEEDS_SETUP" if approval_count is not None else "UNKNOWN", source,
        None if approval_count is not None and approval_count >= approval_minimum else
        "Set the required approval count; verify independent reviewers can approve.",
    ))
    if policy.independent_review:
        checks.append(_setting("dismiss_stale_reviews", "Dismiss stale approvals on push",
                               _combined_bool(rules, protection, "stale_reviews"), source,
                               "Enable dismissal of stale approvals."))
    checks.append(_setting("up_to_date", "Required checks use the latest target branch",
                           _combined_bool(rules, protection, "up_to_date"), source,
                           "Enable strict, up-to-date required checks."))
    checks.append(_setting("force_push_blocked", "Force pushes blocked for covered actors",
                           _combined_bool(rules, protection, "force_push_blocked"), source,
                           "Disallow force pushes on the default branch."))
    codeowners, owners = _codeowners(root, repository, branch)
    checks.append(codeowners)
    checks.append(_setting("code_owner_review", "Require code-owner review",
                           _combined_bool(rules, protection, "code_owner_review"), source,
                           "Require code-owner review after populating CODEOWNERS."))
    if record is not None:
        checks.append(_check(
            "governance_branch", "Governance record matches the hosted default branch",
            record.branch, "PASS" if record.branch == branch else "NEEDS_SETUP",
            record_path,
            None if record.branch == branch else "Update the governance record or the hosted default branch.",
        ))
    declared_people = (() if record is None else
                       (*record.authors, *record.reviewers, *record.integrators))
    role_groups = (() if record is None else (
        ("authors", record.authors), ("reviewers", record.reviewers),
        ("integrators", record.integrators),
    ))
    missing_roles = tuple(role for role, people in role_groups if not people)
    record_needs_setup = record is not None and (
        bool(missing_roles)
        or len({person.casefold() for person in declared_people}) < policy.minimum_actors
        or any(not reviewed_value(person) for person in declared_people)
        or (policy.independent_review and bool(
            {person.casefold() for person in record.authors}
            & {person.casefold() for person in record.reviewers}
        ))
    )
    if missing_roles:
        identity_observed = f"Governance record is missing {', '.join(missing_roles)}"
        identity_action = (
            f"Assign and review at least one {', '.join(missing_roles)} role in the governance record."
        )
    elif record_needs_setup:
        identity_observed = "Governance record has placeholders or insufficient independent actors"
        identity_action = "Replace governance-record placeholders with independently reviewed actors."
    else:
        identity_observed = (
            f"{len(owners)} CODEOWNERS owner(s), {len(declared_people)} declared role(s); "
            "live permissions and team rehearsal unverified"
        )
        identity_action = (
            "Confirm real users/teams have write and review rights, inspect bypass actors, "
            "and rehearse approvals, rejected checks, and access revocation."
        )
    checks.append(_check(
        "team_identities",
        f"At least {policy.minimum_actors} real actors and rehearsed review/merge permissions",
        identity_observed,
        "NEEDS_SETUP" if record_needs_setup else "UNKNOWN", record_path,
        identity_action,
    ))
    hosted_controls_status = _overall([check for check in checks if check.id != "team_identities"])
    status = _overall(checks)
    return HostedGovernanceReport(
        repository=repository, default_branch=branch, required_status_checks=required,
        hosted_controls_status=hosted_controls_status, status=status, checks=tuple(checks),
        next_actions=tuple(dict.fromkeys(check.next_action for check in checks if check.next_action)),
    )


def format_text(report: HostedGovernanceReport) -> str:
    lines = [f"Hosted governance audit: {report.status}"]
    lines.append(f"Hosted controls: {report.hosted_controls_status}")
    if report.repository:
        lines.append(f"Repository: {report.repository}")
    if report.default_branch:
        lines.append(f"Default branch: {report.default_branch}")
    for check in report.checks:
        lines.append(f"  {check.id}: {check.status} ({check.observed})")
        if check.next_action:
            lines.append(f"    Next: {check.next_action}")
    lines.append("Scope: read-only GitHub settings; no desktop, permission-drill, or hardware approval.")
    return "\n".join(lines)
