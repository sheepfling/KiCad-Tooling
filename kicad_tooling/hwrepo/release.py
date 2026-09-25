"""Typed, read-only release-readiness validation; it never creates a release."""
from __future__ import annotations

import csv
import hashlib
import subprocess
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .evidence import source_state, verify_native, verify_release_portable
from .models import (
    Assurance,
    DeviationStatus,
    GovernanceRecord,
    HarnessInterfaceValidationContract,
    InterfacesCatalog,
    LibrariesCatalog,
    PolicyIssue,
    ProductIndex,
    ProductRecord,
    ProjectKind,
    ProjectRecord,
    ReleaseArtifactKind,
    ReleaseAssurancePolicy,
    ReleaseClass,
    ReleaseManifest,
    ReleasePoliciesCatalog,
    ReleaseReadinessReport,
    ReleaseStatus,
    ReleaseVariant,
    SystemWiringValidationContract,
    TeamPolicy,
    ToolchainsCatalog,
)
from .product import ProductRepository, excluded, load_repository, occurrences

MATURITY_ORDER = {
    "training": 0,
    "engineering_review": 1,
    "prototype": 2,
    "pilot": 3,
    "production": 4,
}
RELEASE_MATURITY = {
    ReleaseClass.ENGINEERING_REVIEW: "engineering_review",
    ReleaseClass.PROTOTYPE: "prototype",
    ReleaseClass.PILOT: "pilot",
    ReleaseClass.PRODUCTION: "production",
}
REQUIRED_ARTIFACT_KINDS = {
    ReleaseClass.ENGINEERING_REVIEW: frozenset({ReleaseArtifactKind.REVIEW_RECORD}),
    ReleaseClass.PROTOTYPE: frozenset(
        {
            ReleaseArtifactKind.BOM,
            ReleaseArtifactKind.SCHEMATIC_EXPORT,
            ReleaseArtifactKind.PCB_EXPORT,
            ReleaseArtifactKind.VALIDATION_REPORT,
        }
    ),
    ReleaseClass.PILOT: frozenset(
        {
            ReleaseArtifactKind.BOM,
            ReleaseArtifactKind.SCHEMATIC_EXPORT,
            ReleaseArtifactKind.PCB_EXPORT,
            ReleaseArtifactKind.VALIDATION_REPORT,
        }
    ),
    ReleaseClass.PRODUCTION: frozenset(
        {
            ReleaseArtifactKind.BOM,
            ReleaseArtifactKind.SCHEMATIC_EXPORT,
            ReleaseArtifactKind.PCB_EXPORT,
            ReleaseArtifactKind.VALIDATION_REPORT,
            ReleaseArtifactKind.FABRICATION_PACKAGE,
            ReleaseArtifactKind.ASSEMBLY_PACKAGE,
        }
    ),
}
ASSURANCE_ORDER = {
    Assurance.NOT_APPLICABLE: -1,
    Assurance.UNKNOWN: 0,
    Assurance.ASSUMED: 1,
    Assurance.INFERRED: 2,
    Assurance.OBSERVED: 3,
    Assurance.MANUFACTURER_DOCUMENTED: 4,
    Assurance.VERIFIED: 5,
}


def git(root: Path, *args: str) -> str:
    """Read one Git fact without altering the worktree, index, refs or remotes."""
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def issue(code: str, location: str, message: str) -> PolicyIssue:
    """Create a concise, typed release-readiness finding."""
    return PolicyIssue(code=code, location=location, message=message)


