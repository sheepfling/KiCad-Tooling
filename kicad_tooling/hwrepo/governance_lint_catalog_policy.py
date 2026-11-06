"""Repository and selected-record catalog policy for governance lint."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .discovery import ProjectRegistrySnapshot
from .governance_lint_inputs import GovernanceLintSharedInputs
from .governance_lint_scope import GovernanceLintProjectScope
from .governance_records import reviewed_value
from .models import InterfaceRecord, LibraryRecord
from .part_catalog_models import PartRecord, PartStatus
from .project_models import ToolchainRecord
from .release_model_types import ReleaseClass


@dataclass(frozen=True, slots=True)
class GovernanceLintCatalogPolicyRequest:
    """Captured catalog values, repository configuration, and selected dependencies."""

    root: Path
    registry_snapshot: ProjectRegistrySnapshot
    shared_inputs: GovernanceLintSharedInputs
    project_scope: GovernanceLintProjectScope


@dataclass(frozen=True, slots=True)
class GovernanceLintCatalogPolicyResult:
    """Ordered catalog-policy diagnostics for one governance lint request."""

    issues: tuple[str, ...]


def _missing_dependency_issues(
    scope: GovernanceLintProjectScope,
    interfaces: Mapping[str, InterfaceRecord],
    libraries: Mapping[str, LibraryRecord],
    toolchains: Mapping[str, ToolchainRecord],
) -> tuple[str, ...]:
    """Report selected references absent from their shared catalogs."""
    issues: list[str] = []
    for identifier in sorted(scope.interface_ids - interfaces.keys()):
        issues.append(f"interface catalog: missing dependency {identifier}")
    for identifier in sorted(scope.library_ids - libraries.keys()):
        issues.append(f"library catalog: missing dependency {identifier}")
    for identifier in sorted(scope.toolchain_ids - toolchains.keys()):
        issues.append(f"toolchain catalog: missing dependency {identifier}")
    return tuple(issues)


def _repository_library_path_issues(
    root: Path,
    libraries: Mapping[str, LibraryRecord],
) -> tuple[str, ...]:
    """Validate path safety for every declared library, including unused records."""
    issues: list[str] = []
    for library in libraries.values():
        for label, value in (
            ("path", library.path),
            ("provenance", library.provenance_path),
            ("licensing", library.licensing_path),
        ):
            try:
                repo_path(root, value)
            except ValueError as exc:
                issues.append(f"library {library.id}: unsafe {label}: {exc}")
    return tuple(issues)


def _selected_interface_issues(
    scope: GovernanceLintProjectScope,
    interfaces: Mapping[str, InterfaceRecord],
) -> tuple[str, ...]:
    """Validate pin declarations for interfaces in the selected dependency scope."""
    issues: list[str] = []
    for identifier in sorted(scope.interface_ids):
        interface = interfaces.get(identifier)
        if interface is None:
            continue
        if not interface.pins:
            issues.append(f"interface {interface.id}: needs a non-empty pins list")
        numbers = [pin.number for pin in interface.pins]
        if len(set(numbers)) != len(numbers):
            issues.append(f"interface {interface.id}: duplicate pin number")
    return tuple(issues)


def _selected_part_issues(
    scope: GovernanceLintProjectScope,
    parts: Mapping[str, PartRecord],
) -> tuple[str, ...]:
    """Validate alternate-part references in the selected dependency scope."""
    issues: list[str] = []
    for identifier in sorted(scope.part_ids):
        part = parts.get(identifier)
        if part is None:
            continue
        alternates = set(part.approved_alternates)
        if len(alternates) != len(part.approved_alternates):
            issues.append(f"part {part.id}: duplicate approved alternate")
        for alternate_id in alternates:
            alternate = parts.get(alternate_id)
            if alternate is None or alternate_id == part.id:
                issues.append(f"part {part.id}: unknown or self approved alternate {alternate_id}")
            elif part.status is PartStatus.APPROVED and alternate.status is not PartStatus.APPROVED:
                issues.append(f"part {part.id}: approved alternate {alternate_id} must be approved")
    return tuple(issues)


def _selected_library_issues(
    root: Path,
    scope: GovernanceLintProjectScope,
    snapshot: ProjectRegistrySnapshot,
    libraries: Mapping[str, LibraryRecord],
) -> tuple[str, ...]:
    """Validate selected library location and checkout presence."""
    layout = snapshot.discovery.repository_configuration.value.layout
    issues: list[str] = []
    for identifier in sorted(scope.library_ids):
        library = libraries.get(identifier)
        if library is None:
            continue
        try:
            if Path(library.path).parent.as_posix() not in layout.library_roots:
                issues.append(
                    f"library {library.id}: path must be a named directory under library_roots"
                )
            if not repo_path(root, library.path).is_dir():
                issues.append(f"library {library.id}: declared path is missing: {library.path}")
        except ValueError as exc:
            issues.append(f"library {library.id}: {exc}")
    return tuple(issues)


def _selected_toolchain_issues(
    scope: GovernanceLintProjectScope,
    toolchains: Mapping[str, ToolchainRecord],
) -> tuple[str, ...]:
    """Require exact native versions and digest-pinned images for selected toolchains."""
    issues: list[str] = []
    for identifier in sorted(scope.toolchain_ids):
        toolchain = toolchains.get(identifier)
        if toolchain is None:
            continue
        if not reviewed_value(toolchain.kicad_version):
            issues.append(f"toolchain {toolchain.id}: needs an exact KiCad version")
        if "@sha256:" not in toolchain.image:
            issues.append(f"toolchain {toolchain.id}: image must be digest-pinned")
    return tuple(issues)


def _repository_release_policy_issues(
    shared_inputs: GovernanceLintSharedInputs,
) -> tuple[str, ...]:
    """Require exactly one release minimum for each authored release class."""
    policy_classes = [
        policy.release_class for policy in shared_inputs.release_policies.value.policies
    ]
    if len(set(policy_classes)) == len(policy_classes) and set(policy_classes) == set(ReleaseClass):
        return ()
    return ("release policies: need exactly one minimum assurance for every release class",)


def evaluate_governance_lint_catalog_policy(
    request: GovernanceLintCatalogPolicyRequest,
) -> GovernanceLintCatalogPolicyResult:
    """Evaluate global catalog structure and selected catalog-record semantics.

    The sequence preserves the public diagnostic ordering: missing selected
    dependencies, global library path safety, selected interface/part/library/
    toolchain policy, then global release-policy completeness.
    """
    root = request.root.resolve()
    snapshot = request.registry_snapshot
    shared_inputs = request.shared_inputs
    scope = request.project_scope
    interfaces = shared_inputs.interfaces_catalog.lookup.by_id
    libraries = shared_inputs.libraries_catalog.lookup.by_id
    parts = shared_inputs.parts_catalog.lookup.by_id
    toolchains = shared_inputs.toolchains_catalog.lookup.by_id

    issues = (
        *_missing_dependency_issues(scope, interfaces, libraries, toolchains),
        *_repository_library_path_issues(root, libraries),
        *_selected_interface_issues(scope, interfaces),
        *_selected_part_issues(scope, parts),
        *_selected_library_issues(root, scope, snapshot, libraries),
        *_selected_toolchain_issues(scope, toolchains),
        *_repository_release_policy_issues(shared_inputs),
    )
    return GovernanceLintCatalogPolicyResult(issues=issues)
