"""Per-project governance policies and their captured source records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .discovery import (
    ProjectConfigDocument,
    ProjectRegistryEntry,
    load_project_config_document_from_snapshot,
)
from .electrical import policy_issues as electrical_policy_issues
from .governance_lint_inputs import GovernanceLintSharedInputs
from .governance_records import GovernanceRecordReview, review_governance_record, reviewed_value
from .part_catalog_models import PartStatus
from .project_models import ProjectConfig, ProjectKind, ToolchainRecord
from .project_source_hashes import (
    ProjectSourceInventoryInput,
    capture_project_source_inventory,
    project_source_inventory_issues,
)


@dataclass(frozen=True, slots=True)
class GovernanceLintProjectPolicyRequest:
    """Captured repository inputs for one selected project's policy pass."""

    root: Path
    entry: ProjectRegistryEntry
    shared_inputs: GovernanceLintSharedInputs


@dataclass(frozen=True, slots=True)
class GovernanceProjectSourceReview:
    """Required project sources and source-inventory findings for one project."""

    inventory: ProjectSourceInventoryInput
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernanceLintProjectPolicyResult:
    """Project policy outcome paired with the source records used to produce it."""

    project_id: str
    issues: tuple[str, ...]
    config_document: ProjectConfigDocument | None
    governance_record_review: GovernanceRecordReview | None
    source_review: GovernanceProjectSourceReview | None

    def __post_init__(self) -> None:
        if self.config_document is not None and self.config_document.project_id != self.project_id:
            raise ValueError("Project policy result and config document IDs must match")
        if self.config_document is None and (
            self.governance_record_review is not None or self.source_review is not None
        ):
            raise ValueError("Project source reviews require a captured project config")


def _configuration_issues(
    root: Path,
    entry: ProjectRegistryEntry,
    project_file: Path,
    config: ProjectConfig,
    toolchains: Mapping[str, ToolchainRecord],
) -> tuple[str, ...]:
    """Compare the validated project config with its manifest and catalog."""
    project = entry.record
    identifier = project.id
    issues: list[str] = []
    if config.project_id != project.id:
        issues.append(f"project {identifier}: config project_id must match registry id")
    if config.kind is not project.kind:
        issues.append(f"project {identifier}: config kind must match registry kind")
    # Discovery confines the manifest; the native design must remain in its island.
    if not project_file.is_relative_to(repo_path(root, project.config).parent):
        issues.append(f"project {identifier}: native project must belong to its manifest island")
    if config.project != project.project:
        issues.append(f"project {identifier}: config project path must match registry")
    if config.assurance_profile != project.assurance_profile:
        issues.append(f"project {identifier}: config assurance_profile must match registry")
    toolchain = toolchains.get(config.toolchain_id)
    if toolchain is None:
        issues.append(f"project {identifier}: config needs a declared toolchain_id")
    elif config.kicad_version != toolchain.kicad_version or config.image != toolchain.image:
        issues.append(
            f"project {identifier}: config toolchain must match declared toolchain {config.toolchain_id}"
        )
    return tuple(issues)


def _assurance_issues(entry: ProjectRegistryEntry, config: ProjectConfig) -> tuple[str, ...]:
    """Validate status and disabled-check policy for the authored assurance profile."""
    project = entry.record
    identifier = project.id
    issues: list[str] = []
    if project.assurance_profile == "training":
        if project.status != "training_fixture" or not config.not_for_manufacture:
            issues.append(
                f"project {identifier}: training profile must be a not_for_manufacture training_fixture"
            )
    elif project.assurance_profile == "development":
        if project.status != "engineering" or not config.not_for_manufacture:
            issues.append(f"project {identifier}: development must be unreleased engineering work")
        if (
            config.validation.expected_ignored_checks.erc
            or config.validation.expected_ignored_checks.drc
        ):
            issues.append(f"project {identifier}: development cannot disable ERC or DRC checks")
    elif project.assurance_profile == "production":
        if project.status not in {"engineering", "release_candidate"} or config.not_for_manufacture:
            issues.append(
                f"project {identifier}: production profile must be an engineering or release_candidate project"
            )
        if (
            config.validation.expected_ignored_checks.erc
            or config.validation.expected_ignored_checks.drc
        ):
            issues.append(
                f"project {identifier}: production profile cannot disable ERC or DRC checks"
            )
    return tuple(issues)