def load_release_repository(root: Path, manifest: ReleaseManifest) -> ProductRepository:
    """Load only projects selected explicitly or through release variants.

    Relevant product records and their board/view contracts are still loaded by
    the scoped product repository. An unrelated legacy island is not a release
    dependency merely because it appears in the project registry.
    """
    index = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
    indexed = {product.id: product for product in index.products}
    if len(indexed) != len(index.products):
        raise ValueError("Product index has duplicate IDs")
    selected = set(manifest.projects)
    for variant in manifest.variants:
        product = indexed.get(variant.product)
        if product is not None:
            selected.update(product.project_ids)
    relevant_products = {
        entry.id for entry in index.products
        if not selected.isdisjoint(entry.project_ids)
    } | {variant.product for variant in manifest.variants}
    # Product-view projects name their product in the authored test contract.
    # Read that metadata before narrowing to indexed IDs: otherwise a missing
    # index membership would silently omit its view from release evidence.
    for project in load_registry(root).projects:
        if project.kind not in {ProjectKind.SYSTEM_WIRING, ProjectKind.HARNESS_INTERFACE}:
            continue
        validation = load_config(root, project.config).validation
        if not isinstance(validation, (SystemWiringValidationContract,
                                       HarnessInterfaceValidationContract)):
            raise TypeError(f"{project.config}: product-view validation contract is missing")
        entry = indexed.get(validation.product_id)
        if validation.product_id in relevant_products and (
            entry is None or project.id not in entry.project_ids
        ):
            raise ValueError(
                f"catalog/products.json: product {validation.product_id} omits "
                f"product-view project {project.id} declared by {project.config}"
            )
    return load_repository(root, tuple(sorted(selected)))


def selected_products(
    repository: ProductRepository, manifest: ReleaseManifest, issues: list[PolicyIssue]
) -> tuple[ProductRecord, ...]:
    """Resolve every explicit product/variant selection once and fail unknown values."""
    products = {product.id: product for product in repository.products}
    selected: dict[str, ProductRecord] = {}
    seen: set[tuple[str, str]] = set()
    for selection in manifest.variants:
        key = (selection.product, selection.variant)
        if key in seen:
            issues.append(issue("RELEASE_VARIANT", selection.product, "Duplicate product/variant selection"))
            continue
        seen.add(key)
        product = products.get(selection.product)
        if product is None:
            issues.append(issue("RELEASE_PRODUCT", selection.product, "Unknown product"))
            continue
        if selection.variant not in {variant.id for variant in product.variants}:
            issues.append(
                issue("RELEASE_VARIANT", selection.product, f"Unknown variant {selection.variant}")
            )
            continue
        variant = next(variant for variant in product.variants if variant.id == selection.variant)
        if selection.product_revision != product.revision:
            issues.append(
                issue("RELEASE_PRODUCT_REVISION", selection.product, "Product revision does not match")
            )
        if selection.variant_revision != variant.revision:
            issues.append(
                issue("RELEASE_VARIANT_REVISION", selection.variant, "Variant revision does not match")
            )
        selected[product.id] = product
    if not manifest.variants and not manifest.projects:
        issues.append(issue("RELEASE_SELECTION", "projects", "Select a project or product/variant"))
    return tuple(selected[identifier] for identifier in sorted(selected))


def product_scope(product: ProductRecord) -> frozenset[str]:
    """Return the stable IDs a release deviation may explicitly affect."""
    return frozenset(
        (
            product.id,
            *(assembly.id for assembly in product.assemblies),
            *(terminal.id for terminal in product.terminals),
            *(connection.id for connection in product.connections),
            *(harness.id for harness in product.harnesses),
            *(handoff.id for handoff in product.mechanical),
            *(variant.id for variant in product.variants),
        )
    )


def selected_project_records(
    repository: ProductRepository, products: Iterable[ProductRecord], explicit: tuple[str, ...] = ()
) -> tuple[ProjectRecord, ...]:
    """Resolve controlled KiCad projects used by the selected product definitions."""
    projects: dict[str, ProjectRecord] = {}
    if len(set(explicit)) != len(explicit):
        raise ValueError("Duplicate standalone project selection")
    for identifier in explicit:
        if identifier not in repository.projects:
            raise ValueError(f"Unknown project {identifier}")
        projects[identifier] = repository.projects[identifier]
    for product in products:
        project_ids = repository.product_project_ids.get(product.id)
        if project_ids is None:
            raise ValueError(f"Selected product has no declared project scope: {product.id}")
        for project_id in project_ids:
            project = repository.projects.get(project_id)
            if project is None:
                raise ValueError(f"Selected product uses unknown project {project_id}")
            projects[project.id] = project
    return tuple(projects[identifier] for identifier in sorted(projects))


