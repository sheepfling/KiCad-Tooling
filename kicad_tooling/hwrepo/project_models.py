"""Project-owned configuration, registry, validation, and intake contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .connector_coverage_models import ConnectorInterfaceReview, ConnectorInventoryReview
from .design_lint_policy_models import DesignLintPolicy
from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class ToolchainRecord(StrictModel):
    id: Identifier
    kicad_version: NonEmptyText
    cli_profile: Literal["kicad-10"] | None = None
    image: NonEmptyText
    desktop_edit_policy: NonEmptyText
    installer_source: NonEmptyText
    migration_policy: NonEmptyText


class ToolchainsCatalog(StrictModel):
    schema_version: NonEmptyText
    toolchains: tuple[ToolchainRecord, ...]


class ComponentIdentity(StrictModel):
    required: bool
    part_ids: tuple[Identifier, ...]


class ProjectKind(str, Enum):
    """The engineering deliverable represented by one native KiCad project."""

    PCB = "pcb"
    PCB_ONLY = "pcb_only"
    SCHEMATIC = "schematic"
    SYSTEM_WIRING = "system_wiring"
    HARNESS_INTERFACE = "harness_interface"

    @property
    def domain_name(self) -> str:
        """Return the human-facing directory name for this design kind."""
        return {
            ProjectKind.PCB: "pcb",
            ProjectKind.PCB_ONLY: "pcb-only",
            ProjectKind.SCHEMATIC: "schematic",
            ProjectKind.SYSTEM_WIRING: "system-wiring",
            ProjectKind.HARNESS_INTERFACE: "harness-interface",
        }[self]

    @property
    def design_root(self) -> str:
        """Return the canonical root for adopted-repository project sources."""
        return "projects"

    @property
    def example_root(self) -> str:
        """Return the fixture root used by this template's reference projects."""
        return f"examples/{self.design_root}"

    @property
    def accepted_roots(self) -> tuple[str, str]:
        """Return canonical and template-fixture roots accepted by repository policy."""
        return (self.design_root, self.example_root)


class ProjectRecord(StrictModel):
    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    config: RepositoryPath
    project: RepositoryPath
    component_identity: ComponentIdentity
    tags: tuple[Identifier, ...] = ()
    interfaces: tuple[Identifier, ...] = ()
    library_ids: tuple[Identifier, ...] = ()
    mechanical_handoff: RepositoryPath | None = None
    governance_record: RepositoryPath | None = None


class CatalogPaths(StrictModel):
    parts: RepositoryPath
    interfaces: RepositoryPath
    libraries: RepositoryPath
    toolchains: RepositoryPath
    release_policies: RepositoryPath


class ProjectRegistry(StrictModel):
    schema_version: NonEmptyText
    catalogs: CatalogPaths
    projects: tuple[ProjectRecord, ...]


class ComponentContract(StrictModel):
    value: NonEmptyText
    footprint: str
    part_id: Identifier | None = None


class IgnoredChecks(StrictModel):
    erc: tuple[Identifier, ...]
    drc: tuple[Identifier, ...]


class PcbValidationContract(StrictModel):
    """Native checks and independent electrical contract for a board deliverable."""

    kind: Literal[ProjectKind.PCB]
    components: Mapping[Identifier, ComponentContract]
    nets: Mapping[NetName, tuple[Reference, ...]]
    expected_ignored_checks: IgnoredChecks


class PcbOnlyValidationContract(StrictModel):
    """Native board-layout checks where no authoritative schematic is available."""

    kind: Literal[ProjectKind.PCB_ONLY]
    expected_ignored_checks: IgnoredChecks


class SchematicValidationContract(StrictModel):
    """Native checks for a schematic-only deliverable with no manufactured PCB."""

    kind: Literal[ProjectKind.SCHEMATIC]
    components: Mapping[Identifier, ComponentContract] = Field(default_factory=dict)
    nets: Mapping[NetName, tuple[Reference, ...]] = Field(default_factory=dict)
    expected_ignored_checks: IgnoredChecks


class ProductTraceabilityValidationContract(StrictModel):
    """Shared typed authority for KiCad product, wiring, and harness review views."""

    product_id: Identifier
    connection_ids: tuple[Identifier, ...]
    terminal_ids: tuple[Identifier, ...]
    harness_ids: tuple[Identifier, ...]
    expected_ignored_checks: IgnoredChecks

    def require_complete_unique_coverage(self, *extra: tuple[str, tuple[str, ...]]) -> None:
        for label, values in (
            ("connection_ids", self.connection_ids),
            ("terminal_ids", self.terminal_ids),
            ("harness_ids", self.harness_ids),
            *extra,
        ):
            if not values:
                raise ValueError(f"{label} must not be empty for a product traceability view")
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")