def _project_source_issues(
    root: Path,
    entry: ProjectRegistryEntry,
    project_file: Path,
    config: ProjectConfig,
) -> GovernanceProjectSourceReview:
    """Capture required source roots and compare expected native design files."""
    project = entry.record
    identifier = project.id
    inventory = capture_project_source_inventory(root, config.source_roots)
    issues = list(project_source_inventory_issues(identifier, inventory, config.required_inputs))
    schematic = project_file.with_suffix(".kicad_sch")
    pcb = project_file.with_suffix(".kicad_pcb")
    if project.kind is ProjectKind.PCB:
        if not schematic.is_file():
            issues.append(f"project {identifier}: schematic source is missing")
        elif schematic.relative_to(root).as_posix() not in config.required_inputs:
            issues.append(f"project {identifier}: schematic source is not inventoried")
        if not pcb.is_file():
            issues.append(f"project {identifier}: PCB source is missing")
        elif pcb.relative_to(root).as_posix() not in config.required_inputs:
            issues.append(f"project {identifier}: PCB source is not inventoried")
    elif project.kind is ProjectKind.PCB_ONLY:
        if schematic.exists():
            issues.append(
                f"project {identifier}: pcb_only must not contain a matching schematic source; use pcb instead"
            )
        if not pcb.is_file():
            issues.append(f"project {identifier}: PCB source is missing")
        elif pcb.relative_to(root).as_posix() not in config.required_inputs:
            issues.append(f"project {identifier}: PCB source is not inventoried")
    else:
        if not schematic.is_file():
            issues.append(f"project {identifier}: schematic source is missing")
        elif schematic.relative_to(root).as_posix() not in config.required_inputs:
            issues.append(f"project {identifier}: schematic source is not inventoried")
        if pcb.exists():
            issues.append(
                f"project {identifier}: {project.kind.value} project must not contain a PCB source"
            )
    return GovernanceProjectSourceReview(inventory=inventory, issues=tuple(issues))


def _component_identity_issues(
    entry: ProjectRegistryEntry,
    config: ProjectConfig,
) -> tuple[str, ...]:
    """Compare the manifest's component identity contract with project config."""
    project = entry.record
    identifier = project.id
    identity = project.component_identity
    issues: list[str] = []
    if project.kind is ProjectKind.PCB_ONLY and identity.required:
        issues.append(
            f"project {identifier}: pcb_only cannot require component identity without an authoritative schematic"
        )
    if (
        project.assurance_profile == "production"
        and project.kind in {ProjectKind.PCB, ProjectKind.SCHEMATIC}
        and not identity.required
    ):
        issues.append(f"project {identifier}: production profile must require component identity")
    if identity.required and not identity.part_ids:
        issues.append(
            f"project {identifier}: component identity is required but no part ids are declared"
        )
    validation = config.validation
    components = None
    if validation.kind is ProjectKind.PCB or validation.kind is ProjectKind.SCHEMATIC:
        components = validation.components
    if identity.required and components is not None:
        expected_ids = {component.part_id for component in components.values()}
        if None in expected_ids or expected_ids != set(identity.part_ids):
            issues.append(
                f"project {identifier}: component contracts must bind each reference to its declared part_id"
            )
    return tuple(issues)