def selected_board_variants(
    products: Iterable[ProductRecord], selections: tuple[ReleaseVariant, ...],
    project_ids: Iterable[str],
) -> dict[str, str]:
    """Resolve reviewed product-to-KiCad population mappings without ambiguity."""
    indexed = {product.id: product for product in products}
    allowed = set(project_ids)
    result: dict[str, str] = {}
    for selection in selections:
        product = indexed.get(selection.product)
        if product is None:
            continue  # selected_products already reports an unknown product.
        variant = next((item for item in product.variants if item.id == selection.variant), None)
        if variant is None:
            continue  # selected_products already reports an unknown variant.
        for project_id, name in variant.board_variants.items():
            if project_id not in allowed:
                raise ValueError(f"{selection.product}:{selection.variant} maps unselected board {project_id}")
            if project_id in result and result[project_id] != name:
                raise ValueError(f"Conflicting KiCad assembly variants for {project_id}: "
                                 f"{result[project_id]} and {name}; prepare separate candidates")
            result[project_id] = name
    return result


def expected_board_population(product: ProductRecord, variant_id: str,
                              project_id: str) -> dict[str, str] | None:
    """Resolve the fitted reference/part identities for every included board occurrence."""
    variant = next((item for item in product.variants if item.id == variant_id), None)
    if variant is None:
        raise ValueError(f"Unknown product variant {product.id}:{variant_id}")
    board_assemblies = {assembly.id: assembly for assembly in product.assemblies
                        if assembly.project_id == project_id}
    populations: list[dict[str, str]] = []
    for path, occurrence in occurrences(product).items():
        assembly = board_assemblies.get(occurrence.item)
        if assembly is None or excluded(path, variant):
            continue
        population: dict[str, str] = {}
        for member in assembly.members:
            if not excluded(f"{path}.{member.ref}", variant):
                population[member.ref] = member.item
        populations.append(population)
    if not populations:
        return None
    if any(population != populations[0] for population in populations[1:]):
        raise ValueError(f"Product {product.id}:{variant_id} uses different populations of "
                         f"board {project_id}; prepare separate board variants")
    return populations[0]


def verify_board_population(products: Iterable[ProductRecord],
                            selections: tuple[ReleaseVariant, ...],
                            project_id: str, bom_path: Path) -> None:
    """Native fitted BOM must agree with each selected product's part identities."""
    selected = {product.id: product for product in products}
    expectations: list[tuple[str, dict[str, str]]] = []
    for choice in selections:
        product = selected.get(choice.product)
        if product is None:
            continue
        expected = expected_board_population(product, choice.variant, project_id)
        if expected is not None:
            expectations.append((f"{choice.product}:{choice.variant}", expected))
    if not expectations:
        return
    with bom_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["Reference", "Value", "Footprint", "PartID", "DNP"]:
            raise ValueError(f"{bom_path}: unexpected native BOM columns")
        actual: dict[str, str] = {}
        for row in reader:
            reference, part_id = row["Reference"], row["PartID"]
            if not reference or not part_id or reference in actual:
                raise ValueError(f"{bom_path}: duplicate or incomplete BOM reference {reference!r}")
            actual[reference] = part_id
    for label, expected in expectations:
        if actual != expected:
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            changed = sorted(ref for ref in actual.keys() & expected.keys()
                             if actual[ref] != expected[ref])
            raise ValueError(f"{project_id} native KiCad BOM differs from {label} product population: "
                             f"missing={missing}, extra={extra}, changed_part_ids={changed}. "
                             "Review product exclusions, KiCad DNP/variant overrides and PART_ID fields")