class SystemWiringValidationContract(ProductTraceabilityValidationContract):
    """Trace a whole-system KiCad view to every typed product relationship."""

    kind: Literal[ProjectKind.SYSTEM_WIRING]
    mechanical_handoff_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def complete_unique_coverage(self) -> SystemWiringValidationContract:
        self.require_complete_unique_coverage(
            ("mechanical_handoff_ids", self.mechanical_handoff_ids)
        )
        return self


class HarnessInterfaceValidationContract(ProductTraceabilityValidationContract):
    """Trace a harness-interface sheet to only its owned electrical conductors."""

    kind: Literal[ProjectKind.HARNESS_INTERFACE]

    @model_validator(mode="after")
    def complete_unique_coverage(self) -> HarnessInterfaceValidationContract:
        self.require_complete_unique_coverage()
        return self


ProjectValidationContract = Annotated[
    PcbValidationContract
    | PcbOnlyValidationContract
    | SchematicValidationContract
    | SystemWiringValidationContract
    | HarnessInterfaceValidationContract,
    Field(discriminator="kind"),
]
ProductViewValidation: TypeAlias = (
    SystemWiringValidationContract | HarnessInterfaceValidationContract
)


class ProjectConfig(StrictModel):
    schema_version: NonEmptyText
    kind: ProjectKind
    assurance_profile: Literal["training", "development", "production"]
    not_for_manufacture: bool
    project_id: Identifier
    component_identity: ComponentIdentity
    toolchain_id: Identifier
    kicad_version: NonEmptyText
    cli_profile: Literal["kicad-10"] | None = None
    image: NonEmptyText
    project: RepositoryPath
    source_roots: tuple[RepositoryPath, ...]
    required_inputs: tuple[RepositoryPath, ...]
    validation: ProjectValidationContract
    electrical: RepositoryPath | None = None
    design_lint: DesignLintPolicy | None = None
    interfaces: tuple[Identifier, ...] = ()
    connector_reviews: tuple[ConnectorInterfaceReview, ...] = ()
    connector_inventory_review: ConnectorInventoryReview | None = None

    @model_validator(mode="after")
    def matching_project_kind(self) -> ProjectConfig:
        if self.kind is not self.validation.kind:
            raise ValueError("project kind must match validation contract kind")
        if (
            self.design_lint is not None
            and (
                self.design_lint.pcb_decoupling_map is not None
                or self.design_lint.pcb_protection_path_map is not None
                or self.design_lint.pcb_track_width_map is not None
                or self.design_lint.pcb_reference_plane_map is not None
                or self.design_lint.pcb_switching_loop_map is not None
                or self.design_lint.pcb_differential_pair_rule_map is not None
                or self.design_lint.pcb_signal_path_rule_map is not None
                or self.design_lint.pcb_mechanical_edge_clearance_map is not None
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
                or self.design_lint.pcb_touch_pad_clearance_map is not None
            )
            and self.kind is not ProjectKind.PCB
        ):
            raise ValueError("PCB geometry maps require an authoritative PCB project")
        return self


class ProjectDiscovery(StrictModel):
    """Repository-wide dependencies and roots; project records live with boards."""

    schema_version: Literal["1"] = "1"
    catalogs: CatalogPaths
    project_roots: Annotated[tuple[RepositoryPath, ...], Field(min_length=1)]
    project_depth: Annotated[int, Field(ge=1, le=8)] = 1

    @model_validator(mode="after")
    def unique_project_roots(self) -> ProjectDiscovery:
        if len({name.casefold() for name in self.project_roots}) != len(self.project_roots):
            raise ValueError("Discovery roots must be unique")
        return self


class ReleaseExportSettings(StrictModel):
    """Manufacturer-facing settings reviewed with each board's source."""

    gerber_layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    coordinate_origin: Literal["absolute", "plot"] = "absolute"
    position_units: Literal["mm", "in"] = "mm"
    assembly_variant: NonEmptyText | None = None
    supplier_formats: tuple[Literal["odb", "ipc2581", "ipcd356"], ...] = ()

    @model_validator(mode="after")
    def unique_supplier_formats(self) -> ReleaseExportSettings:
        if len(set(self.supplier_formats)) != len(self.supplier_formats):
            raise ValueError("supplier_formats must not contain duplicates")
        return self