def _catalog_reference_issues(
    entry: ProjectRegistryEntry,
    shared_inputs: GovernanceLintSharedInputs,
) -> tuple[str, ...]:
    """Validate project part, interface, library, and shared-root references."""
    project = entry.record
    identifier = project.id
    parts = shared_inputs.parts_catalog.lookup.by_id
    interfaces = shared_inputs.interfaces_catalog.lookup.by_id
    libraries = shared_inputs.libraries_catalog.lookup.by_id
    issues: list[str] = []
    for part_id in project.component_identity.part_ids:
        part = parts.get(part_id)
        if part is None:
            issues.append(f"project {identifier}: unknown approved part {part_id!r}")
            continue
        if project.assurance_profile == "production":
            for field, value in (
                ("manufacturer", part.manufacturer),
                ("description", part.description),
                ("part_class", part.part_class),
                ("mpn", part.mpn),
                ("datasheet_url", part.datasheet_url),
                ("lifecycle", part.lifecycle),
            ):
                if not reviewed_value(value):
                    issues.append(
                        f"project {identifier}: production part {part_id} needs reviewed {field}"
                    )
            if part.status is not PartStatus.APPROVED:
                issues.append(
                    f"project {identifier}: production part {part_id} must have status approved"
                )
    for interface_id in project.interfaces:
        if interface_id not in interfaces:
            issues.append(f"project {identifier}: unknown interface {interface_id!r}")
    for library_id in project.library_ids:
        library = libraries.get(library_id)
        if library is None:
            issues.append(f"project {identifier}: unknown library {library_id!r}")
        elif project.assurance_profile == "production" and library.status != "approved":
            issues.append(
                f"project {identifier}: production library {library_id} must have status approved"
            )
    expected_shared_roots = {
        libraries[library_id].path for library_id in project.library_ids if library_id in libraries
    }
    authored_shared_roots = set(entry.manifest.shared_source_roots)
    if authored_shared_roots != expected_shared_roots:
        issues.append(
            f"project {identifier}: shared_source_roots must match library_ids catalog paths: "
            f"{sorted(authored_shared_roots ^ expected_shared_roots)}"
        )
    return tuple(issues)


def evaluate_governance_lint_project_policy(
    request: GovernanceLintProjectPolicyRequest,
) -> GovernanceLintProjectPolicyResult:
    """Evaluate one project and retain every source record needed for freshness."""
    root = request.root.resolve()
    entry = request.entry
    shared_inputs = request.shared_inputs
    project = entry.record
    identifier = project.id
    issues: list[str] = []
    if len({tag.casefold() for tag in project.tags}) != len(project.tags):
        issues.append(f"project {identifier}: duplicate metadata tag")
    try:
        project_file = repo_path(root, project.project)
        if not project_file.is_file():
            issues.append(f"project {identifier}: project file is missing")
        config_document = load_project_config_document_from_snapshot(
            root, entry, shared_inputs.toolchains_document.value
        )
    except (OSError, ValueError) as exc:
        issues.append(f"project {identifier}: invalid project/configuration: {exc}")
        return GovernanceLintProjectPolicyResult(
            project_id=identifier,
            issues=tuple(issues),
            config_document=None,
            governance_record_review=None,
            source_review=None,
        )

    config = config_document.value
    issues.extend(
        f"project {identifier}: electrical: {issue}"
        for issue in electrical_policy_issues(root, config)
    )
    toolchains = shared_inputs.toolchains_catalog.lookup.by_id
    issues.extend(_configuration_issues(root, entry, project_file, config, toolchains))
    issues.extend(_assurance_issues(entry, config))

    governance_review = None
    if project.assurance_profile == "production":
        governance_review = review_governance_record(
            root,
            shared_inputs.team_policy,
            project.governance_record,
            identifier,
        )
        issues.extend(governance_review.issues)

    if project.kind is ProjectKind.PCB_ONLY and (
        project.assurance_profile == "production" or not config.not_for_manufacture
    ):
        issues.append(
            f"project {identifier}: pcb_only must remain not_for_manufacture with a training or development profile"
        )

    source_review = _project_source_issues(root, entry, project_file, config)
    issues.extend(source_review.issues)
    issues.extend(_component_identity_issues(entry, config))
    issues.extend(_catalog_reference_issues(entry, shared_inputs))
    return GovernanceLintProjectPolicyResult(
        project_id=identifier,
        issues=tuple(issues),
        config_document=config_document,
        governance_record_review=governance_review,
        source_review=source_review,
    )