def configured_toolchains(root: Path, projects: Iterable[ProjectRecord]) -> frozenset[str]:
    """Resolve declared toolchain identities used by selected KiCad projects."""
    registry = load_registry(root)
    toolchains = read_model(repo_path(root, registry.catalogs.toolchains), ToolchainsCatalog)
    known = {record.id for record in toolchains.toolchains}
    used: set[str] = set()
    for project in projects:
        config = load_config(root, project.config)
        if config.toolchain_id not in known:
            raise ValueError(f"Project has unknown toolchain {config.toolchain_id}")
        used.add(config.toolchain_id)
    return frozenset(used)


def validate_dependencies(
    root: Path,
    projects: Iterable[ProjectRecord],
    manifest: ReleaseManifest,
    findings: list[PolicyIssue],
) -> None:
    """Bind release records to every selected shared-library/interface revision."""
    registry = load_registry(root)
    libraries = {
        record.id: record
        for record in read_model(
            repo_path(root, registry.catalogs.libraries), LibrariesCatalog
        ).libraries
    }
    interfaces = {
        record.id: record
        for record in read_model(
            repo_path(root, registry.catalogs.interfaces), InterfacesCatalog
        ).interfaces
    }
    expected_libraries = {library_id for project in projects for library_id in project.library_ids}
    expected_interfaces = {
        interface_id for project in projects for interface_id in project.interfaces
    }
    release_libraries = {record.id: record for record in manifest.libraries}
    release_interfaces = {record.id: record for record in manifest.interfaces}
    if len(release_libraries) != len(manifest.libraries):
        findings.append(issue("RELEASE_LIBRARY", "libraries", "Duplicate library identity"))
    if len(release_interfaces) != len(manifest.interfaces):
        findings.append(issue("RELEASE_INTERFACE", "interfaces", "Duplicate interface identity"))
    if set(release_libraries) != expected_libraries:
        findings.append(
            issue("RELEASE_LIBRARY", "libraries", "Manifest libraries differ from selected projects")
        )
    if set(release_interfaces) != expected_interfaces:
        findings.append(
            issue("RELEASE_INTERFACE", "interfaces", "Manifest interfaces differ from selected projects")
        )
    for identifier in sorted(expected_libraries):
        catalog = libraries.get(identifier)
        selected = release_libraries.get(identifier)
        if catalog is None or selected is None:
            continue
        if (
            selected.version != catalog.version
            or selected.provenance_sha256 != catalog.provenance_sha256
            or selected.licensing_sha256 != catalog.licensing_sha256
        ):
            findings.append(
                issue("RELEASE_LIBRARY", identifier, "Library version or evidence hash does not match")
            )
    for identifier in sorted(expected_interfaces):
        catalog = interfaces.get(identifier)
        selected = release_interfaces.get(identifier)
        if catalog is None or selected is None:
            continue
        if selected.revision != catalog.revision:
            findings.append(
                issue("RELEASE_INTERFACE", identifier, "Interface revision does not match")
            )


def assurance_policy(root: Path, release_class: ReleaseClass) -> ReleaseAssurancePolicy:
    """Load one explicit assurance floor for the selected release maturity."""
    registry = load_registry(root)
    policies = read_model(
        repo_path(root, registry.catalogs.release_policies), ReleasePoliciesCatalog
    ).policies
    matching = tuple(policy for policy in policies if policy.release_class is release_class)
    if len(matching) != 1:
        raise ValueError(f"Need exactly one assurance policy for {release_class.value}")
    return matching[0]


def validate_assurance(
    products: Iterable[ProductRecord],
    policy: ReleaseAssurancePolicy,
    findings: list[PolicyIssue],
) -> None:
    """Require every retained semantic claim to meet the maturity-specific floor."""
    required = ASSURANCE_ORDER[policy.minimum_assurance]
    for product in products:
        claims = (*product.connections, *product.harnesses, *product.mechanical)
        for claim in claims:
            if ASSURANCE_ORDER[claim.assurance] < required:
                findings.append(
                    issue(
                        "RELEASE_ASSURANCE",
                        claim.id,
                        f"{policy.release_class.value} requires at least "
                        f"{policy.minimum_assurance.value}",
                    )
                )