class ProjectManifest(StrictModel):
    """Authored project-local inputs. Shared paths are explicitly repository-relative."""

    schema_version: Literal["1"] = "1"
    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    toolchain_id: Identifier
    project: RepositoryPath
    source_roots: tuple[RepositoryPath, ...]
    required_inputs: tuple[RepositoryPath, ...]
    checks: RepositoryPath = "tests/contract.json"
    shared_source_roots: tuple[RepositoryPath, ...] = ()
    shared_inputs: tuple[RepositoryPath, ...] = ()
    component_identity: ComponentIdentity
    tags: tuple[Identifier, ...] = ()
    interfaces: tuple[Identifier, ...] = ()
    connector_reviews: tuple[ConnectorInterfaceReview, ...] = ()
    connector_inventory_review: ConnectorInventoryReview | None = None
    library_ids: tuple[Identifier, ...] = ()
    mechanical_handoff: RepositoryPath | None = None
    governance_record: RepositoryPath | None = None
    release_exports: ReleaseExportSettings | None = None

    @model_validator(mode="after")
    def unique_connector_reviews(self) -> ProjectManifest:
        references = [item.reference.casefold() for item in self.connector_reviews]
        if len(set(references)) != len(references):
            raise ValueError("Connector review references must be unique")
        if len(set(self.interfaces)) != len(self.interfaces):
            raise ValueError("Project interface IDs must be unique")
        interface_ids = {
            item.interface_id for item in self.connector_reviews if item.interface_id is not None
        }
        if not interface_ids <= set(self.interfaces):
            raise ValueError("Connector reviews must reference declared project interfaces")
        return self


class ProjectTestContract(StrictModel):
    schema_version: Literal["1"] = "1"
    validation: ProjectValidationContract
    electrical: RepositoryPath | None = None
    design_lint: DesignLintPolicy | None = None

    @model_validator(mode="after")
    def lint_requires_netlist(self) -> ProjectTestContract:
        if self.design_lint is not None and self.validation.kind not in {
            ProjectKind.PCB,
            ProjectKind.SCHEMATIC,
        }:
            raise ValueError("design_lint requires a pcb or schematic netlist")
        if (
            self.design_lint is not None
            and (
                self.design_lint.pcb_decoupling_map is not None
                or self.design_lint.pcb_protection_path_map is not None
                or self.design_lint.pcb_track_width_map is not None
                or self.design_lint.pcb_reference_plane_map is not None
                or self.design_lint.pcb_switching_loop_map is not None
                or self.design_lint.pcb_differential_pair_rule_map is not None
                or self.design_lint.pcb_signal_path_rule_map is not None
                or self.design_lint.pcb_mechanical_edge_clearance_map is not None
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
                or self.design_lint.pcb_touch_pad_clearance_map is not None
            )
            and self.validation.kind is not ProjectKind.PCB
        ):
            raise ValueError("PCB geometry maps require an authoritative PCB project")
        return self


class ProjectScaffoldReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    directory: str
    issues: tuple[str, ...] = ()
    next_step: str = "Create the native KiCad design, then complete the test contract and run kicad_tooling.verify."


class ProjectImportReport(StrictModel):
    """Import receipt; copying source is separate from accepting its engineering checks."""

    status: Literal["PASS", "FAIL"]
    directory: str
    source_project: str
    dry_run: bool
    copied_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    excluded: Mapping[RepositoryPath, str] = Field(default_factory=dict)
    issues: tuple[str, ...] = ()
    review_required: Literal[True] = True
    next_step: str = "Review dependencies, populate independent test expectations, then run kicad_tooling.verify. Import does not approve the design."


class KiCadForeignImportSummary(StrictModel):
    """Narrow projection of KiCad's retained, version-specific JSON import report."""

    source_format: NonEmptyText
    mapped_layers: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class ImportInventoryCandidate(StrictModel):
    """One suggested island and its unchanged-source import preview."""

    source_project: NonEmptyText
    suggested_project_id: Identifier
    kind: ProjectKind | None
    preview: ProjectImportReport
    next_command: NonEmptyText


class ImportInventoryReport(StrictModel):
    """Read-only bulk intake plan; candidates still require individual review."""

    schema_version: Literal["1"] = "1"
    lane: Literal["IMPORT_INVENTORY"] = "IMPORT_INVENTORY"
    source_directory: NonEmptyText
    status: Literal["PASS", "NEEDS_WORK"]
    copied: Literal[False] = False
    candidates: tuple[ImportInventoryCandidate, ...] = ()
    skipped_local_state: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_step: NonEmptyText = (
        "Review each candidate and its exclusions; run one import-project command per accepted design. "
        "An import preview is not electrical validation."
    )
