"""Project-owned policy and catalog validation for declared KiCad projects."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from .contracts import repo_path
from .discovery import (
    ProjectConfigDocument,
    load_registry_snapshot,
    require_project_config_document_current,
    require_project_registry_snapshot_current,
)
from .governance_lint_catalog_policy import (
    GovernanceLintCatalogPolicyRequest,
    evaluate_governance_lint_catalog_policy,
)
from .governance_lint_filesystem_inputs import (
    capture_governance_lint_filesystem_inputs,
    governance_lint_filesystem_freshness_issues,
)
from .governance_lint_inputs import (
    governance_lint_shared_input_freshness_issues,
    read_governance_lint_shared_inputs,
)
from .governance_lint_models import GovernanceLintReport
from .governance_lint_project_policy import (
    GovernanceLintProjectPolicyRequest,
    GovernanceLintProjectPolicyResult,
    evaluate_governance_lint_project_policy,
)
from .governance_lint_scope import resolve_governance_lint_project_scope
from .governance_records import governance_record_review_freshness_issues
from .product_source_inputs import product_record_freshness_issues
from .project_file_membership import (
    capture_project_file_membership,
    project_file_membership_freshness_issues,
    project_file_membership_issues,
)
from .project_source_hashes import (
    project_source_inventory_freshness_issues,
)


def _project_config_freshness_issues(
    root: Path,
    documents: Iterable[ProjectConfigDocument],
) -> tuple[str, ...]:
    """Return source-change issues for every project config used by this lint run."""
    issues: list[str] = []
    for document in documents:
        try:
            require_project_config_document_current(root, document)
        except ValueError as exc:
            issues.append(str(exc))
    return tuple(issues)


def lint(root: Path, selected: Sequence[str] | None = None) -> GovernanceLintReport:
    """Lint all declared project inputs or an explicit project subset."""
    root = root.resolve()
    issues: list[str] = []
    requested = tuple(selected or ())
    try:
        registry_snapshot = load_registry_snapshot(root)
        shared_inputs = read_governance_lint_shared_inputs(root, registry_snapshot)
        issues.extend(shared_inputs.issues)
        libraries = shared_inputs.libraries_catalog.lookup.by_id
        project_entries = registry_snapshot.by_id
    except (OSError, ValueError) as exc:
        return GovernanceLintReport(
            projects=requested,
            issues=(f"registry load: {exc}",),
            status="FAIL",
        )

    scope = resolve_governance_lint_project_scope(
        root, selected, requested, registry_snapshot, shared_inputs
    )
    project_ids = scope.project_ids
    selected_records = scope.selected_records
    library_ids = scope.library_ids
    project_policy_results: list[GovernanceLintProjectPolicyResult] = []
    selected_product_record_inputs = scope.product_record_inputs
    filesystem_inputs = capture_governance_lint_filesystem_inputs(
        root,
        tuple(
            libraries[identifier] for identifier in sorted(library_ids) if identifier in libraries
        ),
        selected_records,
    )
    issues.extend(filesystem_inputs.issues)
    catalog_policy = evaluate_governance_lint_catalog_policy(
        GovernanceLintCatalogPolicyRequest(
            root=root,
            registry_snapshot=registry_snapshot,
            shared_inputs=shared_inputs,
            project_scope=scope,
        )
    )
    issues.extend(catalog_policy.issues)

    declared = {project.project for project in selected_records}
    if selected is None:
        discovery_roots = tuple(
            root / design_root for design_root in registry_snapshot.discovery.value.project_roots
        )
    else:
        selected_roots: set[Path] = set()
        for project in selected_records:
            try:
                selected_roots.add(repo_path(root, project.config).parent)
            except ValueError as exc:
                issues.append(f"project {project.id}: invalid project path: {exc}")
        discovery_roots = tuple(selected_roots)
    discovery_root_names = tuple(
        directory.relative_to(root).as_posix() for directory in discovery_roots
    )
    project_file_membership = capture_project_file_membership(root, discovery_root_names)
    issues.extend(project_file_membership_issues(project_file_membership, declared))

    for identifier in project_ids:
        entry = project_entries.get(identifier)
        if entry is None:
            issues.append(f"project registry: unknown project {identifier!r}")
            continue
        result = evaluate_governance_lint_project_policy(
            GovernanceLintProjectPolicyRequest(
                root=root,
                entry=entry,
                shared_inputs=shared_inputs,
            )
        )
        project_policy_results.append(result)
        issues.extend(result.issues)

    try:
        require_project_registry_snapshot_current(root, registry_snapshot)
    except ValueError as exc:
        issues.append(f"project registry snapshot: {exc}")
    issues.extend(
        _project_config_freshness_issues(
            root,
            (
                result.config_document
                for result in project_policy_results
                if result.config_document is not None
            ),
        )
    )
    issues.extend(governance_lint_shared_input_freshness_issues(root, shared_inputs))
    for result in project_policy_results:
        if result.governance_record_review is not None:
            issues.extend(
                governance_record_review_freshness_issues(
                    root, result.project_id, result.governance_record_review
                )
            )
    issues.extend(product_record_freshness_issues(root, selected_product_record_inputs))
    for result in project_policy_results:
        if result.source_review is not None:
            issues.extend(
                project_source_inventory_freshness_issues(
                    root, result.project_id, result.source_review.inventory
                )
            )
    issues.extend(project_file_membership_freshness_issues(root, project_file_membership))
    issues.extend(governance_lint_filesystem_freshness_issues(root, filesystem_inputs))

    return GovernanceLintReport(
        projects=project_ids,
        issues=tuple(issues),
        status="PASS" if not issues else "FAIL",
    )