def check(root: Path, manifest: ReleaseManifest, today: date | None = None) -> ReleaseReadinessReport:
    """Validate candidate release closure without authorizing build, tag or publication."""
    resolved_root = root.resolve()
    findings: list[PolicyIssue] = []
    try:
        repository = load_release_repository(resolved_root, manifest)
    except (OSError, TypeError, ValueError) as exc:
        findings.append(issue("RELEASE_DEPENDENCY", "products", str(exc)))
        repository = load_repository(resolved_root, ())
    findings.extend(repository.issues)
    products = selected_products(repository, manifest, findings)
    try:
        projects = selected_project_records(repository, products, manifest.projects)
        validate_dependencies(resolved_root, projects, manifest, findings)
    except (OSError, ValueError) as exc:
        findings.append(issue("RELEASE_DEPENDENCY", "projects", str(exc)))
        projects = ()
    try:
        head = git(resolved_root, "rev-parse", "HEAD")
        if head != manifest.source_commit:
            findings.append(issue("RELEASE_COMMIT", "source_commit", "Manifest does not name HEAD"))
        if git(resolved_root, "status", "--porcelain=v1", "--untracked-files=all"):
            findings.append(issue("RELEASE_DIRTY", "repository", "Release candidate requires a clean worktree"))
    except (OSError, subprocess.SubprocessError) as exc:
        findings.append(issue("RELEASE_GIT", "repository", str(exc)))

    required_maturity = RELEASE_MATURITY[manifest.release_class]
    for project in projects:
        if project.kind is ProjectKind.PCB_ONLY and manifest.release_class is not ReleaseClass.ENGINEERING_REVIEW:
            findings.append(
                issue(
                    "RELEASE_PROJECT_KIND",
                    project.id,
                    "pcb_only has no authoritative schematic and is limited to engineering review",
                )
            )
        if manifest.release_class is not ReleaseClass.ENGINEERING_REVIEW and (
            project.assurance_profile != "production" or project.status != "release_candidate"
        ):
            findings.append(issue("RELEASE_PROJECT_MATURITY", project.id,
                                  "Build releases require production-profile release_candidate projects"))
    try:
        validate_assurance(products, assurance_policy(resolved_root, manifest.release_class), findings)
    except (OSError, ValueError) as exc:
        findings.append(issue("RELEASE_ASSURANCE_POLICY", "release_policies", str(exc)))
    for product in products:
        if MATURITY_ORDER[product.maturity] < MATURITY_ORDER[required_maturity]:
            findings.append(
                issue(
                    "RELEASE_MATURITY",
                    product.id,
                    f"{manifest.release_class.value} requires at least {required_maturity}",
                )
            )
        if manifest.release_class is not ReleaseClass.ENGINEERING_REVIEW and (
            product.blocking_issues or any(handoff.open_items for handoff in product.mechanical)
        ):
            findings.append(
                issue("RELEASE_BLOCKER", product.id, "Blocking product or mechanical items remain"))

    try:
        used_toolchains = configured_toolchains(resolved_root, projects)
        if manifest.toolchain_id not in used_toolchains or len(used_toolchains) != 1:
            findings.append(
                issue(
                    "RELEASE_TOOLCHAIN",
                    "toolchain_id",
                    "Manifest must match exactly one selected project toolchain",
                )
            )
    except (OSError, ValueError) as exc:
        findings.append(issue("RELEASE_TOOLCHAIN", "toolchain_id", str(exc)))

    try:
        if manifest.evidence is None:
            raise ValueError("Retained portable and native reports are required; PASS labels are insufficient")
        source = source_state(resolved_root)
        if source.commit != manifest.source_commit or not source.clean:
            raise ValueError("Release evidence requires the clean source commit checked out")
        verify_release_portable(
            resolved_root, manifest.evidence.portable, source,
            tuple(project.id for project in projects),
        )
        if set(manifest.evidence.native) != {project.id for project in projects}:
            raise ValueError("Native evidence must cover exactly the selected projects")
        for project in projects:
            verify_native(resolved_root, manifest.evidence.native[project.id], source, project.id)
        from .exports import verify_exports

        if not set(manifest.evidence.exports) <= {project.id for project in projects}:
            raise ValueError("Export evidence names an unselected project")
        board_variants = selected_board_variants(products, manifest.variants,
                                                 (project.id for project in projects))
        for project in projects:
            exported = manifest.evidence.exports.get(project.id)
            if exported is not None:
                verify_exports(resolved_root, exported, source, project.id, project.config,
                               board_variants.get(project.id))
                verify_board_population(products, manifest.variants, project.id,
                                        repo_path(resolved_root, exported.path).parent / "assembly/bom.csv")
            elif project.id in board_variants:
                raise ValueError(f"{project.id} KiCad assembly variant has no native export evidence")
            elif project.kind is ProjectKind.PCB and manifest.release_class is ReleaseClass.PRODUCTION:
                raise ValueError(f"Production board {project.id} requires native fabrication and assembly exports")
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        findings.append(issue("RELEASE_EVIDENCE", "evidence", str(exc)))

    artifact_ids: set[str] = set()
    artifact_kinds: set[ReleaseArtifactKind] = set()
    for artifact in manifest.artifacts:
        if artifact.id in artifact_ids:
            findings.append(issue("RELEASE_ARTIFACT", artifact.id, "Duplicate artifact identity"))
        artifact_ids.add(artifact.id)
        artifact_kinds.add(artifact.kind)
        try:
            path = repo_path(resolved_root, artifact.path)
            if not path.is_file():
                raise ValueError("missing artifact")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != artifact.sha256:
                raise ValueError("SHA-256 does not match")
        except (OSError, ValueError) as exc:
            findings.append(issue("RELEASE_ARTIFACT", artifact.path, str(exc)))
    if not manifest.artifacts:
        findings.append(issue("RELEASE_ARTIFACT", "artifacts", "At least one retained artifact is required"))
    required_artifact_kinds = set(REQUIRED_ARTIFACT_KINDS[manifest.release_class])
    if not any(project.kind is ProjectKind.PCB for project in projects):
        required_artifact_kinds -= {ReleaseArtifactKind.PCB_EXPORT, ReleaseArtifactKind.BOM,
                                   ReleaseArtifactKind.FABRICATION_PACKAGE, ReleaseArtifactKind.ASSEMBLY_PACKAGE}
    if manifest.release_class in {ReleaseClass.PILOT, ReleaseClass.PRODUCTION} and any(
        product.harnesses for product in products
    ):
        required_artifact_kinds.add(ReleaseArtifactKind.HARNESS_EXPORT)
    missing_artifact_kinds = sorted(
        kind.value for kind in required_artifact_kinds - artifact_kinds
    )
    if missing_artifact_kinds:
        findings.append(
            issue(
                "RELEASE_ARTIFACT_KIND",
                "artifacts",
                f"Required artifact kinds missing: {missing_artifact_kinds}",
            )
        )

    scope = frozenset((*[project.id for project in projects],
                       *[identifier for product in products for identifier in product_scope(product)]))
    evidence = frozenset(
        (*artifact_ids, *(record.id for product in products for record in product.evidence))
    )
    effective_today = today or datetime.now(UTC).date()
    seen_deviations: set[str] = set()
    for deviation in manifest.deviations:
        if deviation.id in seen_deviations:
            findings.append(issue("DEVIATION_ID", deviation.id, "Duplicate deviation identity"))
        seen_deviations.add(deviation.id)
        if not deviation.scope or any(identifier not in scope for identifier in deviation.scope):
            findings.append(issue("DEVIATION_SCOPE", deviation.id, "Scope must name selected release IDs"))
        if deviation.status is not DeviationStatus.APPROVED:
            findings.append(issue("DEVIATION_STATUS", deviation.id, "Release deviation must be approved"))
        if deviation.expires < effective_today:
            findings.append(issue("DEVIATION_EXPIRY", deviation.id, "Release deviation has expired"))
        if not deviation.evidence or any(identifier not in evidence for identifier in deviation.evidence):
            findings.append(issue("DEVIATION_EVIDENCE", deviation.id, "Deviation needs scoped evidence"))

    requires_approval = manifest.release_class is not ReleaseClass.ENGINEERING_REVIEW
    if requires_approval and manifest.status is not ReleaseStatus.APPROVED:
        findings.append(issue("RELEASE_STATUS", "status", "Non-review releases must be approved"))
    if requires_approval and manifest.approval is None:
        findings.append(issue("RELEASE_APPROVAL", "approval", "Approval record is required"))
    if manifest.approval is not None:
        approval = manifest.approval
        if not approval.evidence or not set(approval.evidence) <= artifact_ids:
            findings.append(issue("RELEASE_APPROVAL", "approval", "Approval must reference retained artifacts"))
        if approval.approved_at > effective_today:
            findings.append(issue("RELEASE_APPROVAL", "approval", "Approval date is in the future"))
        try:
            policy = read_model(root / "catalog/team-policy.json", TeamPolicy)
            actors = {actor.casefold() for actor in (approval.electrical_reviewer,
                      approval.mechanical_reviewer, approval.integrator, approval.release_authority) if actor is not None}
            if len(actors) < policy.minimum_actors:
                findings.append(issue("RELEASE_APPROVAL", "approval", "Approval does not meet team actor policy"))
            if requires_approval:
                if approval.release_authority is None:
                    findings.append(issue("RELEASE_APPROVAL", "approval", "Named release authority is required"))
                for project in projects:
                    if project.kind is ProjectKind.PCB and approval.mechanical_reviewer is None:
                        findings.append(issue("RELEASE_APPROVAL", project.id, "PCB release requires mechanical review"))
                    if project.governance_record is None:
                        findings.append(issue("RELEASE_APPROVAL", project.id, "Governance assignment is missing"))
                        continue
                    governance = read_model(repo_path(root, project.governance_record), GovernanceRecord)
                    for actor, allowed, role in (
                        (approval.electrical_reviewer, governance.reviewers, "electrical reviewer"),
                        (approval.mechanical_reviewer, governance.reviewers, "mechanical reviewer"),
                        (approval.integrator, governance.integrators, "integrator"),
                        (approval.release_authority, governance.release_authorities, "release authority"),
                    ):
                        if actor is not None and actor.casefold() not in {name.casefold() for name in allowed}:
                            findings.append(issue("RELEASE_APPROVAL", project.id, f"Unassigned {role}: {actor}"))
        except (OSError, ValueError) as exc:
            findings.append(issue("RELEASE_APPROVAL", "approval", str(exc)))
    if requires_approval and manifest.source_tag is None:
        findings.append(issue("RELEASE_TAG", "source_tag", "Annotated tag is required"))
    if manifest.source_tag is not None:
        try:
            tag_ref = f"refs/tags/{manifest.source_tag}"
            git(resolved_root, "check-ref-format", tag_ref)
            if git(resolved_root, "cat-file", "-t", tag_ref) != "tag":
                findings.append(issue("RELEASE_TAG", "source_tag", "Tag must be annotated"))
            if git(resolved_root, "rev-parse", f"{tag_ref}^{{}}") != manifest.source_commit:
                findings.append(issue("RELEASE_TAG", "source_tag", "Tag does not resolve to source_commit"))
        except (OSError, subprocess.SubprocessError) as exc:
            findings.append(issue("RELEASE_TAG", "source_tag", str(exc)))

    return ReleaseReadinessReport(
        release_id=manifest.release_id,
        release_class=manifest.release_class,
        status="FAIL" if findings else "PASS",
        issues=tuple(findings),
    )
