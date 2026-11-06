"""Typed shared governance inputs captured for one lint operation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .discovery import ProjectRegistrySnapshot
from .governance_records import (
    GovernanceCatalogDocument,
    GovernanceCatalogIndex,
    GovernanceDocumentSource,
    GovernanceTeamPolicyDocument,
    index_governance_catalog,
    read_governance_catalog,
    read_governance_team_policy,
    require_governance_document_current,
)
from .models import (
    InterfaceRecord,
    InterfacesCatalog,
    LibrariesCatalog,
    LibraryRecord,
)
from .part_catalog_models import PartRecord, PartsCatalog
from .product_source_inputs import (
    ProductIndexDocument,
    read_product_index_document,
    require_product_index_document_current,
)
from .project_models import ToolchainRecord, ToolchainsCatalog
from .release_contract_models import ReleasePoliciesCatalog


@dataclass(frozen=True, slots=True)
class GovernanceLintSharedInputs:
    """Named catalog and policy documents used by the governance evaluator."""

    team_policy: GovernanceTeamPolicyDocument
    product_index: ProductIndexDocument
    parts_document: GovernanceCatalogDocument[PartsCatalog]
    parts_catalog: GovernanceCatalogIndex[PartRecord]
    interfaces_document: GovernanceCatalogDocument[InterfacesCatalog]
    interfaces_catalog: GovernanceCatalogIndex[InterfaceRecord]
    libraries_catalog: GovernanceCatalogIndex[LibraryRecord]
    toolchains_document: GovernanceCatalogDocument[ToolchainsCatalog]
    toolchains_catalog: GovernanceCatalogIndex[ToolchainRecord]
    release_policies: GovernanceCatalogDocument[ReleasePoliciesCatalog]
    issues: tuple[str, ...]

    @property
    def sources(self) -> tuple[GovernanceDocumentSource, ...]:
        return (
            self.team_policy.source,
            self.parts_catalog.source,
            self.interfaces_catalog.source,
            self.libraries_catalog.source,
            self.toolchains_document.source,
            self.release_policies.source,
        )


def read_governance_lint_shared_inputs(
    root: Path,
    snapshot: ProjectRegistrySnapshot,
) -> GovernanceLintSharedInputs:
    """Capture the named shared catalogs and policy selected by one registry snapshot."""
    registry = snapshot.registry
    configuration = snapshot.discovery.repository_configuration
    team_policy = read_governance_team_policy(root, configuration)
    parts = read_governance_catalog(root, registry.catalogs.parts, PartsCatalog)
    interfaces = read_governance_catalog(root, registry.catalogs.interfaces, InterfacesCatalog)
    libraries = read_governance_catalog(root, registry.catalogs.libraries, LibrariesCatalog)
    toolchains = read_governance_catalog(root, registry.catalogs.toolchains, ToolchainsCatalog)
    release_policies = read_governance_catalog(
        root, registry.catalogs.release_policies, ReleasePoliciesCatalog
    )
    product_index = read_product_index_document(root, configuration.value.layout.products)
    parts_index = index_governance_catalog(parts, lambda catalog: catalog.parts, "parts catalog")
    interfaces_index = index_governance_catalog(
        interfaces, lambda catalog: catalog.interfaces, "interface catalog"
    )
    libraries_index = index_governance_catalog(
        libraries, lambda catalog: catalog.libraries, "library catalog"
    )
    toolchains_index = index_governance_catalog(
        toolchains, lambda catalog: catalog.toolchains, "toolchain catalog"
    )
    issues = (
        *parts_index.lookup.issues,
        *interfaces_index.lookup.issues,
        *libraries_index.lookup.issues,
        *toolchains_index.lookup.issues,
    )
    return GovernanceLintSharedInputs(
        team_policy=team_policy,
        product_index=product_index,
        parts_document=parts,
        parts_catalog=parts_index,
        interfaces_document=interfaces,
        interfaces_catalog=interfaces_index,
        libraries_catalog=libraries_index,
        toolchains_document=toolchains,
        toolchains_catalog=toolchains_index,
        release_policies=release_policies,
        issues=issues,
    )


def governance_lint_shared_input_freshness_issues(
    root: Path,
    inputs: GovernanceLintSharedInputs,
) -> tuple[str, ...]:
    """Report shared governance sources that changed after evaluation began."""
    issues: list[str] = []
    for source in inputs.sources:
        try:
            require_governance_document_current(root, source)
        except ValueError as exc:
            issues.append(str(exc))
    try:
        require_product_index_document_current(root, inputs.product_index)
    except ValueError as exc:
        issues.append(str(exc))
    return tuple(issues)
