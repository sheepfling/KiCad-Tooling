"""Resolve changed repository paths into a conservative project check scope."""
from __future__ import annotations

from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_registry
from .models import ImpactPlan, LibrariesCatalog, ProductIndex, ProductRecord, ProjectManifest

# These authored root documents affect the workflow's policy or agent behavior.
POLICY_MARKDOWN = frozenset({"AGENTS.md", "CLAUDE.md", "LICENSE.md"})
GLOBAL_PREFIXES = ("tools/", "tests/", "catalog/", ".github/")
DOCUMENTATION_ROOT_FILES = frozenset({"README.md", "generated/README.md", "schemas/README.md"})


def _within(path: str, directory: str) -> bool:
    """Match a path component boundary, not a similarly named sibling."""
    return path == directory or path.startswith(f"{directory}/")


def _local_references(manifest: ProjectManifest) -> tuple[str, ...]:
    references = [*manifest.required_inputs, manifest.project, manifest.checks]
    if manifest.mechanical_handoff is not None:
        references.append(manifest.mechanical_handoff)
    if manifest.governance_record is not None:
        references.append(manifest.governance_record)
    return tuple(references)


def _local_path(project_directory: str, relative: str) -> str:
    """Name a manifest's project-local input in repository coordinates."""
    return f"{project_directory}/{relative}"


def _full(
    all_ids: tuple[str, ...], paths: tuple[str, ...], reasons: set[str], docs_changed: bool
) -> ImpactPlan:
    return ImpactPlan(
        scope="full", projects=all_ids, changed_paths=paths,
        reasons=tuple(sorted(reasons)), docs_changed=docs_changed,
    )


def plan_paths(root: Path, changed_paths: tuple[str, ...]) -> ImpactPlan:
    """Plan focused checks only when every changed path has a known owner.

    The caller supplies Git's repository-relative changed path names, including
    deleted names. This function neither invokes Git nor trusts file existence.
    Malformed inputs, undeclared owners and shared policy changes select all
    projects. Invalid registry/manifest data raises, so CI cannot silently skip.
    """
    root = root.resolve()
    registry = load_registry(root)
    catalog_paths = {
        registry.catalogs.parts,
        registry.catalogs.interfaces,
        registry.catalogs.libraries,
        registry.catalogs.toolchains,
        registry.catalogs.release_policies,
        "catalog/projects.json",
        "catalog/products.json",
    }
    all_ids = tuple(project.id for project in registry.projects)
    paths = tuple(sorted(set(changed_paths)))
    if not paths:
        return _full(all_ids, paths, {"No changed paths supplied; run full scope"}, False)

    docs_changed = any(path.lower().endswith(".md") for path in paths)
    for path in paths:
        try:
            repo_path(root, path)
        except (OSError, ValueError):
            return _full(
                all_ids, paths, {f"Unsafe or nonportable changed path: {path!r}"}, docs_changed
            )

    products = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
    libraries = read_model(repo_path(root, registry.catalogs.libraries), LibrariesCatalog)
    manifests: dict[str, ProjectManifest] = {
        project.id: read_model(repo_path(root, project.config), ProjectManifest)
        for project in registry.projects
    }
    product_dependencies: dict[str, set[str]] = {}
    for product in products.products:
        record = read_model(repo_path(root, product.path), ProductRecord)
        product_dependencies[product.id] = {
            *(evidence.path for evidence in record.evidence),
            *(handoff.drawing for handoff in record.mechanical),
        }
    library_metadata_owners: dict[str, set[str]] = {}
    for library in libraries.libraries:
        owners = {
            project.id
            for project in registry.projects
            if library.id in manifests[project.id].library_ids
        }
        for metadata_path in (library.provenance_path, library.licensing_path):
            library_metadata_owners.setdefault(metadata_path, set()).update(owners)
    known_ids = set(all_ids)
    selected: set[str] = set()
    reasons: set[str] = set()
    full_reasons: set[str] = set()
    for path in paths:
        consumers = {
            project.id
            for project in registry.projects
            if path in manifests[project.id].shared_inputs
            or any(_within(path, shared_root)
                   for shared_root in manifests[project.id].shared_source_roots)
        }
        if consumers:
            selected.update(consumers)
            reasons.add(f"Shared dependency {path} affects {', '.join(sorted(consumers))}")

        if path in POLICY_MARKDOWN or path in catalog_paths or path.startswith(GLOBAL_PREFIXES):
            full_reasons.add(f"Shared workflow or policy path changed: {path}")
            continue

        library_owners = library_metadata_owners.get(path)
        if library_owners is not None:
            if not library_owners:
                full_reasons.add(f"Unconsumed library metadata changed: {path}")
                continue
            selected.update(library_owners)
            reasons.add(f"Library metadata {path} affects {', '.join(sorted(library_owners))}")

        project_owners = {
            project.id for project in registry.projects
            if _within(path, Path(project.config).parent.as_posix())
        }
        source_owners = {
            project.id
            for project in registry.projects
            if path in {
                _local_path(Path(project.config).parent.as_posix(), relative)
                for relative in _local_references(manifests[project.id])
            }
            or any(
                _within(path, _local_path(Path(project.config).parent.as_posix(), source_root))
                for source_root in manifests[project.id].source_roots
            )
        }
        product_owners = {
            project_id
            for product in products.products
            if _within(path, Path(product.path).parent.as_posix())
            for project_id in product.project_ids
        }
        product_source_owners = {
            project_id
            for product in products.products
            if path in product_dependencies[product.id]
            for project_id in product.project_ids
        }
        if (product_owners | product_source_owners) - known_ids:
            full_reasons.add(f"Product path has undeclared project membership: {path}")
            continue
        # Only known documentation namespaces get the lightweight docs lane.
        # Declared local/shared Markdown inputs are source, so they stay focused.
        if path.lower().endswith(".md") and not (
            consumers or source_owners or product_source_owners or library_owners
        ):
            if (
                path in DOCUMENTATION_ROOT_FILES
                or path.startswith("docs/")
                or project_owners
                or product_owners
            ):
                continue
            full_reasons.add(f"No declared documentation owner for changed path: {path}")
            continue
        owners = (
            project_owners | product_owners | source_owners | product_source_owners
            | (library_owners or set())
        )
        if owners:
            selected.update(owners)
            reasons.add(f"Owned path {path} affects {', '.join(sorted(owners))}")
        elif not consumers:
            full_reasons.add(f"No declared owner for changed path: {path}")

    if full_reasons:
        return _full(all_ids, paths, full_reasons, docs_changed)
    if selected:
        return ImpactPlan(
            scope="focused", projects=tuple(sorted(selected)), changed_paths=paths,
            reasons=tuple(sorted(reasons)), docs_changed=docs_changed,
        )
    return ImpactPlan(
        scope="docs", projects=(), changed_paths=paths,
        reasons=("Only ordinary Markdown documentation changed",), docs_changed=docs_changed,
    )
