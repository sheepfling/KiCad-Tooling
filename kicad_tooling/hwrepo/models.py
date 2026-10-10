"""Typed, strict records for repository inputs, policy outputs and generated views."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from enum import Enum
from typing import Annotated, Literal, cast

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from . import component_peer_pin_models as _component_peer_pin_models
from . import connector_peer_pin_models as _connector_peer_pin_models
from . import design_lint_rule_models as _design_lint_rule_models
from . import design_lint_rule_types as _design_lint_rule_types
from . import digital_peer_voltage_models as _digital_peer_voltage_models
from . import pcb_decoupling_models as _pcb_decoupling_models
from . import pcb_drc_models as _pcb_drc_models
from . import pcb_reference_plane_models as _pcb_reference_plane_models
from . import pcb_rf_antenna_models as _pcb_rf_antenna_models
from . import pcb_switching_loop_models as _pcb_switching_loop_models
from . import pcb_track_width_models as _pcb_track_width_models
from . import serial_peer_reference_models as _serial_peer_reference_models
from . import usb_peer_reference_models as _usb_peer_reference_models
from .model_primitives import (
    CapacitancePf,
    Digest,
    GitCommit,
    Identifier,
    NativePcbUuid,
    NetName,
    NonEmptyText,
    NonNegativeCapacitancePf,
    NonNegativeCount,
    PositiveCount,
    PositiveMeasure,
    Reference,
    RepositoryPath,
    ResistorReference,
    Stm32PortPin,
    Stm32SymbolPin,
    StrictModel,
    TemplateVersion,
    UsbDataPortGroup,
)
from .netlist_pins import is_native_unconnected_net_name

ComponentPeerPinRuleCoverage = _component_peer_pin_models.ComponentPeerPinRuleCoverage
ConnectorPartIdPeerPinCoverage = _connector_peer_pin_models.ConnectorPartIdPeerPinCoverage
ConnectorPeerPinHeuristicCoverage = _connector_peer_pin_models.ConnectorPeerPinHeuristicCoverage
DigitalPeerVoltageRuleCoverage = _digital_peer_voltage_models.DigitalPeerVoltageRuleCoverage
SerialPeerReferenceCoverageReport = _serial_peer_reference_models.SerialPeerReferenceCoverageReport
SerialPeerReferenceLinkCoverageEntry = (
    _serial_peer_reference_models.SerialPeerReferenceLinkCoverageEntry
)
UsbPeerDataLineCoverage = _usb_peer_reference_models.UsbPeerDataLineCoverage
UsbPeerDataPathCoverage = _usb_peer_reference_models.UsbPeerDataPathCoverage
UsbPeerDataSeriesResistorCoverage = _usb_peer_reference_models.UsbPeerDataSeriesResistorCoverage
UsbPeerDataShuntBranchCoverage = _usb_peer_reference_models.UsbPeerDataShuntBranchCoverage
UsbPeerEndpointGroupCoverage = _usb_peer_reference_models.UsbPeerEndpointGroupCoverage
UsbPeerReferenceCoverageReport = _usb_peer_reference_models.UsbPeerReferenceCoverageReport
UsbPeerReferencePathCoverageEntry = _usb_peer_reference_models.UsbPeerReferencePathCoverageEntry
UsbPeerReferencePinCoverage = _usb_peer_reference_models.UsbPeerReferencePinCoverage
PcbDrcMinMaxRequirement = _pcb_drc_models.PcbDrcMinMaxRequirement
PcbDrcMaximumRequirement = _pcb_drc_models.PcbDrcMaximumRequirement
PcbDrcPadSelectorPattern = _pcb_drc_models.PcbDrcPadSelectorPattern
PcbSignalPathRequirement = _pcb_drc_models.PcbSignalPathRequirement
PcbSignalPathBundleRequirement = _pcb_drc_models.PcbSignalPathBundleRequirement
PcbSignalPathRuleMap = _pcb_drc_models.PcbSignalPathRuleMap
PcbDifferentialPairRuleRequirement = _pcb_drc_models.PcbDifferentialPairRuleRequirement
PcbDifferentialPairRuleMap = _pcb_drc_models.PcbDifferentialPairRuleMap
PcbDrcConstraintName = _pcb_drc_models.PcbDrcConstraintName
PcbDrcConstraintCoverageStatus = _pcb_drc_models.PcbDrcConstraintCoverageStatus
PcbDrcConstraintCoverage = _pcb_drc_models.PcbDrcConstraintCoverage
PcbDifferentialPairRuleCoverageEntry = _pcb_drc_models.PcbDifferentialPairRuleCoverageEntry
PcbDifferentialPairRuleCoverageReport = _pcb_drc_models.PcbDifferentialPairRuleCoverageReport
PcbSignalPathRuleCoverageEntry = _pcb_drc_models.PcbSignalPathRuleCoverageEntry
PcbSignalPathRuleCoverageReport = _pcb_drc_models.PcbSignalPathRuleCoverageReport
PcbDecouplingCandidateObservation = _pcb_decoupling_models.PcbDecouplingCandidateObservation
PcbDecouplingCoverageEntry = _pcb_decoupling_models.PcbDecouplingCoverageEntry
PcbDecouplingCoverageReport = _pcb_decoupling_models.PcbDecouplingCoverageReport
PcbTrackWidthRequirement = _pcb_track_width_models.PcbTrackWidthRequirement
PcbTrackWidthMap = _pcb_track_width_models.PcbTrackWidthMap
PcbTrackWidthMeasurement = _pcb_track_width_models.PcbTrackWidthMeasurement
PcbTrackWidthCoverageEntry = _pcb_track_width_models.PcbTrackWidthCoverageEntry
PcbTrackWidthCoverageReport = _pcb_track_width_models.PcbTrackWidthCoverageReport
PcbReferencePlaneRequirement = _pcb_reference_plane_models.PcbReferencePlaneRequirement
PcbReferencePlaneMap = _pcb_reference_plane_models.PcbReferencePlaneMap
PcbReferencePlaneTrackMeasurement = _pcb_reference_plane_models.PcbReferencePlaneTrackMeasurement
PcbReferencePlaneCoverageEntry = _pcb_reference_plane_models.PcbReferencePlaneCoverageEntry
PcbReferencePlaneCoverageReport = _pcb_reference_plane_models.PcbReferencePlaneCoverageReport
PcbSwitchingLoopPad = _pcb_switching_loop_models.PcbSwitchingLoopPad
PcbSwitchingLoopEdge = _pcb_switching_loop_models.PcbSwitchingLoopEdge
PcbSwitchingLoopRequirement = _pcb_switching_loop_models.PcbSwitchingLoopRequirement
PcbSwitchingLoopMap = _pcb_switching_loop_models.PcbSwitchingLoopMap
PcbSwitchingLoopRouteEdgeCoverage = _pcb_switching_loop_models.PcbSwitchingLoopRouteEdgeCoverage
PcbSwitchingLoopCoverageEntry = _pcb_switching_loop_models.PcbSwitchingLoopCoverageEntry
PcbSwitchingLoopCoverageReport = _pcb_switching_loop_models.PcbSwitchingLoopCoverageReport
PcbRfAntennaKeepout = _pcb_rf_antenna_models.PcbRfAntennaKeepout
PcbRfAntennaPolygon = _pcb_rf_antenna_models.PcbRfAntennaPolygon
PcbRfModuleAntennaCoverageEntry = _pcb_rf_antenna_models.PcbRfModuleAntennaCoverageEntry
PcbRfModuleAntennaCoverageReport = _pcb_rf_antenna_models.PcbRfModuleAntennaCoverageReport
PcbRfModuleAntennaMap = _pcb_rf_antenna_models.PcbRfModuleAntennaMap
PcbRfModuleAntennaRequirement = _pcb_rf_antenna_models.PcbRfModuleAntennaRequirement
DesignLintRuleCatalog = _design_lint_rule_models.DesignLintRuleCatalog
DesignLintRuleCatalogDocument = _design_lint_rule_models.DesignLintRuleCatalogDocument
DesignLintRuleMetadata = _design_lint_rule_models.DesignLintRuleMetadata
DesignLintRuleId = _design_lint_rule_types.DesignLintRuleId
DesignLintTheme = _design_lint_rule_types.DesignLintTheme


class SchematicTextMetricsResource(StrictModel):
    """Pinned KiCad standard-stroke glyph metrics used by schematic review lint."""

    schema_version: Literal["4"]
    kicad_version: Literal["10.0.6"]
    native_image: Literal[
        "kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec"
    ]
    reference_size_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    stroke_width_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    single_glyph_svg_end_spacing_mm: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    line_end_spacing_mm: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    multiline_line_spacing_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    vertical_ink_envelope_ratio: tuple[
        Annotated[float, Field(allow_inf_nan=False)],
        Annotated[float, Field(allow_inf_nan=False)],
    ]
    metrics_method: NonEmptyText
    advances_mm: Mapping[
        Annotated[str, StringConstraints(min_length=1, max_length=1)],
        Annotated[float, Field(gt=0, allow_inf_nan=False)],
    ]

    @model_validator(mode="after")
    def complete_calibrated_glyph_metrics(self) -> SchematicTextMetricsResource:
        expected_characters = {
            " ",
            *(chr(code) for code in range(33, 127)),
            "°",
            "±",
            "µ",
            "×",
            "Ω",
            "—",
        }
        if set(self.advances_mm) != expected_characters:
            raise ValueError("Schematic text metrics must cover the calibrated glyph set exactly")
        top, bottom = self.vertical_ink_envelope_ratio
        if top >= bottom:
            raise ValueError("Schematic text metric vertical envelope is reversed")
        return self


class Assurance(str, Enum):
    UNKNOWN = "unknown"
    ASSUMED = "assumed"
    INFERRED = "inferred"
    OBSERVED = "observed"
    MANUFACTURER_DOCUMENTED = "manufacturer_documented"
    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"


class PartStatus(str, Enum):
    TRAINING = "not_for_manufacture"
    APPROVED = "approved"


class PartCadBinding(StrictModel):
    """Reviewed symbol, value, package and source model for one catalog part."""

    symbol_id: NonEmptyText
    value: NonEmptyText
    footprint: Annotated[str, StringConstraints(pattern=r"^[^:\r\n]+:[^:\r\n]+$")]
    model: RepositoryPath
    digikey_sku: Annotated[str, StringConstraints(min_length=1)] | None = None

    @model_validator(mode="after")
    def exact_sku(self) -> PartCadBinding:
        if self.digikey_sku is not None and (
            self.digikey_sku != self.digikey_sku.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in self.digikey_sku)
        ):
            raise ValueError("DigiKey SKU must be exact text without padding or control characters")
        return self


class PartRecord(StrictModel):
    id: Identifier
    revision: Identifier
    description: NonEmptyText
    part_class: NonEmptyText
    unit: Literal["each"]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    datasheet_url: NonEmptyText
    lifecycle: NonEmptyText
    status: PartStatus
    approved_alternates: tuple[Identifier, ...] = ()
    cad: PartCadBinding | None = None


class PartsCatalog(StrictModel):
    schema_version: NonEmptyText
    parts: tuple[PartRecord, ...]


ConnectorPinRole = Literal["signal", "return", "supply", "shield", "other"]


class InterfacePin(StrictModel):
    number: NonEmptyText
    signal: NonEmptyText
    role: ConnectorPinRole | None = None
    direction: NonEmptyText
    voltage_domain: NonEmptyText
    mating: NonEmptyText
    orientation: NonEmptyText
    mechanical_clearance: NonEmptyText


class InterfaceRecord(StrictModel):
    id: Identifier
    revision: NonEmptyText
    pins: tuple[InterfacePin, ...]

    @model_validator(mode="after")
    def unique_pin_numbers(self) -> InterfaceRecord:
        if len({pin.number for pin in self.pins}) != len(self.pins):
            raise ValueError("Interface pin numbers must be unique")
        return self


class InterfacesCatalog(StrictModel):
    schema_version: NonEmptyText
    interfaces: tuple[InterfaceRecord, ...]


class LibraryRecord(StrictModel):
    id: Identifier
    version: NonEmptyText
    path: RepositoryPath
    owner: NonEmptyText
    status: NonEmptyText
    provenance_path: RepositoryPath
    provenance_sha256: Digest
    licensing_path: RepositoryPath
    licensing_sha256: Digest


class LibrariesCatalog(StrictModel):
    schema_version: NonEmptyText
    libraries: tuple[LibraryRecord, ...]


class LibrarySbom(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    libraries: tuple[LibraryRecord, ...]


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


SchematicGeometryRuleId = Literal[
    "schematic.wire_end_on_pin_line",
    "schematic.pin_tip_on_wire_interior",
    "schematic.wire_endpoint_near_pin_tip",
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.coincident_text_anchors",
    "schematic.free_text_overlap",
    "schematic.free_text_over_wire",
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
]
SchematicGeometryRuleCoverageStatus = Literal["DISABLED", "COMPLETE", "PARTIAL", "UNSUPPORTED"]


class DesignLintRuleOverride(StrictModel):
    rule_id: DesignLintRuleId
    mode: Literal["review", "block", "off"]
    reason: NonEmptyText


class DesignLintIgnore(StrictModel):
    rule_id: DesignLintRuleId
    fingerprint: Digest
    reason: NonEmptyText


class I2cAddressBitRequirement(StrictModel):
    """Reviewed mapping from one 7-bit responder-address bit to a symbol pin."""

    bit: Annotated[int, Field(ge=0, le=6)]
    pin: Reference
    function: NonEmptyText
    low_net: NetName
    high_net: NetName

    @model_validator(mode="after")
    def distinct_logic_nets(self) -> I2cAddressBitRequirement:
        if self.low_net == self.high_net:
            raise ValueError("I2C address bit low_net and high_net must differ")
        return self


class I2cResponderAddressRequirement(StrictModel):
    """Project-owned identity and static-address basis for one bus responder."""

    reference: Identifier
    expected_symbol: NonEmptyText
    sda_pin: Reference
    scl_pin: Reference
    mode: Literal["fixed", "strapped", "dynamic"]
    address: Annotated[int, Field(ge=0, le=127)] | None = None
    address_bits: tuple[I2cAddressBitRequirement, ...] = ()
    basis: NonEmptyText

    @model_validator(mode="after")
    def address_source_is_explicit(self) -> I2cResponderAddressRequirement:
        prefix = f"{self.reference}."
        pins = (self.sda_pin, self.scl_pin, *(item.pin for item in self.address_bits))
        if self.sda_pin == self.scl_pin:
            raise ValueError("I2C responder SDA and SCL pins must differ")
        if any(not pin.casefold().startswith(prefix.casefold()) for pin in pins):
            raise ValueError("I2C responder pins must belong to its declared component")
        normalized_pins = [pin.casefold() for pin in pins]
        if len(set(normalized_pins)) != len(normalized_pins):
            raise ValueError("I2C responder signal and address pins must be unique")
        if len({item.pin.casefold() for item in self.address_bits}) != len(self.address_bits):
            raise ValueError("I2C address pin mappings must be unique")
        if len({item.bit for item in self.address_bits}) != len(self.address_bits):
            raise ValueError("I2C address bit positions must be unique")
        if self.mode == "fixed" and (self.address is None or self.address_bits):
            raise ValueError("Fixed I2C addresses need one authored address and no strap pins")
        if self.mode == "strapped" and (self.address is None or not self.address_bits):
            raise ValueError("Strapped I2C addresses need a base address and mapped address pins")
        if self.mode == "dynamic" and (self.address is not None or self.address_bits):
            raise ValueError("Dynamic I2C addresses cannot declare a static value or strap pins")
        return self


class I2cAddressSegmentRequirement(StrictModel):
    """One project-declared arbitration domain, such as a mux output segment."""

    id: Identifier
    sda_net: NetName
    scl_net: NetName
    responders: Annotated[tuple[I2cResponderAddressRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_signal_nets_and_responders(self) -> I2cAddressSegmentRequirement:
        if self.sda_net == self.scl_net:
            raise ValueError("I2C address segment SDA and SCL nets must differ")
        references = [item.reference.casefold() for item in self.responders]
        if len(set(references)) != len(references):
            raise ValueError("I2C responder references must be unique within a segment")
        return self


class I2cAddressMap(StrictModel):
    """Reviewed scope for deterministic static responder-address checks."""

    basis: NonEmptyText
    segments: Annotated[tuple[I2cAddressSegmentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_segments_and_responders(self) -> I2cAddressMap:
        if len({item.id.casefold() for item in self.segments}) != len(self.segments):
            raise ValueError("I2C address segment IDs must be unique")
        signal_pairs = [(item.sda_net, item.scl_net) for item in self.segments]
        if len(set(signal_pairs)) != len(signal_pairs):
            raise ValueError("I2C address segments must use unique SDA/SCL net pairs")
        signal_nets = [net for item in self.segments for net in (item.sda_net, item.scl_net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("I2C address segments cannot share signal nets")
        references = [
            responder.reference.casefold()
            for segment in self.segments
            for responder in segment.responders
        ]
        if len(set(references)) != len(references):
            raise ValueError("An I2C responder can be assigned to only one declared segment")
        return self


class ExternalProtectionChannelRequirement(StrictModel):
    """Reviewed TVS or clamp channel between one interface signal and its reference."""

    device_reference: Identifier
    signal_pin: Reference
    reference_pin: Reference
    reference_net: NetName

    @model_validator(mode="after")
    def distinct_component_pins(self) -> ExternalProtectionChannelRequirement:
        if self.signal_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("Protection channel signal and reference pins must differ")
        if (
            self.signal_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
            or self.reference_pin.rsplit(".", 1)[0].casefold() != self.device_reference.casefold()
        ):
            raise ValueError("Protection channel pins must belong to the declared device")
        return self


class ExternalProtectionInterfaceRequirement(StrictModel):
    """Project-authored protection disposition for one reviewed connector signal pin."""

    connector_reference: Identifier
    expected_connector_symbol: NonEmptyText
    expected_connector_footprint: NonEmptyText
    connector_pin: Reference
    signal_net: NetName
    disposition: Literal["required", "not_required"]
    basis: NonEmptyText
    channels: tuple[ExternalProtectionChannelRequirement, ...] = ()

    @model_validator(mode="after")
    def complete_protection_disposition(self) -> ExternalProtectionInterfaceRequirement:
        if not self.connector_pin.casefold().startswith(f"{self.connector_reference}.".casefold()):
            raise ValueError("External interface pin must belong to its connector")
        if self.disposition == "required" and not self.channels:
            raise ValueError("Required external protection needs at least one mapped channel")
        if self.disposition == "not_required" and self.channels:
            raise ValueError("Not-required external protection cannot map device channels")
        channel_keys = [
            (item.device_reference.casefold(), item.signal_pin.casefold()) for item in self.channels
        ]
        if len(set(channel_keys)) != len(channel_keys):
            raise ValueError("External protection channels must be unique per device signal pin")
        return self


class ExternalProtectionDeviceRequirement(StrictModel):
    """Exact device identity and native pin-net disposition for mapped protection parts."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    pin_nets: Mapping[Reference, NetName]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_component_pin_disposition(self) -> ExternalProtectionDeviceRequirement:
        prefix = f"{self.reference}.".casefold()
        pins = (*self.pin_nets, *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix) for pin in pins):
            raise ValueError("Protection device pins must belong to the declared component")
        normalized = [pin.casefold() for pin in pins]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Protection device pins must have one unique disposition")
        if len(self.pin_nets) < 2:
            raise ValueError("A mapped protection device needs at least two assigned pins")
        return self


class ExternalProtectionMap(StrictModel):
    """Explicit requirements for protection or reviewed non-applicability at interfaces."""

    basis: NonEmptyText
    interfaces: Annotated[tuple[ExternalProtectionInterfaceRequirement, ...], Field(min_length=1)]
    devices: tuple[ExternalProtectionDeviceRequirement, ...] = ()

    @model_validator(mode="after")
    def map_devices_and_interfaces(self) -> ExternalProtectionMap:
        interface_pins = [item.connector_pin.casefold() for item in self.interfaces]
        if len(set(interface_pins)) != len(interface_pins):
            raise ValueError("External protection interface pins must be unique")
        device_map = {item.reference.casefold(): item for item in self.devices}
        if len(device_map) != len(self.devices):
            raise ValueError("External protection device references must be unique")
        used_devices: set[str] = set()
        for interface in self.interfaces:
            for channel in interface.channels:
                key = channel.device_reference.casefold()
                device = device_map.get(key)
                if device is None:
                    raise ValueError("Protection channel references an undeclared device")
                used_devices.add(key)
                if device.pin_nets.get(channel.signal_pin) != interface.signal_net:
                    raise ValueError("Protection signal pin must map to the interface signal net")
                if device.pin_nets.get(channel.reference_pin) != channel.reference_net:
                    raise ValueError(
                        "Protection reference pin must map to its declared reference net"
                    )
        if used_devices != set(device_map):
            raise ValueError("Every declared protection device must serve a mapped channel")
        return self


class UsbDataSeriesResistorRequirement(StrictModel):
    """Exact project-selected USB data-line resistor and accepted nominal range."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_resistance_range(self) -> UsbDataSeriesResistorRequirement:
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("USB data series-resistor range is reversed")
        return self


class UsbDataPathLineRequirement(StrictModel):
    """PHY-specific path; parallel pin tuples list every same-net contact."""

    line: Literal["D+", "D-"]
    connector_pin: Reference
    phy_pin: Reference
    connector_net: NetName
    phy_net: NetName
    topology: Literal["direct", "series_resistor"]
    connector_parallel_pins: tuple[Reference, ...] = ()
    phy_parallel_pins: tuple[Reference, ...] = ()
    series_resistor: UsbDataSeriesResistorRequirement | None = None

    @property
    def connector_pins(self) -> tuple[str, ...]:
        return (self.connector_pin, *self.connector_parallel_pins)

    @property
    def phy_pins(self) -> tuple[str, ...]:
        return (self.phy_pin, *self.phy_parallel_pins)

    @model_validator(mode="after")
    def topology_matches_resistor_disposition(self) -> UsbDataPathLineRequirement:
        for pin in (*self.connector_pins, *self.phy_pins):
            if "." not in pin:
                raise ValueError("USB data endpoint pins must use COMPONENT.PIN form")
        if len({pin.casefold() for pin in self.connector_pins}) != len(self.connector_pins):
            raise ValueError("USB connector data pins must be unique")
        if len({pin.casefold() for pin in self.phy_pins}) != len(self.phy_pins):
            raise ValueError("USB PHY data pins must be unique")
        if self.topology == "direct":
            if self.connector_net != self.phy_net or self.series_resistor is not None:
                raise ValueError(
                    "Direct USB data paths need one shared net and no series-resistor map"
                )
        elif self.connector_net == self.phy_net or self.series_resistor is None:
            raise ValueError(
                "USB data series-resistor paths need distinct nets and an exact resistor map"
            )
        return self


class UsbReferencePinRequirement(StrictModel):
    """One source-reviewed USB endpoint reference pin and expected native net."""

    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB reference pin mappings must use COMPONENT.PIN form")
        return value


class ReferenceBondRequirement(StrictModel):
    """One exact fitted two-pin component mapped between distinct reference nets."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    side_a_pin: Reference
    side_b_pin: Reference
    side_a_net: NetName
    side_b_net: NetName

    @model_validator(mode="after")
    def component_sides_are_distinct(self) -> ReferenceBondRequirement:
        if self.side_a_net.casefold() == self.side_b_net.casefold():
            raise ValueError("USB reference bonds must span distinct schematic nets")
        if self.side_a_pin.casefold() == self.side_b_pin.casefold():
            raise ValueError("USB reference-bond sides must use distinct pins")
        for pin in (self.side_a_pin, self.side_b_pin):
            if "." not in pin or pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("USB reference-bond pins must belong to the declared component")
        return self


class UsbDataInterfaceRequirement(StrictModel):
    """Reviewed connector-to-PHY USB 2.0 data pair and selected topology."""

    id: Identifier
    basis: NonEmptyText
    connector_reference: Identifier
    expected_connector_symbol: NonEmptyText
    expected_connector_footprint: NonEmptyText
    phy_reference: Identifier
    expected_phy_symbol: NonEmptyText
    expected_phy_footprint: NonEmptyText
    data_port_group: UsbDataPortGroup | None = None
    positive: UsbDataPathLineRequirement
    negative: UsbDataPathLineRequirement
    connector_reference_pins: tuple[UsbReferencePinRequirement, ...] = ()
    phy_reference_pins: tuple[UsbReferencePinRequirement, ...] = ()
    reference_policy: Literal["common_net", "bonded", "separate_nets"] | None = None
    reference_bond: ReferenceBondRequirement | None = None

    @model_validator(mode="after")
    def complete_distinct_pair(self) -> UsbDataInterfaceRequirement:
        if self.connector_reference.casefold() == self.phy_reference.casefold():
            raise ValueError("USB connector and PHY references must differ")
        if self.positive.line != "D+" or self.negative.line != "D-":
            raise ValueError("USB data pair must map one D+ line and one D- line")
        if any(
            any(
                not pin.casefold().startswith(f"{self.connector_reference}.".casefold())
                for pin in line.connector_pins
            )
            or any(
                not pin.casefold().startswith(f"{self.phy_reference}.".casefold())
                for pin in line.phy_pins
            )
            for line in (self.positive, self.negative)
        ):
            raise ValueError("USB data endpoints must belong to the declared connector and PHY")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.connector_reference.casefold()
            for item in self.connector_reference_pins
        ):
            raise ValueError("USB connector reference pins must belong to the declared connector")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.phy_reference.casefold()
            for item in self.phy_reference_pins
        ):
            raise ValueError("USB PHY reference pins must belong to the declared PHY")
        connector_reference_ids = [item.pin.casefold() for item in self.connector_reference_pins]
        phy_reference_ids = [item.pin.casefold() for item in self.phy_reference_pins]
        if len(set(connector_reference_ids)) != len(connector_reference_ids):
            raise ValueError("USB connector reference pin mappings must be unique")
        if len(set(phy_reference_ids)) != len(phy_reference_ids):
            raise ValueError("USB PHY reference pin mappings must be unique")
        signal_pin_ids = {
            item.casefold()
            for item in (
                *self.positive.connector_pins,
                *self.positive.phy_pins,
                *self.negative.connector_pins,
                *self.negative.phy_pins,
            )
        }
        if signal_pin_ids & (set(connector_reference_ids) | set(phy_reference_ids)):
            raise ValueError("USB data and reference pin mappings must be distinct")
        if self.reference_policy is None:
            if self.connector_reference_pins or self.phy_reference_pins or self.reference_bond:
                raise ValueError("USB reference pin mappings need an explicit reference policy")
        else:
            if not self.connector_reference_pins or not self.phy_reference_pins:
                raise ValueError("USB reference policy needs mapped pins on both connector and PHY")
            connector_reference_nets = {
                item.net.casefold() for item in self.connector_reference_pins
            }
            phy_reference_nets = {item.net.casefold() for item in self.phy_reference_pins}
            if len(connector_reference_nets) != 1 or len(phy_reference_nets) != 1:
                raise ValueError("Each USB endpoint must use one declared reference net")
            if self.reference_policy == "common_net":
                if connector_reference_nets != phy_reference_nets:
                    raise ValueError("common_net USB reference pins must share one declared net")
                if self.reference_bond is not None:
                    raise ValueError("common_net USB reference policy cannot declare a bond")
            elif self.reference_policy == "separate_nets":
                if connector_reference_nets == phy_reference_nets:
                    raise ValueError("separate_nets USB reference policy needs distinct nets")
                if self.reference_bond is not None:
                    raise ValueError("separate_nets USB reference policy cannot declare a bond")
            elif connector_reference_nets == phy_reference_nets:
                raise ValueError("bonded USB reference policy needs distinct endpoint nets")
            elif self.reference_bond is None:
                raise ValueError("bonded USB reference policy needs one exact bond component")
            elif {
                self.reference_bond.side_a_net.casefold(),
                self.reference_bond.side_b_net.casefold(),
            } != connector_reference_nets | phy_reference_nets:
                raise ValueError("USB reference bond must join the mapped connector and PHY nets")
            elif self.reference_bond.reference.casefold() in {
                self.connector_reference.casefold(),
                self.phy_reference.casefold(),
            }:
                raise ValueError("USB reference bond cannot reuse an endpoint component")
        if self.reference_bond is not None and self.reference_bond.reference.casefold() in {
            line.series_resistor.reference.casefold()
            for line in (self.positive, self.negative)
            if line.series_resistor is not None
        }:
            raise ValueError("USB reference bond cannot reuse a data-line series resistor")
        mapped_signal_and_reference_pins = {
            item.casefold()
            for item in (
                *self.positive.connector_pins,
                *self.positive.phy_pins,
                *self.negative.connector_pins,
                *self.negative.phy_pins,
                *(item.pin for item in self.connector_reference_pins),
                *(item.pin for item in self.phy_reference_pins),
            )
        }
        if (
            self.reference_bond is not None
            and {
                self.reference_bond.side_a_pin.casefold(),
                self.reference_bond.side_b_pin.casefold(),
            }
            & mapped_signal_and_reference_pins
        ):
            raise ValueError("USB reference-bond pins must be distinct from endpoint pins")
        pins = (
            *self.positive.connector_pins,
            *self.positive.phy_pins,
            *self.negative.connector_pins,
            *self.negative.phy_pins,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("USB data pair endpoint pins must be unique")
        positive_nets = {
            self.positive.connector_net.casefold(),
            self.positive.phy_net.casefold(),
        }
        negative_nets = {
            self.negative.connector_net.casefold(),
            self.negative.phy_net.casefold(),
        }
        if positive_nets & negative_nets:
            raise ValueError("USB D+ and D- paths must use distinct declared nets")
        resistors = tuple(
            line.series_resistor.reference.casefold()
            for line in (self.positive, self.negative)
            if line.series_resistor is not None
        )
        if len(set(resistors)) != len(resistors):
            raise ValueError("USB D+ and D- paths must use distinct series resistors")
        if set(resistors) & {
            self.connector_reference.casefold(),
            self.phy_reference.casefold(),
        }:
            raise ValueError("USB data resistor cannot reuse a connector or PHY reference")
        return self


class UsbDataPathMap(StrictModel):
    """Project-authored USB connector-to-PHY topology; no universal resistor is assumed."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    interfaces: Annotated[tuple[UsbDataInterfaceRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_interfaces_and_resistors(self) -> UsbDataPathMap:
        if len({item.id.casefold() for item in self.interfaces}) != len(self.interfaces):
            raise ValueError("USB data interface IDs must be unique")
        connector_references = [item.connector_reference.casefold() for item in self.interfaces]
        if len(set(connector_references)) != len(connector_references):
            raise ValueError("USB data connector references must be unique")
        resistor_references = [
            line.series_resistor.reference.casefold()
            for item in self.interfaces
            for line in (item.positive, item.negative)
            if line.series_resistor is not None
        ]
        if len(set(resistor_references)) != len(resistor_references):
            raise ValueError("USB data series resistors must be unique across mapped paths")
        return self


class PowerPathEndpointRequirement(StrictModel):
    """One exact endpoint in a project-authored series power-path map."""

    reference: Identifier
    pin: Reference
    symbol: NonEmptyText
    footprint: NonEmptyText
    net: NetName

    @model_validator(mode="after")
    def endpoint_pin_belongs_to_component(self) -> PowerPathEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Power-path endpoint pin must belong to its declared component")
        return self


class PowerPathElementRequirement(StrictModel):
    """One fitted two-terminal component required between adjacent power nets."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    side_a_pin: Reference
    side_b_pin: Reference
    side_a_net: NetName
    side_b_net: NetName

    @model_validator(mode="after")
    def valid_component_sides(self) -> PowerPathElementRequirement:
        if self.side_a_pin.casefold() == self.side_b_pin.casefold():
            raise ValueError("Power-path component sides must use distinct pins")
        for pin in (self.side_a_pin, self.side_b_pin):
            if "." not in pin or pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("Power-path component pins must belong to the declared component")
        if self.side_a_net == self.side_b_net:
            raise ValueError("Power-path component sides must span distinct nets")
        return self


class PowerPathRequirement(StrictModel):
    """Exact ordered netlist membership for a required, component-mediated path."""

    id: Identifier
    basis: NonEmptyText
    start: PowerPathEndpointRequirement
    end: PowerPathEndpointRequirement
    elements: Annotated[tuple[PowerPathElementRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def continuous_unique_path(self) -> PowerPathRequirement:
        if self.start.pin.casefold() == self.end.pin.casefold():
            raise ValueError("Power-path endpoint pins must be distinct")
        if self.start.net == self.end.net:
            raise ValueError("A mapped series power path must span distinct endpoint nets")
        references = [
            self.start.reference.casefold(),
            self.end.reference.casefold(),
            *(item.reference.casefold() for item in self.elements),
        ]
        if len(set(references)) != len(references):
            raise ValueError("Power-path component references must be unique within a path")
        pins = [
            self.start.pin.casefold(),
            self.end.pin.casefold(),
            *(
                pin.casefold()
                for item in self.elements
                for pin in (item.side_a_pin, item.side_b_pin)
            ),
        ]
        if len(set(pins)) != len(pins):
            raise ValueError("Power-path endpoint and element pins must be unique")
        nets = [self.start.net]
        expected_net = self.start.net
        for element in self.elements:
            if element.side_a_net != expected_net:
                raise ValueError("Power-path elements must form one ordered net chain")
            expected_net = element.side_b_net
            nets.append(expected_net)
        if expected_net != self.end.net:
            raise ValueError("Power-path elements must end on the declared endpoint net")
        if len(set(nets)) != len(nets):
            raise ValueError("Power-path nets must not repeat")
        return self


class PowerPathMap(StrictModel):
    """Project-authored exact identity and pin/net map for required power paths."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    paths: Annotated[tuple[PowerPathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_path_ids(self) -> PowerPathMap:
        if len({item.id.casefold() for item in self.paths}) != len(self.paths):
            raise ValueError("Power-path IDs must be unique")
        return self


class PowerSequenceEndpointRequirement(StrictModel):
    """One project-authored regulator endpoint in a power-sequence map."""

    reference: Identifier
    pin: Reference
    symbol: NonEmptyText
    footprint: NonEmptyText
    net: NetName
    part_id: Identifier | None = None

    @model_validator(mode="after")
    def endpoint_pin_belongs_to_component(self) -> PowerSequenceEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Power-sequence endpoint pin must belong to its declared component")
        return self


class PowerSequenceStageRequirement(StrictModel):
    """Exact output and optional enable/power-good pins for one named rail stage."""

    id: Identifier
    output: PowerSequenceEndpointRequirement
    power_good: PowerSequenceEndpointRequirement | None = None
    enable: PowerSequenceEndpointRequirement | None = None
    enable_control: Literal["netlist", "firmware", "external", "always_on", "unmodeled"]
    basis: NonEmptyText

    @model_validator(mode="after")
    def stage_endpoints_match_component(self) -> PowerSequenceStageRequirement:
        endpoints = tuple(
            item for item in (self.output, self.power_good, self.enable) if item is not None
        )
        identity = (
            self.output.reference,
            self.output.symbol,
            self.output.footprint,
            self.output.part_id,
        )
        if any(
            (item.reference, item.symbol, item.footprint, item.part_id) != identity
            for item in endpoints
        ):
            raise ValueError("Power-sequence stage endpoints must identify the same component")
        pins = [item.pin.casefold() for item in endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Power-sequence stage endpoint pins must be unique")
        if self.enable_control == "netlist" and self.enable is None:
            raise ValueError(
                "A netlist-controlled power-sequence stage requires an enable endpoint"
            )
        return self


class PowerSequenceDependencyRequirement(StrictModel):
    """One required upstream power-good to downstream enable dependency."""

    id: Identifier
    predecessor_stage: Identifier
    successor_stage: Identifier
    signal_net: NetName
    basis: NonEmptyText

    @model_validator(mode="after")
    def distinct_stages(self) -> PowerSequenceDependencyRequirement:
        if self.predecessor_stage.casefold() == self.successor_stage.casefold():
            raise ValueError("A power-sequence dependency must connect two different stages")
        return self


class PowerSequenceMap(StrictModel):
    """Project-authored power-good-to-enable dependencies; no pin-name inference."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    stages: Annotated[tuple[PowerSequenceStageRequirement, ...], Field(min_length=2)]
    dependencies: Annotated[tuple[PowerSequenceDependencyRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_resolved_dependencies(self) -> PowerSequenceMap:
        stage_ids = {item.id.casefold() for item in self.stages}
        if len(stage_ids) != len(self.stages):
            raise ValueError("Power-sequence stage IDs must be unique")
        dependency_ids = [item.id.casefold() for item in self.dependencies]
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("Power-sequence dependency IDs must be unique")
        dependency_pairs = [
            (item.predecessor_stage.casefold(), item.successor_stage.casefold())
            for item in self.dependencies
        ]
        if len(set(dependency_pairs)) != len(dependency_pairs):
            raise ValueError("Power-sequence stage dependency pairs must be unique")
        stages = {item.id.casefold(): item for item in self.stages}
        for item in self.dependencies:
            predecessor = stages.get(item.predecessor_stage.casefold())
            successor = stages.get(item.successor_stage.casefold())
            if predecessor is None or successor is None:
                raise ValueError("Power-sequence dependencies must name declared stages")
            if predecessor.power_good is None:
                raise ValueError(
                    f"Power-sequence predecessor {predecessor.id} requires a mapped power-good endpoint"
                )
            if successor.enable is None:
                raise ValueError(
                    f"Power-sequence successor {successor.id} requires a mapped enable endpoint"
                )
            if predecessor.power_good.net != item.signal_net:
                raise ValueError("Power-sequence dependency net must match its power-good endpoint")
            if successor.enable.net != item.signal_net:
                raise ValueError("Power-sequence dependency net must match its enable endpoint")
        return self


class Stm32PinRequirement(StrictModel):
    """Reviewed package-pad to KiCad-pin assignment and accepted CubeMX functions."""

    port_pin: Stm32PortPin
    symbol_pin: Stm32SymbolPin
    expected_net: NetName
    accepted_ioc_signals: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    accepted_ioc_gpio_labels: tuple[NonEmptyText | None, ...] | None

    @model_validator(mode="after")
    def explicit_gpio_label_scope(self) -> Stm32PinRequirement:
        if len({item.casefold() for item in self.accepted_ioc_signals}) != len(
            self.accepted_ioc_signals
        ):
            raise ValueError("Accepted CubeMX signals must be unique")
        if self.accepted_ioc_gpio_labels is not None and len(
            {
                "<absent>" if item is None else item.casefold()
                for item in self.accepted_ioc_gpio_labels
            }
        ) != len(self.accepted_ioc_gpio_labels):
            raise ValueError("Accepted CubeMX GPIO labels must be unique")
        if any(item.upper().startswith("GPIO_") for item in self.accepted_ioc_signals) and (
            self.accepted_ioc_gpio_labels is None
        ):
            raise ValueError(
                "Generic CubeMX GPIO signals require an explicit label expectation, including an absent-label expectation"
            )
        return self


class Stm32PinExclusion(StrictModel):
    """Reasoned package pin outside the project's CubeMX signal comparison."""

    port_pin: Stm32PortPin
    reason: NonEmptyText


class Stm32CubeMxPinMap(StrictModel):
    """Project-authored full package-pad map for one exact MCU and CubeMX file."""

    id: Identifier
    basis: NonEmptyText
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_part: NonEmptyText
    ioc_path: RepositoryPath
    package_pins: Annotated[tuple[Stm32PortPin, ...], Field(min_length=1)]
    pins: Annotated[tuple[Stm32PinRequirement, ...], Field(min_length=1)]
    exclusions: tuple[Stm32PinExclusion, ...] = ()

    @model_validator(mode="after")
    def complete_unique_package_coverage(self) -> Stm32CubeMxPinMap:
        if not self.ioc_path.casefold().endswith(".ioc"):
            raise ValueError("CubeMX pin maps must name a repository-local .ioc file")
        package = [item.casefold() for item in self.package_pins]
        mapped = [item.port_pin.casefold() for item in self.pins]
        excluded = [item.port_pin.casefold() for item in self.exclusions]
        if len(set(package)) != len(package):
            raise ValueError("CubeMX package-pin inventory must be unique")
        if len(set(mapped)) != len(mapped):
            raise ValueError("CubeMX mapped package pins must be unique")
        if len(set(excluded)) != len(excluded):
            raise ValueError("CubeMX excluded package pins must be unique")
        if set(mapped) & set(excluded):
            raise ValueError("A CubeMX package pin cannot be mapped and excluded")
        if set(mapped) | set(excluded) != set(package):
            raise ValueError("Every CubeMX package pin must be mapped or explicitly excluded")
        symbol_pins = [item.symbol_pin.casefold() for item in self.pins]
        if len(set(symbol_pins)) != len(symbol_pins):
            raise ValueError("CubeMX package pins must map to unique KiCad symbol pins")
        return self


class CrystalLoadCapRequirement(StrictModel):
    """Exact identity, pins, and accepted nominal value for one crystal load capacitor."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    signal_pin: Reference
    reference_pin: Reference
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf

    @model_validator(mode="after")
    def exact_component_pins_and_range(self) -> CrystalLoadCapRequirement:
        prefix = f"{self.reference}.".casefold()
        if not self.signal_pin.casefold().startswith(
            prefix
        ) or not self.reference_pin.casefold().startswith(prefix):
            raise ValueError("Crystal load-capacitor pins must belong to the declared component")
        if self.signal_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("Crystal load-capacitor signal and reference pins must differ")
        if self.minimum_nominal_capacitance_pf > self.maximum_nominal_capacitance_pf:
            raise ValueError("Crystal load-capacitor nominal capacitance range is reversed")
        return self


class CrystalNetworkRequirement(StrictModel):
    """Reviewed Pierce crystal topology and nominal effective-load requirement."""

    oscillator_reference: Identifier
    expected_oscillator_value: NonEmptyText
    expected_oscillator_symbol: NonEmptyText
    expected_oscillator_footprint: NonEmptyText
    oscillator_input_pin: Reference
    oscillator_output_pin: Reference
    resonator_reference: Identifier
    expected_resonator_value: NonEmptyText
    expected_resonator_symbol: NonEmptyText
    expected_resonator_footprint: NonEmptyText
    resonator_input_pin: Reference
    resonator_output_pin: Reference
    load_capacitors: Annotated[
        tuple[CrystalLoadCapRequirement, ...], Field(min_length=2, max_length=2)
    ]
    reference_net: NetName
    minimum_target_load_pf: CapacitancePf
    maximum_target_load_pf: CapacitancePf
    minimum_stray_capacitance_pf: NonNegativeCapacitancePf
    maximum_stray_capacitance_pf: NonNegativeCapacitancePf
    basis: NonEmptyText

    @model_validator(mode="after")
    def unique_roles_and_ordered_ranges(self) -> CrystalNetworkRequirement:
        if self.oscillator_reference.casefold() == self.resonator_reference.casefold():
            raise ValueError("Crystal oscillator and resonator references must differ")
        if self.oscillator_input_pin.casefold() == self.oscillator_output_pin.casefold():
            raise ValueError("Crystal oscillator input and output pins must differ")
        if self.resonator_input_pin.casefold() == self.resonator_output_pin.casefold():
            raise ValueError("Crystal resonator pins must differ")
        pins = (
            self.oscillator_input_pin,
            self.oscillator_output_pin,
            self.resonator_input_pin,
            self.resonator_output_pin,
            *(pin for cap in self.load_capacitors for pin in (cap.signal_pin, cap.reference_pin)),
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Crystal network pin mappings must be unique")
        if any(
            not pin.casefold().startswith(f"{self.oscillator_reference}.".casefold())
            for pin in (self.oscillator_input_pin, self.oscillator_output_pin)
        ):
            raise ValueError("Crystal oscillator pins must belong to the declared oscillator")
        if any(
            not pin.casefold().startswith(f"{self.resonator_reference}.".casefold())
            for pin in (self.resonator_input_pin, self.resonator_output_pin)
        ):
            raise ValueError("Crystal resonator pins must belong to the declared resonator")
        references = (
            self.oscillator_reference,
            self.resonator_reference,
            *(item.reference for item in self.load_capacitors),
        )
        if len({reference.casefold() for reference in references}) != len(references):
            raise ValueError("Crystal network component references must be unique")
        if self.minimum_target_load_pf > self.maximum_target_load_pf:
            raise ValueError("Crystal target load capacitance range is reversed")
        if self.minimum_stray_capacitance_pf > self.maximum_stray_capacitance_pf:
            raise ValueError("Crystal stray capacitance range is reversed")
        return self


class CrystalNetworkMap(StrictModel):
    """Project-authored scope for deterministic crystal load-network checks."""

    basis: NonEmptyText
    networks: Annotated[tuple[CrystalNetworkRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_network_references(self) -> CrystalNetworkMap:
        references = [item.oscillator_reference.casefold() for item in self.networks]
        if len(set(references)) != len(references):
            raise ValueError("Crystal network oscillator references must be unique")
        all_components = [
            reference.casefold()
            for item in self.networks
            for reference in (
                item.oscillator_reference,
                item.resonator_reference,
                *(cap.reference for cap in item.load_capacitors),
            )
        ]
        if len(set(all_components)) != len(all_components):
            raise ValueError("A component can belong to only one mapped crystal network")
        return self


class RegulatorDividerResistorRequirement(StrictModel):
    """One explicitly mapped side of a conventional regulator feedback divider."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    feedback_pin: Reference
    rail_pin: Reference
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive

    @model_validator(mode="after")
    def local_distinct_pins_and_ordered_range(self) -> RegulatorDividerResistorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not pin.casefold().startswith(prefix) for pin in (self.feedback_pin, self.rail_pin)):
            raise ValueError("Regulator divider pins must belong to their declared resistor")
        if self.feedback_pin.casefold() == self.rail_pin.casefold():
            raise ValueError("Regulator divider feedback and rail pins must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("Regulator divider nominal resistance range is reversed")
        return self


class RegulatorFeedbackRequirement(StrictModel):
    """Reviewed identity, pin map, reference range, and output range for one regulator."""

    id: Identifier
    regulator_reference: Identifier
    expected_regulator_value: NonEmptyText
    expected_regulator_symbol: NonEmptyText
    expected_regulator_footprint: NonEmptyText
    output_pin: Reference
    expected_output_pin_function: NonEmptyText
    feedback_pin: Reference
    expected_feedback_pin_function: NonEmptyText
    output_net: NetName
    reference_net: NetName
    upper_resistor: RegulatorDividerResistorRequirement
    lower_resistor: RegulatorDividerResistorRequirement
    minimum_feedback_reference_voltage_v: ElectricalPositive
    maximum_feedback_reference_voltage_v: ElectricalPositive
    minimum_target_output_voltage_v: ElectricalPositive
    maximum_target_output_voltage_v: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def conventional_divider_is_complete(self) -> RegulatorFeedbackRequirement:
        prefix = f"{self.regulator_reference}.".casefold()
        if any(
            not pin.casefold().startswith(prefix) for pin in (self.output_pin, self.feedback_pin)
        ):
            raise ValueError("Regulator output and feedback pins must belong to the regulator")
        if self.output_pin.casefold() == self.feedback_pin.casefold():
            raise ValueError("Regulator output and feedback pins must differ")
        references = (
            self.regulator_reference,
            self.upper_resistor.reference,
            self.lower_resistor.reference,
        )
        if len({reference.casefold() for reference in references}) != len(references):
            raise ValueError("Regulator and divider component references must be unique")
        pins = (
            self.output_pin,
            self.feedback_pin,
            self.upper_resistor.feedback_pin,
            self.upper_resistor.rail_pin,
            self.lower_resistor.feedback_pin,
            self.lower_resistor.rail_pin,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Regulator feedback pin mappings must be unique")
        if self.output_net.casefold() == self.reference_net.casefold():
            raise ValueError("Regulator output and reference nets must differ")
        if self.minimum_feedback_reference_voltage_v > self.maximum_feedback_reference_voltage_v:
            raise ValueError("Regulator feedback-reference voltage range is reversed")
        if self.minimum_target_output_voltage_v > self.maximum_target_output_voltage_v:
            raise ValueError("Regulator target output voltage range is reversed")
        return self


class RegulatorFeedbackMap(StrictModel):
    """Project-authored scope for deterministic adjustable-regulator checks."""

    basis: NonEmptyText
    regulators: Annotated[tuple[RegulatorFeedbackRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_regulators_and_components(self) -> RegulatorFeedbackMap:
        if len({item.id.casefold() for item in self.regulators}) != len(self.regulators):
            raise ValueError("Regulator feedback IDs must be unique")
        all_components = [
            reference.casefold()
            for item in self.regulators
            for reference in (
                item.regulator_reference,
                item.upper_resistor.reference,
                item.lower_resistor.reference,
            )
        ]
        if len(set(all_components)) != len(all_components):
            raise ValueError("A component can belong to only one regulator feedback map")
        return self


class RcFilterRequirement(StrictModel):
    """Reviewed identity, topology, values, and corner range for one RC low-pass."""

    id: Identifier
    resistor_reference: ResistorReference
    expected_resistor_symbol: NonEmptyText
    expected_resistor_footprint: NonEmptyText
    resistor_first_pin: Reference
    resistor_second_pin: Reference
    capacitor_reference: Identifier
    expected_capacitor_symbol: NonEmptyText
    expected_capacitor_footprint: NonEmptyText
    capacitor_signal_pin: Reference
    capacitor_reference_pin: Reference
    input_net: NetName
    filtered_net: NetName
    reference_net: NetName
    minimum_nominal_resistance_ohms: ElectricalPositive
    maximum_nominal_resistance_ohms: ElectricalPositive
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf
    minimum_target_corner_hz: ElectricalPositive
    maximum_target_corner_hz: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def complete_first_order_map(self) -> RcFilterRequirement:
        resistor_prefix = f"{self.resistor_reference}.".casefold()
        capacitor_prefix = f"{self.capacitor_reference}.".casefold()
        if any(
            not pin.casefold().startswith(resistor_prefix)
            for pin in (self.resistor_first_pin, self.resistor_second_pin)
        ):
            raise ValueError("RC filter resistor pins must belong to the declared resistor")
        if any(
            not pin.casefold().startswith(capacitor_prefix)
            for pin in (self.capacitor_signal_pin, self.capacitor_reference_pin)
        ):
            raise ValueError("RC filter capacitor pins must belong to the declared capacitor")
        pins = (
            self.resistor_first_pin,
            self.resistor_second_pin,
            self.capacitor_signal_pin,
            self.capacitor_reference_pin,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("RC filter pin mappings must be unique")
        if (
            len(
                {
                    self.input_net.casefold(),
                    self.filtered_net.casefold(),
                    self.reference_net.casefold(),
                }
            )
            != 3
        ):
            raise ValueError("RC filter input, filtered, and reference nets must be distinct")
        if self.resistor_reference.casefold() == self.capacitor_reference.casefold():
            raise ValueError("RC filter resistor and capacitor references must differ")
        if self.minimum_nominal_resistance_ohms > self.maximum_nominal_resistance_ohms:
            raise ValueError("RC filter resistance range is reversed")
        if self.minimum_nominal_capacitance_pf > self.maximum_nominal_capacitance_pf:
            raise ValueError("RC filter capacitance range is reversed")
        if self.minimum_target_corner_hz > self.maximum_target_corner_hz:
            raise ValueError("RC filter target corner range is reversed")
        return self


class RcFilterMap(StrictModel):
    """Project-authored scope for deterministic first-order RC filter checks."""

    filters: Annotated[tuple[RcFilterRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_filter_parts(self) -> RcFilterMap:
        if len({item.id.casefold() for item in self.filters}) != len(self.filters):
            raise ValueError("RC filter IDs must be unique")
        references = [
            reference.casefold()
            for item in self.filters
            for reference in (item.resistor_reference, item.capacitor_reference)
        ]
        if len(set(references)) != len(references):
            raise ValueError("A component can belong to only one mapped RC filter")
        return self


class PcbDecouplingCapacitor(StrictModel):
    """Exact capacitor pin mapping eligible to decouple one supply pin."""

    reference: Identifier
    footprint: NonEmptyText
    supply_pad: Reference
    return_pad: Reference

    @model_validator(mode="after")
    def exact_capacitor_pads(self) -> PcbDecouplingCapacitor:
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in (self.supply_pad, self.return_pad)):
            raise ValueError("Decoupling capacitor pads must belong to the declared component")
        if self.supply_pad.casefold() == self.return_pad.casefold():
            raise ValueError("Decoupling capacitor supply and return pads must differ")
        return self


class PcbDecouplingRequirement(StrictModel):
    """Project-reviewed IC power/return pin and candidate capacitor placement rule."""

    id: Identifier
    basis: NonEmptyText
    ic_reference: Identifier
    ic_footprint: NonEmptyText
    supply_pad: Reference
    return_pad: Reference
    supply_net: NetName
    return_net: NetName
    capacitors: Annotated[tuple[PcbDecouplingCapacitor, ...], Field(min_length=1)]
    selection: Literal["any", "all"] = "any"
    max_distance_um: PositiveCount | None = None
    max_return_via_distance_um: PositiveCount | None = None

    @model_validator(mode="after")
    def exact_supply_mapping(self) -> PcbDecouplingRequirement:
        prefix = f"{self.ic_reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in (self.supply_pad, self.return_pad)):
            raise ValueError("Decoupling IC pads must belong to the declared component")
        if self.supply_pad.casefold() == self.return_pad.casefold():
            raise ValueError("Decoupling IC supply and return pads must differ")
        if self.supply_net.casefold() == self.return_net.casefold():
            raise ValueError("Decoupling supply and return nets must differ")
        if len({item.reference.casefold() for item in self.capacitors}) != len(self.capacitors):
            raise ValueError("A decoupling requirement cannot repeat a capacitor reference")
        return self


class PcbDecouplingMap(StrictModel):
    """Explicit per-project PCB decoupling scopes; no universal distance is assumed."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbDecouplingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_supply_pins(self) -> PcbDecouplingMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB decoupling requirement IDs must be unique")
        supply_pads = [item.supply_pad.casefold() for item in self.requirements]
        if len(set(supply_pads)) != len(supply_pads):
            raise ValueError("An IC supply pad can belong to only one decoupling requirement")
        return self


class PcbProtectionPathRequirement(StrictModel):
    """Project-reviewed connector-to-protector pad path and reference-via screen."""

    id: Identifier
    connector_reference: Identifier
    connector_footprint: NonEmptyText
    connector_signal_pad: Reference
    protection_reference: Identifier
    protection_footprint: NonEmptyText
    protection_signal_pad: Reference
    protection_reference_pad: Reference
    signal_net: NetName
    reference_net: NetName
    max_entry_distance_um: PositiveCount | None = None
    minimum_reference_vias: PositiveCount | None = None
    reference_via_radius_um: PositiveCount | None = None

    @model_validator(mode="after")
    def exact_protection_pad_mapping(self) -> PcbProtectionPathRequirement:
        if not self.connector_signal_pad.casefold().startswith(
            f"{self.connector_reference}.".casefold()
        ):
            raise ValueError("PCB protection connector pad must belong to its connector")
        prefix = f"{self.protection_reference}.".casefold()
        if any(
            not pad.casefold().startswith(prefix)
            for pad in (self.protection_signal_pad, self.protection_reference_pad)
        ):
            raise ValueError("PCB protection pads must belong to the declared device")
        if self.protection_signal_pad.casefold() == self.protection_reference_pad.casefold():
            raise ValueError("PCB protection signal and reference pads must differ")
        if self.signal_net.casefold() == self.reference_net.casefold():
            raise ValueError("PCB protection signal and reference nets must differ")
        if (self.minimum_reference_vias is None) != (self.reference_via_radius_um is None):
            raise ValueError(
                "PCB reference-via count and radius limits must be configured together"
            )
        if self.max_entry_distance_um is None and self.minimum_reference_vias is None:
            raise ValueError(
                "PCB protection path needs at least one project-authored geometry limit"
            )
        return self


class PcbProtectionPathMap(StrictModel):
    """Explicit PCB pads and project-selected limits for external protection paths."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbProtectionPathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_path_ids_and_endpoints(self) -> PcbProtectionPathMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB protection path IDs must be unique")
        endpoints = [
            (item.connector_signal_pad.casefold(), item.protection_signal_pad.casefold())
            for item in self.requirements
        ]
        if len(set(endpoints)) != len(endpoints):
            raise ValueError("PCB protection connector and signal-pad pairs must be unique")
        return self


class PcbProtectionPathEntry(StrictModel):
    """Native pad, component, and connected-via evidence for one protection path."""

    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    connector_signal_pad: Reference
    protection_signal_pad: Reference
    protection_reference_pad: Reference
    signal_net: NetName
    reference_net: NetName
    expected_connector_footprint: NonEmptyText
    observed_connector_footprint: NonEmptyText | None
    expected_protection_footprint: NonEmptyText
    observed_protection_signal_footprint: NonEmptyText | None
    observed_protection_reference_footprint: NonEmptyText | None
    observed_connector_signal_net: NetName | None
    observed_protection_signal_net: NetName | None
    observed_protection_reference_net: NetName | None
    connector_signal_fitted: bool | None
    protection_signal_fitted: bool | None
    protection_reference_fitted: bool | None
    native_signal_path_connected: bool
    connector_to_protection_distance_nm: NonNegativeCount | None
    connector_to_protection_distance_squared_nm2: NonNegativeCount | None
    connected_reference_via_count: NonNegativeCount
    reference_vias_within_radius: NonNegativeCount | None
    reference_via_radius_um: PositiveCount | None
    nearest_reference_via_id: Digest | None
    nearest_reference_via_distance_nm: NonNegativeCount | None
    max_entry_distance_um: PositiveCount | None
    minimum_reference_vias: PositiveCount | None
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_measured_distances(self) -> PcbProtectionPathEntry:
        if (self.connector_to_protection_distance_nm is None) != (
            self.connector_to_protection_distance_squared_nm2 is None
        ):
            raise ValueError("PCB protection entry distance fields must be present together")
        if (self.nearest_reference_via_id is None) != (
            self.nearest_reference_via_distance_nm is None
        ):
            raise ValueError("PCB protection via identity and distance must be present together")
        if self.minimum_reference_vias is None:
            if (
                self.reference_via_radius_um is not None
                or self.reference_vias_within_radius is not None
            ):
                raise ValueError("PCB protection via-radius evidence requires a configured minimum")
        elif self.reference_via_radius_um is None:
            raise ValueError("Configured PCB protection via minimum needs its authored radius")
        elif self.reference_vias_within_radius is None and not self.issues:
            raise ValueError("Complete PCB protection evidence needs a measured via-radius count")
        if self.status == "COMPLETE" and self.issues:
            raise ValueError("Complete PCB protection path cannot contain issues")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete PCB protection path must explain the evidence gap")
        return self


class PcbProtectionPathCoverageReport(StrictModel):
    """Source-bound native PCB evidence for configured external protection paths."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[PcbProtectionPathEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbProtectionPathCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(
            item is None
            for item in (
                self.map_sha256,
                self.board_path,
                self.board_sha256,
                self.snapshot_path,
                self.snapshot_sha256,
                self.probe_sha256,
                self.kicad_version,
                self.image,
                self.netlist_sha256,
            )
        ):
            raise ValueError("Scanned PCB protection path evidence must bind all native sources")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB protection path evidence must explain the source gap")
        return self


class PcbKeepoutRequirement(StrictModel):
    """Reviewed identity and exact native signature for one PCB keepout rule area."""

    id: Identifier
    basis: NonEmptyText
    name: NonEmptyText
    geometry_sha256: Digest
    layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    forbids_tracks: bool
    forbids_vias: bool
    forbids_pads: bool
    forbids_zone_fills: bool
    forbids_footprints: bool

    @model_validator(mode="after")
    def unique_layers(self) -> PcbKeepoutRequirement:
        if len({item.casefold() for item in self.layers}) != len(self.layers):
            raise ValueError("PCB keepout requirement layers must be unique")
        return self


class PcbKeepoutMap(StrictModel):
    """Project-owned signatures for reviewed copper keepout rule areas."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbKeepoutRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_keepouts(self) -> PcbKeepoutMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB keepout requirement IDs must be unique")
        if len({item.name.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A named PCB keepout can be mapped only once")
        return self


class PcbKeepoutCoverageEntry(StrictModel):
    """Comparison between one reviewed keepout signature and a native rule area."""

    id: Identifier
    basis: NonEmptyText
    name: NonEmptyText
    expected_geometry_sha256: Digest
    observed_uuid: NativePcbUuid | None = None
    observed_geometry_sha256: Digest | None = None
    expected_layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    observed_layers: tuple[NonEmptyText, ...] = ()
    expected_forbids_tracks: bool
    expected_forbids_vias: bool
    expected_forbids_pads: bool
    expected_forbids_zone_fills: bool
    expected_forbids_footprints: bool
    observed_forbids_tracks: bool | None = None
    observed_forbids_vias: bool | None = None
    observed_forbids_pads: bool | None = None
    observed_forbids_zone_fills: bool | None = None
    observed_forbids_footprints: bool | None = None
    status: Literal["COMPLETE", "INCOMPLETE"]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def status_matches_observation(self) -> PcbKeepoutCoverageEntry:
        observed_flags = (
            self.observed_forbids_tracks,
            self.observed_forbids_vias,
            self.observed_forbids_pads,
            self.observed_forbids_zone_fills,
            self.observed_forbids_footprints,
        )
        if self.status == "COMPLETE":
            if self.issues or any(item is None for item in observed_flags):
                raise ValueError("Complete PCB keepout coverage needs full matching evidence")
            expected_layers = {item.casefold() for item in self.expected_layers}
            observed_layers = {item.casefold() for item in self.observed_layers}
            expected_flags = (
                self.expected_forbids_tracks,
                self.expected_forbids_vias,
                self.expected_forbids_pads,
                self.expected_forbids_zone_fills,
                self.expected_forbids_footprints,
            )
            if (
                self.observed_geometry_sha256 != self.expected_geometry_sha256
                or observed_layers != expected_layers
                or observed_flags != expected_flags
            ):
                raise ValueError("Complete PCB keepout coverage must match its exact signature")
        elif not self.issues:
            raise ValueError("Incomplete PCB keepout coverage must explain its gap")
        return self


class PcbKeepoutCoverageReport(StrictModel):
    """Source-bound comparison of reviewed keepout signatures with native rule areas."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[PcbKeepoutCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbKeepoutCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(
            item is None
            for item in (
                self.map_sha256,
                self.board_path,
                self.board_sha256,
                self.snapshot_path,
                self.snapshot_sha256,
                self.probe_sha256,
                self.kicad_version,
                self.image,
                self.netlist_sha256,
            )
        ):
            raise ValueError("Scanned PCB keepout evidence must bind all source and tool inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned PCB keepout coverage must contain every mapped area")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("PCB keepout report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB keepout coverage must explain its evidence gap")
        return self


class ConnectorReturnDistributionRequirement(StrictModel):
    """Project-owned signal/return contact ratio for one reviewed interface."""

    id: Identifier
    interface_id: Identifier
    minimum_signal_pin_count: Annotated[int, Field(ge=1)]
    maximum_signal_to_return_ratio: ElectricalPositive
    basis: NonEmptyText


class ConnectorReturnDistributionMap(StrictModel):
    """Opt-in thresholds for explicitly role-classified interfaces."""

    requirements: Annotated[tuple[ConnectorReturnDistributionRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements(self) -> ConnectorReturnDistributionMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Connector return-distribution IDs must be unique")
        interfaces = [item.interface_id.casefold() for item in self.requirements]
        if len(set(interfaces)) != len(interfaces):
            raise ValueError("Connector return-distribution interfaces must be unique")
        return self


class ComponentRolePin(StrictModel):
    """One exact native pin signature used to classify a custom component."""

    number: NonEmptyText
    function: NonEmptyText
    electrical_type: NonEmptyText


class ComponentRoleBinding(StrictModel):
    """Project-reviewed role for one exact part, symbol, footprint and pin set."""

    part_id: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    role: Literal["led", "capacitor"]
    pins: Annotated[tuple[ComponentRolePin, ...], Field(min_length=2)]
    basis: NonEmptyText

    @model_validator(mode="after")
    def complete_unique_pin_signature(self) -> ComponentRoleBinding:
        numbers = tuple(item.number for item in self.pins)
        if len(numbers) != 2 or len(set(numbers)) != len(numbers):
            raise ValueError("Component role maps require exactly two unique native pins")
        if self.role == "capacitor" and any(
            item.electrical_type.casefold() != "passive" for item in self.pins
        ):
            raise ValueError("The capacitor role requires two native passive pins")
        return self


class ComponentRoleMap(StrictModel):
    """Opt-in project classification for exact custom component identities."""

    entries: Annotated[tuple[ComponentRoleBinding, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_part_identities(self) -> ComponentRoleMap:
        identifiers = tuple(item.part_id.casefold() for item in self.entries)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Component role-map PART_ID entries must be unique")
        return self


class ComplementaryPinFunctionAlias(StrictModel):
    """Project-owned pin-function aliases for one exact KiCad symbol pair."""

    symbol: NonEmptyText
    family: NonEmptyText
    positive_functions: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    negative_functions: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    basis: NonEmptyText

    @model_validator(mode="after")
    def unambiguous_function_aliases(self) -> ComplementaryPinFunctionAlias:
        def key(value: str) -> str:
            return re.sub(r"[\s_./]", "", value.casefold()).replace("−", "-")

        positive = tuple(key(value) for value in self.positive_functions)
        negative = tuple(key(value) for value in self.negative_functions)
        if any(not value for value in (*positive, *negative)):
            raise ValueError("Complementary pin-function aliases must contain a letter or symbol")
        if len(set(positive)) != len(positive) or len(set(negative)) != len(negative):
            raise ValueError("Complementary pin-function aliases must be unique within each side")
        if set(positive) & set(negative):
            raise ValueError("A complementary pin-function alias cannot name both pair sides")
        return self


class ComplementaryPinFunctionAliasMap(StrictModel):
    """Opt-in function aliases scoped to exact native KiCad symbol identities."""

    entries: Annotated[tuple[ComplementaryPinFunctionAlias, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_symbols_families_and_functions(self) -> ComplementaryPinFunctionAliasMap:
        identities = tuple((item.symbol, item.family.casefold()) for item in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("Complementary pin-function alias symbol/family pairs must be unique")
        aliases: set[tuple[str, str]] = set()
        for item in self.entries:
            for function in (*item.positive_functions, *item.negative_functions):
                key = re.sub(r"[\s_./]", "", function.casefold()).replace("−", "-")
                identity = (item.symbol, key)
                if identity in aliases:
                    raise ValueError(
                        "A symbol pin-function alias can belong to only one pair family and side"
                    )
                aliases.add(identity)
        return self


class DesignLintPolicy(StrictModel):
    """Project-owned review decisions; no observed netlist values become requirements."""

    schema_version: Literal["1"] = "1"
    rules: tuple[DesignLintRuleOverride, ...] = ()
    ignores: tuple[DesignLintIgnore, ...] = ()
    component_role_map: ComponentRoleMap | None = None
    complementary_pin_function_alias_map: ComplementaryPinFunctionAliasMap | None = None
    stm32_pin_maps: tuple[Stm32CubeMxPinMap, ...] = ()
    i2c_address_map: I2cAddressMap | None = None
    external_protection_map: ExternalProtectionMap | None = None
    usb_data_path_map: UsbDataPathMap | None = None
    power_path_map: PowerPathMap | None = None
    power_sequence_map: PowerSequenceMap | None = None
    crystal_network_map: CrystalNetworkMap | None = None
    regulator_feedback_map: RegulatorFeedbackMap | None = None
    rc_filter_map: RcFilterMap | None = None
    connector_return_distribution_map: ConnectorReturnDistributionMap | None = None
    pcb_decoupling_map: PcbDecouplingMap | None = None
    pcb_protection_path_map: PcbProtectionPathMap | None = None
    pcb_track_width_map: PcbTrackWidthMap | None = None
    pcb_reference_plane_map: PcbReferencePlaneMap | None = None
    pcb_switching_loop_map: PcbSwitchingLoopMap | None = None
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None
    pcb_signal_path_rule_map: PcbSignalPathRuleMap | None = None
    pcb_keepout_map: PcbKeepoutMap | None = None
    pcb_rf_module_antenna_map: PcbRfModuleAntennaMap | None = None

    @model_validator(mode="after")
    def unique_decisions(self) -> DesignLintPolicy:
        if len({item.rule_id for item in self.rules}) != len(self.rules):
            raise ValueError("design_lint rule overrides must be unique")
        if len({item.fingerprint for item in self.ignores}) != len(self.ignores):
            raise ValueError("design_lint ignores must have unique fingerprints")
        if len({item.id.casefold() for item in self.stm32_pin_maps}) != len(self.stm32_pin_maps):
            raise ValueError("STM32 CubeMX pin-map IDs must be unique")
        if len({item.reference.casefold() for item in self.stm32_pin_maps}) != len(
            self.stm32_pin_maps
        ):
            raise ValueError("An MCU reference can appear in only one CubeMX pin map")
        return self


class ConnectorInterfaceReview(StrictModel):
    """Project-owned pinout coverage decision for one schematic component."""

    reference: Identifier
    disposition: Literal["interface", "not_applicable"]
    basis: NonEmptyText
    interface_id: Identifier | None = None
    pin_map: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    unlisted_pin_reasons: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: NonEmptyText | None = None

    @model_validator(mode="after")
    def complete_disposition(self) -> ConnectorInterfaceReview:
        if self.disposition == "interface":
            if self.interface_id is None or not self.pin_map:
                raise ValueError("Interface review needs an interface ID and a pin map")
            targets = tuple(self.pin_map.values())
            if len(set(targets)) != len(targets):
                raise ValueError("Interface pin map must use each component pin at most once")
            if set(targets) & set(self.unlisted_pin_reasons):
                raise ValueError("A component pin cannot be mapped and listed as unlisted")
        elif (
            self.interface_id is not None
            or self.pin_map
            or self.unlisted_pin_reasons
            or self.peer_assignment_group is not None
            or self.peer_assignment_basis is not None
        ):
            raise ValueError("Not-applicable review cannot contain interface or peer-group data")
        if (self.peer_assignment_group is None) != (self.peer_assignment_basis is None):
            raise ValueError("Connector peer-assignment groups need a review basis")
        return self


class ConnectorInventoryReview(StrictModel):
    """Project-owned basis for a complete connector-reference inventory review."""

    basis: NonEmptyText


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
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
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
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
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


class ProductIndexEntry(StrictModel):
    id: Identifier
    path: RepositoryPath
    project_ids: tuple[Identifier, ...]


class ProductIndex(StrictModel):
    schema_version: Literal["1"]
    products: tuple[ProductIndexEntry, ...]

    @model_validator(mode="after")
    def unique_product_ids(self) -> ProductIndex:
        ids = [product.id.casefold() for product in self.products]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate product IDs in catalog/products.json")
        return self


class AssemblyKind(str, Enum):
    PURCHASED = "purchased"
    BUILT = "built"
    PHANTOM = "phantom"


class AssemblyMember(StrictModel):
    ref: Identifier
    item: Reference
    quantity: PositiveCount


class Assembly(StrictModel):
    id: Identifier
    revision: Identifier
    kind: AssemblyKind
    members: tuple[AssemblyMember, ...]
    purchase_part: Reference | None = None
    project_id: Identifier | None = None


class TerminalKind(str, Enum):
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    LOGICAL = "logical"


class Terminal(StrictModel):
    id: Identifier
    instance: Reference
    pin: Identifier
    kind: TerminalKind
    exclusive: bool
    interface_id: Identifier | None = None
    interface_pin: NonEmptyText | None = None


class ConnectionKind(str, Enum):
    ELECTRICAL = "electrical"
    FUNCTIONAL = "functional"
    MECHANICAL = "mechanical"
    PROTOCOL = "protocol"


class Connection(StrictModel):
    id: Identifier
    kind: ConnectionKind
    from_terminal: Identifier = Field(alias="from")
    to_terminal: Identifier = Field(alias="to")
    variants: tuple[Identifier, ...]
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    harness: Identifier | None = None


class Variant(StrictModel):
    id: Identifier
    revision: Identifier
    exclude: tuple[Reference, ...]
    board_variants: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)


class EvidenceKind(str, Enum):
    DESIGN_NOTE = "design_note"
    OBSERVATION = "observation"
    DATASHEET = "datasheet"
    TEST_REPORT = "test_report"


class Evidence(StrictModel):
    id: Identifier
    kind: EvidenceKind
    path: RepositoryPath
    sha256: Digest
    claims: tuple[Identifier, ...]


class Harness(StrictModel):
    id: Identifier
    revision: Identifier
    instance: Reference
    length_mm: PositiveMeasure
    conductor_area_mm2: PositiveMeasure
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class MechanicalHandoff(StrictModel):
    id: Identifier
    instances: tuple[Reference, ...]
    units: Literal["mm"]
    datum: NonEmptyText
    drawing: RepositoryPath
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    open_items: tuple[NonEmptyText, ...]


class ProductRecord(StrictModel):
    schema_version: Literal["1"]
    id: Identifier
    revision: Identifier
    maturity: Literal["training", "engineering_review", "prototype", "pilot", "production"]
    root_assembly: Identifier
    assemblies: tuple[Assembly, ...]
    terminals: tuple[Terminal, ...]
    connections: tuple[Connection, ...]
    variants: tuple[Variant, ...]
    evidence: tuple[Evidence, ...]
    harnesses: tuple[Harness, ...]
    mechanical: tuple[MechanicalHandoff, ...]
    blocking_issues: tuple[NonEmptyText, ...]


class PolicyIssue(StrictModel):
    code: NonEmptyText
    location: NonEmptyText
    message: NonEmptyText


class ProductPolicyReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["PRODUCT_POLICY"] = "PRODUCT_POLICY"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    products: tuple[Identifier, ...]
    open_items: Mapping[Identifier, tuple[NonEmptyText, ...]]
    issues: tuple[PolicyIssue, ...]


class Occurrence(StrictModel):
    item: Reference
    quantity: PositiveCount


class BomRow(StrictModel):
    part_id: Identifier
    revision: Identifier
    quantity: PositiveCount
    unit: Literal["each"]
    instances: NonEmptyText
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    disposition: Literal["NOT FOR MANUFACTURE"]


class HarnessScheduleRow(StrictModel):
    """One non-procurement harness schedule row for a selected product variant."""

    harness_id: Identifier
    revision: Identifier
    instance: Reference
    length_mm: PositiveMeasure
    conductor_area_mm2: PositiveMeasure
    electrical_connection_ids: tuple[Identifier, ...]
    endpoint_terminal_ids: tuple[Identifier, ...]
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    disposition: Literal["NOT FOR MANUFACTURE"]


class HarnessSchedule(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    rows: tuple[HarnessScheduleRow, ...]


class ElectricalConnectionView(StrictModel):
    id: Identifier
    from_terminal: Terminal = Field(alias="from")
    to_terminal: Terminal = Field(alias="to")
    harness: Identifier | None = None
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class ElectricalView(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    connections: tuple[ElectricalConnectionView, ...]


class SystemConnectionView(StrictModel):
    id: Identifier
    kind: ConnectionKind
    from_terminal: Terminal = Field(alias="from")
    to_terminal: Terminal = Field(alias="to")
    harness: Identifier | None = None
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class SystemView(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    connections: tuple[SystemConnectionView, ...]


class SnapshotManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    kind: Literal["engineering_review_snapshot"] = "engineering_review_snapshot"
    build_authorized: Literal[False] = False
    commit: NonEmptyText
    working_tree_clean: bool
    git_status: str
    python_version: NonEmptyText
    policy_version: NonEmptyText
    products: tuple[Identifier, ...]
    checks: Mapping[Identifier, NonEmptyText]
    sources_sha256: Mapping[RepositoryPath, Digest]
    artifacts_sha256: Mapping[RepositoryPath, Digest]


class NetlistIdentityReport(StrictModel):
    status: Literal["PASS", "NOT_APPLICABLE"]
    assemblies: tuple[Identifier, ...] = ()
    components: int = 0
    reason: NonEmptyText | None = None


class SnapshotVerification(StrictModel):
    status: Literal["PASS"]
    artifacts: PositiveCount
    build_authorized: Literal[False] = False
    scope: Literal["artifact_integrity_only_not_authenticity_or_source_reconstruction"]


class ReleaseClass(str, Enum):
    ENGINEERING_REVIEW = "engineering_review"
    PROTOTYPE = "prototype"
    PILOT = "pilot"
    PRODUCTION = "production"


class ReleaseAssurancePolicy(StrictModel):
    release_class: ReleaseClass
    minimum_assurance: Assurance


class ReleasePoliciesCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    policies: tuple[ReleaseAssurancePolicy, ...]


class ReleaseStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"


class DeviationStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    CLOSED = "closed"


class ReleaseVariant(StrictModel):
    product: Identifier
    product_revision: Identifier
    variant: Identifier
    variant_revision: Identifier


class ReleaseLibrary(StrictModel):
    id: Identifier
    version: NonEmptyText
    provenance_sha256: Digest
    licensing_sha256: Digest


class ReleaseInterface(StrictModel):
    id: Identifier
    revision: NonEmptyText


class ReleaseArtifactKind(str, Enum):
    REVIEW_RECORD = "review_record"
    BOM = "bom"
    SCHEMATIC_EXPORT = "schematic_export"
    PCB_EXPORT = "pcb_export"
    HARNESS_EXPORT = "harness_export"
    VALIDATION_REPORT = "validation_report"
    FABRICATION_PACKAGE = "fabrication_package"
    ASSEMBLY_PACKAGE = "assembly_package"


class ReleaseArtifact(StrictModel):
    id: Identifier
    kind: ReleaseArtifactKind
    path: RepositoryPath
    sha256: Digest
    intended_use: NonEmptyText


class ReleaseDeviation(StrictModel):
    id: Identifier
    scope: tuple[Identifier, ...]
    owner: NonEmptyText
    reason: NonEmptyText
    status: DeviationStatus
    expires: date
    evidence: tuple[Identifier, ...]


class ReleaseApproval(StrictModel):
    electrical_reviewer: NonEmptyText
    mechanical_reviewer: NonEmptyText | None = None
    integrator: NonEmptyText
    release_authority: NonEmptyText | None = None
    approved_at: date
    evidence: tuple[Identifier, ...]


class SourceState(StrictModel):
    """Observed Git identity and source bytes, never a caller-supplied assertion."""

    commit: GitCommit | None = None
    clean: bool = False
    files_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)


class EvidenceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest


class ReleaseEvidence(StrictModel):
    portable: EvidenceFile
    native: Mapping[Identifier, EvidenceFile]
    exports: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)
    electrical: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)


class ReleaseManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    release_id: Identifier
    release_class: ReleaseClass
    status: ReleaseStatus
    source_commit: GitCommit
    source_tag: NonEmptyText | None = None
    toolchain_id: Identifier
    projects: tuple[Identifier, ...] = ()
    variants: tuple[ReleaseVariant, ...] = ()
    libraries: tuple[ReleaseLibrary, ...]
    interfaces: tuple[ReleaseInterface, ...]
    checks: Mapping[Identifier, Literal["PASS", "NOT_APPLICABLE"]] = Field(default_factory=dict)
    evidence: ReleaseEvidence | None = None
    artifacts: tuple[ReleaseArtifact, ...]
    deviations: tuple[ReleaseDeviation, ...] = ()
    approval: ReleaseApproval | None = None


class ReleaseReadinessReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["RELEASE_READINESS"] = "RELEASE_READINESS"
    build_authorized: Literal[False] = False
    release_id: Identifier
    release_class: ReleaseClass
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class RepositoryPolicyReport(StrictModel):
    lane: Literal["REPOSITORY_POLICY"] = "REPOSITORY_POLICY"
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]


class GenerationReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]


class GovernanceRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    branch: NonEmptyText
    required_status_checks: tuple[NonEmptyText, ...]
    authors: tuple[NonEmptyText, ...]
    reviewers: tuple[NonEmptyText, ...]
    integrators: tuple[NonEmptyText, ...]
    release_authorities: tuple[NonEmptyText, ...]
    branch_protection_evidence: tuple[NonEmptyText, ...]
    branch_protection_verified_at: NonEmptyText


class TeamPolicy(StrictModel):
    """Reviewed team choices, kept separately from project-specific assignments."""

    schema_version: Literal["1"] = "1"
    minimum_actors: Annotated[int, Field(ge=1)] = 2
    independent_review: bool = True
    required_status_checks: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)] = (
        "Template acceptance",
    )
    rationale: NonEmptyText


class HostedGovernanceCheck(StrictModel):
    """One observed hosted control, with uncertainty preserved."""

    id: Identifier
    status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    expected: NonEmptyText
    observed: NonEmptyText
    source: NonEmptyText | None = None
    next_action: NonEmptyText | None = None


class HostedGovernanceReport(StrictModel):
    """Read-only API observations, never team or hardware approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["HOSTED_GOVERNANCE_AUDIT"] = "HOSTED_GOVERNANCE_AUDIT"
    build_authorized: Literal[False] = False
    repository: NonEmptyText | None = None
    default_branch: NonEmptyText | None = None
    required_status_checks: tuple[NonEmptyText, ...] = ()
    hosted_controls_status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    checks: tuple[HostedGovernanceCheck, ...]
    next_actions: tuple[NonEmptyText, ...] = ()


class GovernanceLintReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["STATIC_GOVERNANCE_LINT"] = "STATIC_GOVERNANCE_LINT"
    projects: tuple[Identifier, ...]
    issues: tuple[NonEmptyText, ...]
    status: Literal["PASS", "FAIL"]


class ToolchainAssessment(StrictModel):
    toolchain_id: Identifier
    expected_version: NonEmptyText
    observed_version: NonEmptyText | None
    desktop_editing_allowed: bool
    status: Literal["PASS", "FAIL"]
    next_action: NonEmptyText


class MatrixEntry(StrictModel):
    project: Identifier
    image: NonEmptyText
    kicad_version: NonEmptyText
    fault_probes: bool = False
    electrical: bool = False


class CiMatrix(StrictModel):
    include: tuple[MatrixEntry, ...]


class ImpactPlan(StrictModel):
    """Fail-closed scope for a changed-path development check."""

    schema_version: Literal["1"] = "1"
    scope: Literal["docs", "focused", "full"]
    projects: tuple[Identifier, ...]
    changed_paths: tuple[str, ...]
    reasons: tuple[NonEmptyText, ...]
    docs_changed: bool = False


class CommandEvidence(StrictModel):
    argv: tuple[NonEmptyText, ...]
    started_utc: NonEmptyText
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class ReleaseExportReport(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    source: SourceState
    toolchain_id: Identifier
    settings: ReleaseExportSettings
    assembly_variant: NonEmptyText | None = None
    commands: Mapping[Identifier, CommandEvidence]
    artifacts_sha256: Mapping[RepositoryPath, Digest]
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...] = ()


class ReleasePackageIndex(StrictModel):
    schema_version: Literal["1"] = "1"
    source_commit: GitCommit
    manifest: RepositoryPath
    files_sha256: Mapping[RepositoryPath, Digest]


class ReleasePackageReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source_commit: GitCommit
    package: str
    package_sha256: Digest
    manifest: RepositoryPath
    build_authorized: Literal[False] = False


class DocumentationException(StrictModel):
    """A reviewed, path-scoped and time-bounded documentation-policy waiver."""

    id: Identifier
    code: Identifier
    path: RepositoryPath
    reason: NonEmptyText
    expires: date


class DocumentationPolicy(StrictModel):
    """Repository-owned Markdown graph roots and narrow policy exceptions."""

    schema_version: Literal["1"] = "1"
    roots: tuple[RepositoryPath, ...]
    documentation_namespaces: tuple[RepositoryPath, ...] = ()
    exceptions: tuple[DocumentationException, ...] = ()


class DocumentationIssue(StrictModel):
    code: Identifier
    path: RepositoryPath
    line: PositiveCount
    message: NonEmptyText


class DocumentationPolicyReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["MARKDOWN_REPOSITORY_POLICY"] = "MARKDOWN_REPOSITORY_POLICY"
    roots: tuple[RepositoryPath, ...]
    documents: NonNegativeCount
    issues: tuple[DocumentationIssue, ...]
    status: Literal["PASS", "FAIL"]


class TemplateContract(StrictModel):
    """Versioned, portable inventory for a repository template implementation."""

    schema_version: Literal["1"] = "1"
    template_version: TemplateVersion
    required_paths: tuple[RepositoryPath, ...]
    adoption_guide: RepositoryPath
    upgrades_catalog: RepositoryPath


class TemplateUpgrade(StrictModel):
    id: Identifier
    from_version: TemplateVersion
    to_version: TemplateVersion
    breaking: bool
    steps: tuple[NonEmptyText, ...]


class TemplateUpgradesCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    upgrades: tuple[TemplateUpgrade, ...]


class TemplateAdoptionRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    template_version: TemplateVersion
    project_id: Identifier
    status: Literal["needs_adoption", "initialized"] = "needs_adoption"


class TemplateInitReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    project_id: str
    changed: tuple[RepositoryPath, ...] = ()
    removed: tuple[RepositoryPath, ...] = ()
    issues: tuple[PolicyIssue, ...] = ()


class TemplateAdoptReport(StrictModel):
    """One-command fork initialization and portable acceptance result."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_ADOPTION"] = "TEMPLATE_ADOPTION"
    build_authorized: Literal[False] = False
    project_id: Identifier
    preflight: Literal["PASS", "FAIL"]
    initialization: Literal["PASS", "FAIL", "NOT_RUN"]
    portable: Literal["PASS", "FAIL", "NOT_RUN"]
    status: Literal["PASS", "FAIL"]
    changed: tuple[RepositoryPath, ...] = ()
    removed: tuple[RepositoryPath, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()


class EnvironmentCheck(StrictModel):
    id: Identifier
    required: bool
    status: Literal["PASS", "FAIL", "OPTIONAL"]
    expected: NonEmptyText
    observed: NonEmptyText | None = None
    next_action: NonEmptyText


class TemplateDoctorReport(StrictModel):
    """Local prerequisites and native-runner readiness without changing the repository."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_DOCTOR"] = "TEMPLATE_DOCTOR"
    build_authorized: Literal[False] = False
    native_requested: bool
    electrical_requested: bool = False
    checks: tuple[EnvironmentCheck, ...]
    status: Literal["PASS", "FAIL"]
    next_actions: tuple[NonEmptyText, ...] = ()


class InventoryProject(StrictModel):
    """Declared island and whether its authored inputs are present for a check."""

    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    manifest: RepositoryPath
    project: RepositoryPath
    toolchain_id: Identifier
    tags: tuple[Identifier, ...]
    products: tuple[Identifier, ...]
    readiness: Literal["INPUTS_PRESENT", "NEEDS_INPUTS"]
    missing_inputs: tuple[RepositoryPath, ...] = ()
    next_command: NonEmptyText


class McpProjectReport(StrictModel):
    """One project's declared inputs; inspection never authorizes manufacturing."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    project: InventoryProject
    manifest: ProjectManifest
    contract: ProjectTestContract | None


class InventoryGroup(StrictModel):
    """One product or tag and its selected project IDs."""

    id: Identifier
    project_ids: tuple[Identifier, ...]


class InventoryToolchain(StrictModel):
    id: Identifier
    kicad_version: NonEmptyText


class TemplateInventoryReport(StrictModel):
    """Read-only discovery; input presence is not validation or release approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_INVENTORY"] = "TEMPLATE_INVENTORY"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[InventoryProject, ...] = ()
    products: tuple[InventoryGroup, ...] = ()
    tags: tuple[InventoryGroup, ...] = ()
    toolchains: tuple[InventoryToolchain, ...] = ()
    issues: tuple[PolicyIssue, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()


class DiagnosticFinding(StrictModel):
    """One observed failure or review task with a concrete repair path."""

    severity: Literal["BLOCKING", "REVIEW"]
    code: NonEmptyText
    location: NonEmptyText
    observed: NonEmptyText
    action: NonEmptyText
    guide: RepositoryPath


class DiagnosticReport(StrictModel):
    """A local coaching view; success never constitutes engineering approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_DIAGNOSTICS"] = "PROJECT_DIAGNOSTICS"
    build_authorized: Literal[False] = False
    project_id: NonEmptyText
    scope: Literal["import", "project"]
    status: Literal["PASS", "NEEDS_WORK"]
    findings: tuple[DiagnosticFinding, ...]
    next_command: NonEmptyText
    follow_up_command: NonEmptyText | None = None
    run_directory: str | None = None


class LocalRescueReport(StrictModel):
    """Partial, read-only island inspection that cannot satisfy repository gates."""

    schema_version: Literal["1"] = "1"
    lane: Literal["LOCAL_PROJECT_RESCUE"] = "LOCAL_PROJECT_RESCUE"
    status: Literal["UNVERIFIED_GLOBAL"] = "UNVERIFIED_GLOBAL"
    build_authorized: Literal[False] = False
    ci_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    project_id: NonEmptyText
    selected_manifest: RepositoryPath | None = None
    local_inspection: Literal["CLEAR", "NEEDS_REPAIR"]
    findings: tuple[DiagnosticFinding, ...] = ()
    omitted_checks: tuple[NonEmptyText, ...]
    next_command: NonEmptyText
    run_directory: NonEmptyText


class TemplatePreflightReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_PREFLIGHT"] = "TEMPLATE_PREFLIGHT"
    build_authorized: Literal[False] = False
    template_version: TemplateVersion | None = None
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class TemplateBootstrapReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_BOOTSTRAP"] = "TEMPLATE_BOOTSTRAP"
    build_authorized: Literal[False] = False
    template_version: TemplateVersion | None = None
    destination: NonEmptyText
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]
    removed: tuple[RepositoryPath, ...] = ()


class TemplateUpgradePlan(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_UPGRADE_PLAN"] = "TEMPLATE_UPGRADE_PLAN"
    build_authorized: Literal[False] = False
    current_version: TemplateVersion | None = None
    target_version: NonEmptyText
    status: Literal["PASS", "FAIL"]
    upgrades: tuple[TemplateUpgrade, ...]
    issues: tuple[PolicyIssue, ...]


class SupplierOffer(StrictModel):
    id: Identifier
    part_id: Identifier
    supplier: NonEmptyText
    supplier_sku: NonEmptyText
    source_url: NonEmptyText
    region: NonEmptyText
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    quantity_break: PositiveCount
    unit_price_minor: NonNegativeCount
    availability: NonEmptyText
    lead_time_days: NonNegativeCount | None = None


class SourcingSnapshot(StrictModel):
    schema_version: Literal["1"] = "1"
    snapshot_id: Identifier
    source_commit: GitCommit
    observed_at: AwareDatetime
    offers: tuple[SupplierOffer, ...]


class SourcingSnapshotReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["SOURCING_SNAPSHOT"] = "SOURCING_SNAPSHOT"
    build_authorized: Literal[False] = False
    snapshot_id: Identifier
    offers: NonNegativeCount
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class CheckMetric(StrictModel):
    name: Identifier
    status: Literal["PASS", "FAIL"]
    findings: NonNegativeCount


class DeviationMetrics(StrictModel):
    total: NonNegativeCount
    approved: NonNegativeCount
    open: NonNegativeCount
    closed: NonNegativeCount
    expired: NonNegativeCount


class TemplateMetricsReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_METRICS"] = "TEMPLATE_METRICS"
    build_authorized: Literal[False] = False
    checks: tuple[CheckMetric, ...]
    stale_evidence: NonNegativeCount
    deviations: DeviationMetrics


class CheckEvidence(StrictModel):
    status: Literal["PASS", "FAIL", "NOT_RUN"]
    returncode: int | None = None
    error: NonEmptyText | None = None
    findings: int | None = None
    expected_ignored_checks: tuple[Identifier, ...] = ()
    files: tuple[RepositoryPath, ...] = ()
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    identity_status: Literal["PASS", "NOT_APPLICABLE"] | None = None
    observed_version: NonEmptyText | None = None
    image: NonEmptyText | None = None


class NetlistContract(StrictModel):
    components: Mapping[Identifier, ComponentContract]
    nets: Mapping[NetName, tuple[Reference, ...]]
    unconnected_nets: Mapping[NetName, tuple[Reference, ...]] = Field(default_factory=dict)
    dnp_components: tuple[Identifier, ...] = ()
    component_symbols: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)
    pin_functions: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    pin_electrical_types: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    component_pin_numbers: Mapping[Identifier, tuple[NonEmptyText, ...]] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def separate_native_unconnected_nets(cls, value: object, info: ValidationInfo) -> object:
        """Keep KiCad's per-pin unconnected sentinels out of electrical nets."""
        if not isinstance(value, Mapping):
            return value
        source = cast(Mapping[object, object], value)
        nets = source.get("nets")
        existing_unconnected = source.get("unconnected_nets", {})
        if not isinstance(nets, Mapping) or not isinstance(existing_unconnected, Mapping):
            return cast(object, value)
        net_mapping = cast(Mapping[object, object], nets)
        unconnected_mapping = cast(Mapping[object, object], existing_unconnected)

        assigned: dict[object, object] = {}
        unconnected: dict[object, object] = dict(unconnected_mapping)
        moved = False
        for name, pins in net_mapping.items():
            if not isinstance(name, str) or not is_native_unconnected_net_name(name):
                assigned[name] = pins
                continue
            moved = True
            previous = unconnected.get(name)
            if isinstance(previous, (tuple, list)) and isinstance(pins, (tuple, list)):
                previous_items = cast(tuple[object, ...] | list[object], previous)
                current_items = cast(tuple[object, ...] | list[object], pins)
                if all(isinstance(pin, str) for pin in previous_items) and all(
                    isinstance(pin, str) for pin in current_items
                ):
                    previous_pins = cast(tuple[str, ...] | list[str], previous_items)
                    current_pins = cast(tuple[str, ...] | list[str], current_items)
                    unconnected[name] = tuple(
                        sorted(set(previous_pins) | set(current_pins), key=str.casefold)
                    )
                else:
                    unconnected[name] = pins
            else:
                unconnected[name] = pins

        if not moved and info.mode != "json":
            return cast(object, value)
        normalized: dict[object, object] = dict(source.items())
        if moved:
            normalized["nets"] = assigned
            normalized["unconnected_nets"] = unconnected
        if info.mode == "json":
            # Returning a Python mapping from a before-validator switches
            # subsequent validation to Python mode. Preserve JSON array
            # semantics for every tuple field before strict field validation.
            for field in ("nets", "unconnected_nets", "component_pin_numbers"):
                table = normalized.get(field)
                if isinstance(table, Mapping):
                    table_mapping = cast(Mapping[object, object], table)
                    normalized[field] = {
                        key: tuple(cast(list[object], items)) if isinstance(items, list) else items
                        for key, items in table_mapping.items()
                    }
            dnp_components = normalized.get("dnp_components")
            if isinstance(dnp_components, list):
                normalized["dnp_components"] = tuple(cast(list[object], dnp_components))
        return normalized


class ReturnNetGroup(StrictModel):
    """Unreviewed, similarly named return nets observed in a native export."""

    stem: NonEmptyText
    nets: Mapping[NetName, tuple[Reference, ...]]


class NumberedPowerRailGroup(StrictModel):
    """Unreviewed, similarly named numbered positive supply nets."""

    stem: NonEmptyText
    nets: Mapping[NetName, tuple[Reference, ...]]


class SimilarConnectorPinGroup(StrictModel):
    """Unreviewed repeated connector pin functions with differing schematic nets."""

    symbol: NonEmptyText
    function: NonEmptyText
    pins: Mapping[Reference, tuple[NetName, ...]]
    reviewed_role: ConnectorPinRole | None = None
    reviewed_voltage_domain: NonEmptyText | None = None
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def mapped_supply_has_domain(self) -> SimilarConnectorPinGroup:
        if (self.reviewed_role == "supply") != (self.reviewed_voltage_domain is not None):
            raise ValueError("Mapped supply connector groups require an exact voltage domain")
        if self.reviewed_voltage_domain is not None and self.reviewed_role != "supply":
            raise ValueError("Only mapped supply connector groups carry a voltage domain")
        if (self.peer_assignment_group is None) != (not self.peer_assignment_basis):
            raise ValueError("Scoped connector comparisons need their reviewed group basis")
        return self


class ValidationSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI"] = "KICAD_CLI"
    timestamp_utc: NonEmptyText
    checked_commit: NonEmptyText
    source: SourceState | None = None
    project_id: Identifier | None = None
    pr_head_commit: str | None = None
    assurance_profile: Literal["training", "development", "production"] | None = None
    not_for_manufacture: bool | None = None
    project_kind: ProjectKind | None = None
    checks: Mapping[Identifier, CheckEvidence]
    status: Literal["PASS", "FAIL"]
    artifacts_sha256: Mapping[RepositoryPath, Digest]


class ProjectCheckSummary(StrictModel):
    id: Identifier
    status: Literal["PASS", "FAIL"]
    summary: RepositoryPath


class CheckAllSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI_ALL_PROJECTS"] = "KICAD_CLI_ALL_PROJECTS"
    governance: GovernanceLintReport
    repository: RepositoryPolicyReport
    product_policy: ProductPolicyReport
    projects: tuple[ProjectCheckSummary, ...]
    status: Literal["PASS", "FAIL"]


class FaultProbeCase(StrictModel):
    id: Identifier
    status: Literal["PASS", "FAIL"]
    expected_failing_check: Identifier
    observed_status: Literal["PASS", "FAIL", "NOT_RUN"] | None = None
    observed_returncode: int | None = None


class FaultProbeReport(StrictModel):
    lane: Literal["KICAD_CLI"] = "KICAD_CLI"
    not_for_manufacture: Literal[True] = True
    cases: tuple[FaultProbeCase, ...]
    status: Literal["PASS", "FAIL"]


class UnitTestReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    returncode: int


class SkippedCheck(StrictModel):
    status: Literal["NOT_RUN"] = "NOT_RUN"
    reason: NonEmptyText


class FailedCheck(StrictModel):
    status: Literal["FAIL"] = "FAIL"
    error: NonEmptyText


class ProjectTestsReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    commands: Mapping[Identifier, CommandEvidence]


class StaticPipelineReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source: SourceState | None = None
    scope: Literal["static_only", "repository_static"] = "static_only"
    tooling_version: NonEmptyText | None = None
    build_authorized: Literal[False] = False
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    documentation: DocumentationPolicyReport
    rumdl: CommandEvidence
    mdrepo: CommandEvidence
    product: ProductPolicyReport
    generation: GenerationReport
    ruff: CommandEvidence | None = None
    pyright: CommandEvidence | None = None
    unit_tests: CommandEvidence | None = None
    project_tests: ProjectTestsReport

    @model_validator(mode="after")
    def explicit_tooling_boundary(self) -> StaticPipelineReport:
        if self.scope == "static_only" and any(
            command is None for command in (self.ruff, self.pyright, self.unit_tests)
        ):
            raise ValueError("Legacy full reports require all tooling quality commands")
        if self.scope == "repository_static" and self.tooling_version is None:
            raise ValueError(
                "Project repository reports must identify the installed tooling version"
            )
        return self


class ProjectStaticPipelineReport(StrictModel):
    """Fast local policy result for explicitly selected design projects."""

    status: Literal["PASS", "FAIL"]
    scope: Literal["project_static"] = "project_static"
    build_authorized: Literal[False] = False
    projects: tuple[Identifier, ...]
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    product: ProductPolicyReport
    generation: GenerationReport
    project_tests: ProjectTestsReport


class ProjectVerificationReport(StrictModel):
    """One local project attempt with retained portable and optional native evidence."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_VERIFY"] = "PROJECT_VERIFY"
    build_authorized: Literal[False] = False
    project_id: Identifier
    depth: Literal["portable", "native", "electrical"]
    runner: Literal["none", "local", "container"] = "none"
    run_directory: NonEmptyText
    portable: ProjectStaticPipelineReport | None = None
    doctor: TemplateDoctorReport | None = None
    dependency_command: CommandEvidence | None = None
    native_command: CommandEvidence | None = None
    native: CheckAllSummary | None = None
    design_lint: DesignLintReport | None = None
    electrical: ElectricalAnalysisReport | None = None
    diagnosis: DiagnosticReport | None = None
    status: Literal["PASS", "FAIL", "ERROR"]
    next_actions: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class ScopedReleasePortableReport(StrictModel):
    """Committed-source binding for the selected portable release lane.

    This is deliberately a different type from StaticPipelineReport: a
    selected lane can never masquerade as the repository-wide portable gate.
    """

    schema_version: Literal["1"] = "1"
    scope: Literal["release_projects"] = "release_projects"
    source: SourceState
    projects: tuple[Identifier, ...]
    checks: ProjectStaticPipelineReport


class ContractDifference(StrictModel):
    kind: Literal["component", "net"]
    identifier: NonEmptyText
    difference: Literal["observed_only", "authored_only", "different"]


class ContractCoachReport(StrictModel):
    """Observed netlist inventory for human contract review, never an approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["CONTRACT_COACH"] = "CONTRACT_COACH"
    status: Literal["READY_FOR_REVIEW", "BLOCKED"]
    project_id: Identifier
    project_kind: ProjectKind | None = None
    review_state: Literal["UNREVIEWED"] = "UNREVIEWED"
    electrical_coverage: Literal[False] = False
    build_authorized: Literal[False] = False
    selected_runner: Literal["local", "container"] | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_summary: str | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    observed: NetlistContract | None = None
    authored: NetlistContract | None = None
    differences: tuple[ContractDifference, ...] = ()
    return_net_groups: tuple[ReturnNetGroup, ...] = ()
    similar_connector_pin_groups: tuple[SimilarConnectorPinGroup, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    receipt_dir: str | None = None


class ConnectorMappedPinEvidence(StrictModel):
    interface_pin_number: NonEmptyText
    interface_signal: NonEmptyText
    component_pin: Reference
    role: ConnectorPinRole | None = None
    voltage_domain: NonEmptyText | None = None
    symbol_function: NonEmptyText | None = None
    nets: tuple[NetName, ...] = ()


class ConnectorCoverageEntry(StrictModel):
    reference: Identifier
    status: Literal["COVERED", "NOT_APPLICABLE", "UNDECLARED", "INCOMPLETE", "STALE"]
    interface_id: Identifier | None = None
    basis: NonEmptyText | None = None
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: NonEmptyText | None = None
    interface_pin_map: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    unlisted_pin_reasons: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    mapped_pins: tuple[ConnectorMappedPinEvidence, ...] = ()
    interface_pins_unmapped: tuple[NonEmptyText, ...] = ()
    interface_pins_unknown: tuple[NonEmptyText, ...] = ()
    component_pins_unaccounted: tuple[NonEmptyText, ...] = ()
    component_pins_unknown: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_peer_assignment_group(self) -> ConnectorCoverageEntry:
        if (self.peer_assignment_group is None) != (self.peer_assignment_basis is None):
            raise ValueError("Connector peer-assignment groups need a review basis")
        if self.status == "NOT_APPLICABLE" and self.peer_assignment_group is not None:
            raise ValueError("Not-applicable connectors cannot join a peer-assignment group")
        return self


class ConnectorCoverageReport(StrictModel):
    """Coverage of explicitly identified or heuristically discovered connector candidates."""

    status: Literal["COMPLETE", "INCOMPLETE", "UNDECLARED", "UNASSESSED", "SCOPE_UNREVIEWED"]
    scope: NonEmptyText
    project_interfaces: tuple[Identifier, ...] = ()
    unbound_interface_ids: tuple[Identifier, ...] = ()
    inventory_review_basis: NonEmptyText | None = None
    interface_catalog_path: RepositoryPath | None = None
    interface_catalog_sha256: Digest | None = None
    entries: tuple[ConnectorCoverageEntry, ...] = ()
    catalog_issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def inventory_review_matches_status(self) -> ConnectorCoverageReport:
        if self.status == "COMPLETE" and self.inventory_review_basis is None:
            raise ValueError("Complete connector coverage requires an inventory review basis")
        if self.status in {"UNASSESSED", "SCOPE_UNREVIEWED"} and (
            self.inventory_review_basis is not None
        ):
            raise ValueError(f"{self.status} connector coverage cannot include an inventory basis")
        return self


class ConnectorReturnDistributionEntry(StrictModel):
    """Role counts and threshold result for one mapped connector instance."""

    id: Identifier
    connector_reference: Identifier | None = None
    interface_id: Identifier
    status: Literal["COMPLETE", "BELOW_SCOPE", "OUT_OF_RANGE", "INCOMPLETE"]
    signal_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    return_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    supply_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    shield_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    other_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    unclassified_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    signal_pin_count: NonNegativeCount
    return_pin_count: NonNegativeCount
    required_return_pin_count: NonNegativeCount
    signal_to_return_ratio: ElectricalPositive | None = None
    minimum_signal_pin_count: Annotated[int, Field(ge=1)]
    maximum_signal_to_return_ratio: ElectricalPositive
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class ConnectorReturnDistributionCoverageReport(StrictModel):
    """Source-bound review coverage for authored return-contact thresholds."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Counts explicitly role-classified connector contacts for project-scoped signal/return "
        "ratios. It does not assert net equality, electrical capacity, or PCB continuity."
    )
    netlist_sha256: Digest | None = None
    interface_catalog_sha256: Digest | None = None
    entries: tuple[ConnectorReturnDistributionEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> ConnectorReturnDistributionCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and (
            self.netlist_sha256 is None or self.interface_catalog_sha256 is None
        ):
            raise ValueError(
                "Configured return-distribution coverage must bind netlist and interface catalog"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked return-distribution coverage must explain the evidence gap")
        return self


class ExternalProtectionCoverageEntry(StrictModel):
    connector_reference: Identifier
    connector_pin: Reference
    interface_signal: NonEmptyText | None = None
    signal_net: NetName | None = None
    observed_nets: tuple[NetName, ...] = ()
    status: Literal[
        "PROTECTED",
        "NOT_REQUIRED",
        "HANDLED_BY_EXISTING_CONTRACT",
        "UNDECLARED",
        "INCOMPLETE",
        "STALE",
    ]
    basis: NonEmptyText | None = None
    device_references: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class ExternalProtectionCoverageReport(StrictModel):
    """Coverage and exact pin checks for reviewed external-interface protection."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "UNDECLARED", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    scope: NonEmptyText = (
        "Only project-reviewed connector interface pins and explicitly mapped protector channels "
        "are compared; this does not infer a protection requirement from a signal name."
    )
    netlist_sha256: Digest | None = None
    electrical_contract_path: RepositoryPath | None = None
    electrical_contract_sha256: Digest | None = None
    entries: tuple[ExternalProtectionCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def evidence_is_source_bound(self) -> ExternalProtectionCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE", "UNDECLARED"} and (
            self.netlist_sha256 is None
        ):
            raise ValueError("Configured external-protection coverage needs a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked external-protection coverage must explain the evidence gap")
        if (self.electrical_contract_path is None) != (self.electrical_contract_sha256 is None):
            raise ValueError("Electrical contract path and digest must be bound together")
        return self


class I2cAddressBitEvidence(StrictModel):
    bit: Annotated[int, Field(ge=0, le=6)]
    pin: Reference
    expected_function: NonEmptyText
    observed_function: NonEmptyText | None = None
    nets: tuple[NetName, ...] = ()
    resolved_value: Literal[0, 1] | None = None


class I2cResponderAddressCoverageEntry(StrictModel):
    reference: Identifier
    segment_id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "DYNAMIC", "NOT_FITTED"]
    mode: Literal["fixed", "strapped", "dynamic"]
    expected_symbol: NonEmptyText
    observed_symbol: NonEmptyText | None = None
    sda_pin: Reference
    scl_pin: Reference
    sda_nets: tuple[NetName, ...] = ()
    scl_nets: tuple[NetName, ...] = ()
    expected_address: Annotated[int, Field(ge=0, le=127)] | None = None
    observed_address: Annotated[int, Field(ge=0, le=127)] | None = None
    address_bits: tuple[I2cAddressBitEvidence, ...] = ()
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class I2cAddressCoverageReport(StrictModel):
    """Coverage of an authored responder map against the native netlist."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only project-declared responders and segments are compared; this does not enumerate "
        "off-board, unlisted, or firmware-addressed devices."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[I2cResponderAddressCoverageEntry, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> I2cAddressCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured I2C address coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked I2C address coverage must explain the evidence gap")
        return self


class CrystalNetworkCoverageEntry(StrictModel):
    """One mapped oscillator network compared with native netlist assignments."""

    oscillator_reference: Identifier
    resonator_reference: Identifier
    load_capacitor_references: tuple[Identifier, ...]
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    target_minimum_load_pf: CapacitancePf
    target_maximum_load_pf: CapacitancePf
    minimum_stray_capacitance_pf: NonNegativeCapacitancePf
    maximum_stray_capacitance_pf: NonNegativeCapacitancePf
    basis: NonEmptyText
    extra_capacitor_references: tuple[Identifier, ...] = ()
    extra_capacitor_pin_nets: Mapping[Identifier, tuple[NonEmptyText, ...]] = Field(
        default_factory=dict
    )
    formula: Literal["C1*C2/(C1+C2) + Cstray"] = "C1*C2/(C1+C2) + Cstray"
    node_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    capacitance_pf: Mapping[Identifier, CapacitancePf] = Field(default_factory=dict)
    calculated_minimum_load_pf: CapacitancePf | None = None
    calculated_maximum_load_pf: CapacitancePf | None = None
    issues: tuple[NonEmptyText, ...] = ()


class CrystalNetworkCoverageReport(StrictModel):
    """Coverage of authored crystal load-network requirements against native evidence."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped Pierce networks are compared. The nominal load estimate does "
        "not establish oscillator startup, frequency accuracy, drive level, ESR margin, "
        "parasitics, layout quality, or environmental performance."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[CrystalNetworkCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> CrystalNetworkCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured crystal network coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked crystal network coverage must explain the evidence gap")
        return self


class RegulatorFeedbackCoverageEntry(StrictModel):
    """One authored adjustable-regulator divider compared with native netlist evidence."""

    id: Identifier
    regulator_reference: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    output_net: NetName
    reference_net: NetName
    feedback_net: NetName | None = None
    formula: Literal["Vref*(1+Rupper/Rlower)"] = "Vref*(1+Rupper/Rlower)"
    feedback_reference_minimum_v: ElectricalPositive
    feedback_reference_maximum_v: ElectricalPositive
    target_output_minimum_v: ElectricalPositive
    target_output_maximum_v: ElectricalPositive
    nominal_resistance_ohms: Mapping[Identifier, ElectricalPositive] = Field(default_factory=dict)
    calculated_output_minimum_v: ElectricalPositive | None = None
    calculated_output_maximum_v: ElectricalPositive | None = None
    pin_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class RegulatorFeedbackCoverageReport(StrictModel):
    """Coverage of authored regulator-feedback requirements against native evidence."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped conventional two-resistor adjustable feedback dividers are "
        "checked. The nominal DC estimate does not establish stability, compensation, startup, "
        "load response, resistor tolerance, IC ratings, or PCB feedback routing."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[RegulatorFeedbackCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> RegulatorFeedbackCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError(
                "Configured regulator feedback coverage must bind a native netlist hash"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked regulator feedback coverage must explain the evidence gap")
        return self


class RcFilterCoverageEntry(StrictModel):
    """One explicitly mapped first-order RC filter checked against the native netlist."""

    id: Identifier
    resistor_reference: ResistorReference
    capacitor_reference: Identifier
    status: Literal["COMPLETE", "INCOMPLETE", "OUT_OF_RANGE"]
    input_net: NetName
    filtered_net: NetName
    reference_net: NetName
    formula: Literal["1/(2*pi*R*C)"] = "1/(2*pi*R*C)"
    resistance_ohms: ElectricalPositive | None = None
    capacitance_pf: CapacitancePf | None = None
    calculated_corner_hz: ElectricalPositive | None = None
    target_minimum_corner_hz: ElectricalPositive
    target_maximum_corner_hz: ElectricalPositive
    nominal_resistance_range_ohms: tuple[ElectricalPositive, ElectricalPositive]
    nominal_capacitance_range_pf: tuple[CapacitancePf, CapacitancePf]
    pin_nets: Mapping[Reference, tuple[NetName, ...]] = Field(default_factory=dict)
    unlisted_parallel_components: tuple[Identifier, ...] = ()
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class RcFilterCoverageReport(StrictModel):
    """Coverage of authored RC filter requirements against source-bound netlists."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Only explicitly mapped first-order series-resistor/shunt-capacitor low-pass networks "
        "are checked. Nominal cutoff estimates do not model source/load impedance, tolerances, "
        "transient behavior, or higher-order filters."
    )
    netlist_sha256: Digest | None = None
    entries: tuple[RcFilterCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> RcFilterCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Configured RC filter coverage must bind a native netlist hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked RC filter coverage must explain the evidence gap")
        return self


class Stm32PinMapMismatch(StrictModel):
    """One exact package pin whose CubeMX or schematic evidence differs from contract."""

    map_id: Identifier
    reference: Identifier
    port_pin: Stm32PortPin
    symbol_pin: NonEmptyText
    expected_net: NetName
    observed_nets: tuple[NetName, ...]
    accepted_ioc_signals: tuple[NonEmptyText, ...]
    observed_ioc_signal: NonEmptyText | None
    accepted_ioc_gpio_labels: tuple[NonEmptyText | None, ...] | None
    observed_ioc_gpio_label: NonEmptyText | None
    ioc_path: RepositoryPath
    ioc_sha256: Digest
    map_sha256: Digest
    netlist_sha256: Digest
    issues: tuple[NonEmptyText, ...]


class Stm32UnmappedDevice(StrictModel):
    """Likely STM32 component found in the native netlist without a pin-map contract."""

    reference: Identifier
    observed_symbol: NonEmptyText | None = None
    observed_part: NonEmptyText
    netlist_sha256: Digest


class Stm32PinMapCoverageReport(StrictModel):
    """Coverage and source hashes for project-authored CubeMX pin-map comparisons."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    ioc_source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    mapped_pin_count: NonNegativeCount = 0
    excluded_pin_count: NonNegativeCount = 0
    mismatches: tuple[Stm32PinMapMismatch, ...] = ()
    unmapped_devices: tuple[Stm32UnmappedDevice, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def coverage_has_source_evidence(self) -> Stm32PinMapCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and self.netlist_sha256 is None:
            raise ValueError("Evaluated STM32 pin-map coverage must bind a native netlist hash")
        if self.status == "COMPLETE" and self.map_sha256 is None:
            raise ValueError("Complete STM32 pin-map coverage requires an authored map hash")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked STM32 pin-map coverage must explain the evidence gap")
        if self.status == "DISABLED" and self.mode != "off":
            raise ValueError("Disabled STM32 pin-map coverage must record the off policy")
        return self


class DesignLintFinding(StrictModel):
    rule_id: DesignLintRuleId
    fingerprint: Digest
    subject: NonEmptyText
    message: NonEmptyText
    evidence: Mapping[str, tuple[str, ...]]
    mode: Literal["review", "block", "off"]
    disposition: Literal["OPEN", "IGNORED", "RULE_OFF"]
    reason: NonEmptyText | None = None


class DesignLintMappedCheckRun(StrictModel):
    """Execution receipt for an optional mapped topology check."""

    rule_id: Literal[
        "bus.usb_data_path_mismatch",
        "power.mapped_series_path_mismatch",
        "power.mapped_sequence_dependency_mismatch",
    ]
    status: Literal["NOT_CONFIGURED", "EVALUATED", "BLOCKED"]
    mode: Literal["review", "block", "off"]
    map_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    requirement_count: NonNegativeCount = 0
    finding_count: NonNegativeCount = 0
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def execution_matches_map_state(self) -> DesignLintMappedCheckRun:
        if self.status == "NOT_CONFIGURED" and (
            self.map_sha256 is not None
            or self.requirement_count != 0
            or self.finding_count != 0
            or self.reason is None
        ):
            raise ValueError("Unconfigured mapped checks need a reason and zero map counts")
        if self.status == "EVALUATED" and (
            self.map_sha256 is None
            or self.netlist_sha256 is None
            or self.requirement_count == 0
            or self.reason is not None
        ):
            raise ValueError("Evaluated mapped checks need source hashes and authored entries")
        if self.status == "BLOCKED" and (
            self.map_sha256 is None or self.requirement_count == 0 or self.reason is None
        ):
            raise ValueError("Blocked mapped checks need a configured map and blocking reason")
        return self


class ControlInputBiasHeuristicEntry(StrictModel):
    """One connected-control heuristic candidate and its authored-contract coverage."""

    net: NetName
    control_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    status: Literal["COVERED", "OPEN"]
    signal_id: Identifier | None = None
    bias_mode: Literal["local", "internal", "external", "not_required"] | None = None
    bias_basis: NonEmptyText | None = None
    bias_reason: NonEmptyText | None = None
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def coverage_has_exact_intent(self) -> ControlInputBiasHeuristicEntry:
        if self.status == "COVERED" and (
            self.signal_id is None
            or self.bias_mode is None
            or self.bias_basis is None
            or self.issues
        ):
            raise ValueError("Covered control-bias candidates need a clean authored requirement")
        if self.status == "OPEN" and not self.issues:
            raise ValueError("Open control-bias candidates must explain why coverage is incomplete")
        return self


class ControlInputBiasHeuristicCoverage(StrictModel):
    """Source-bound accounting for control-bias prompts resolved by reviewed requirements."""

    status: Literal[
        "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
    ] = "NOT_CONFIGURED"
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[ControlInputBiasHeuristicEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_coverage(self) -> ControlInputBiasHeuristicCoverage:
        if (self.source_path is None) != (self.source_sha256 is None):
            raise ValueError("Control-input contract path and hash must be recorded together")
        if self.entries and self.netlist_sha256 is None:
            raise ValueError("Control-bias candidate coverage needs its native netlist hash")
        nets = [item.net.casefold() for item in self.entries]
        if len(nets) != len(set(nets)):
            raise ValueError("Control-bias coverage entries need unique nets")
        if self.status == "COMPLETE" and any(item.status != "COVERED" for item in self.entries):
            raise ValueError("Complete control-bias coverage cannot contain open candidates")
        if self.status == "OPEN" and not any(item.status == "OPEN" for item in self.entries):
            raise ValueError("Open control-bias coverage needs an open candidate")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked control-bias coverage must explain the evidence gap")
        return self


class I2cPullupHeuristicEntry(StrictModel):
    """One missing-pull-up hint and the exact authored requirement used to resolve it."""

    sda_net: NetName
    scl_net: NetName
    missing_lines: Annotated[tuple[Literal["SDA", "SCL"], ...], Field(min_length=1)]
    status: Literal["COVERED", "OPEN"]
    bus_id: Identifier | None = None
    check_ids: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def exact_requirement_is_recorded(self) -> I2cPullupHeuristicEntry:
        if self.sda_net.casefold() == self.scl_net.casefold():
            raise ValueError("I2C pull-up coverage needs distinct SDA and SCL nets")
        if len(set(self.missing_lines)) != len(self.missing_lines):
            raise ValueError("I2C missing-pull-up lines must be unique")
        if len(set(self.check_ids)) != len(self.check_ids):
            raise ValueError("I2C pull-up check IDs must be unique")
        if self.status == "COVERED" and (self.bus_id is None or not self.check_ids or self.issues):
            raise ValueError("Covered I2C hints need a clean exact authored requirement")
        if self.status == "COVERED" and self.bus_id is not None:
            required_checks = {
                f"i2c-pullup/{self.bus_id}/sda",
                f"i2c-pullup/{self.bus_id}/scl",
            }
            if not required_checks.issubset(self.check_ids):
                raise ValueError("Covered I2C hints need passing checks for both bus lines")
        if self.status == "OPEN" and not self.issues:
            raise ValueError("Open I2C hints must explain why coverage is incomplete")
        return self


class I2cPullupHeuristicCoverage(StrictModel):
    """Source-bound accounting for I2C pull-up hints resolved by authored requirements."""

    status: Literal[
        "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
    ] = "NOT_CONFIGURED"
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[I2cPullupHeuristicEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_coverage(self) -> I2cPullupHeuristicCoverage:
        if (self.source_path is None) != (self.source_sha256 is None):
            raise ValueError("I2C pull-up contract path and hash must be recorded together")
        if self.entries and self.netlist_sha256 is None:
            raise ValueError("I2C pull-up candidate coverage needs its native netlist hash")
        pairs = [(item.sda_net.casefold(), item.scl_net.casefold()) for item in self.entries]
        if len(pairs) != len(set(pairs)):
            raise ValueError("I2C pull-up coverage entries need unique ordered net pairs")
        if self.status == "COMPLETE" and any(item.status != "COVERED" for item in self.entries):
            raise ValueError("Complete I2C pull-up coverage cannot contain open candidates")
        if self.status == "OPEN" and not any(item.status == "OPEN" for item in self.entries):
            raise ValueError("Open I2C pull-up coverage needs an open candidate")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked I2C pull-up coverage must explain the evidence gap")
        if self.status == "BLOCKED" and any(item.status == "COVERED" for item in self.entries):
            raise ValueError("Blocked I2C pull-up coverage cannot resolve candidate prompts")
        return self


def _empty_schematic_geometry_rule_modes() -> dict[
    SchematicGeometryRuleId, Literal["review", "block", "off"]
]:
    return {}


def _empty_schematic_geometry_rule_coverage() -> dict[
    SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus
]:
    return {}


def _empty_schematic_geometry_unsupported_by_rule() -> dict[
    SchematicGeometryRuleId, tuple[NonEmptyText, ...]
]:
    return {}


class SchematicGeometrySourceBinding(StrictModel):
    """One source file bound to a concrete schematic hierarchy occurrence."""

    source_path: RepositoryPath
    source_sha256: Digest
    sheet_instance_path: NonEmptyText
    sheet_path: tuple[NonEmptyText, ...] = ()


class SchematicGeometryCoverage(StrictModel):
    """Opt-in geometry-check coverage bound to schematic and native netlist bytes."""

    status: Literal[
        "NOT_REQUESTED", "DISABLED", "COMPLETE", "PARTIAL", "UNSUPPORTED", "BLOCKED"
    ] = "NOT_REQUESTED"
    mode: Literal["review", "block", "off"] | None = None
    rule_modes: Mapping[SchematicGeometryRuleId, Literal["review", "block", "off"]] = Field(
        default_factory=_empty_schematic_geometry_rule_modes
    )
    rule_coverage: Mapping[SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus] = Field(
        default_factory=_empty_schematic_geometry_rule_coverage
    )
    unsupported_by_rule: Mapping[SchematicGeometryRuleId, tuple[NonEmptyText, ...]] = Field(
        default_factory=_empty_schematic_geometry_unsupported_by_rule
    )
    source_path: RepositoryPath | None = None
    source_sha256: Digest | None = None
    source_tree_sha256: Digest | None = None
    source_bindings: tuple[SchematicGeometrySourceBinding, ...] = ()
    netlist_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    schematic_version: NonEmptyText | None = None
    finding_count: NonNegativeCount = 0
    unsupported: tuple[NonEmptyText, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> SchematicGeometryCoverage:
        if self.status in {"COMPLETE", "PARTIAL", "UNSUPPORTED"} and (
            self.source_path is None
            or self.source_sha256 is None
            or self.source_tree_sha256 is None
            or not self.source_bindings
            or self.netlist_sha256 is None
            or self.kicad_version is None
        ):
            raise ValueError(
                "Scanned schematic geometry must bind its source tree, instance paths, and native netlist evidence"
            )
        if self.status in {"COMPLETE", "PARTIAL", "UNSUPPORTED"}:
            instance_paths = tuple(item.sheet_instance_path for item in self.source_bindings)
            if len(instance_paths) != len(set(instance_paths)):
                raise ValueError(
                    "Schematic geometry source bindings must have unique instance paths"
                )
            if not any(
                item.source_path == self.source_path and item.source_sha256 == self.source_sha256
                for item in self.source_bindings
            ):
                raise ValueError("Schematic geometry bindings must include the root source")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked schematic geometry coverage must explain the evidence gap")
        return self


class DesignLintReport(StrictModel):
    """Source-bound heuristic findings; neither a pinout nor electrical approval."""

    schema_version: Literal["1", "2"] = "2"
    lane: Literal["DESIGN_LINT"] = "DESIGN_LINT"
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"]
    project_id: Identifier
    review_state: Literal["HEURISTIC"] = "HEURISTIC"
    build_authorized: Literal[False] = False
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_summary: str | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    rule_catalog: DesignLintRuleCatalog | None = None
    project_manifest_sha256: Digest | None = None
    policy_path: RepositoryPath | None = None
    policy_sha256: Digest | None = None
    findings: tuple[DesignLintFinding, ...] = ()
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...] = ()
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...] = ()
    component_peer_pin_coverage: tuple[ComponentPeerPinRuleCoverage, ...] = ()
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None = None
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None = None
    connector_peer_pin_coverage: ConnectorPeerPinHeuristicCoverage | None = None
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage = Field(
        default_factory=ControlInputBiasHeuristicCoverage
    )
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage = Field(
        default_factory=I2cPullupHeuristicCoverage
    )
    connector_coverage: ConnectorCoverageReport | None = None
    stm32_pin_map_coverage: Stm32PinMapCoverageReport = Field(
        default_factory=Stm32PinMapCoverageReport
    )
    schematic_geometry: SchematicGeometryCoverage = Field(default_factory=SchematicGeometryCoverage)
    i2c_address_coverage: I2cAddressCoverageReport = Field(default_factory=I2cAddressCoverageReport)
    external_protection_coverage: ExternalProtectionCoverageReport = Field(
        default_factory=ExternalProtectionCoverageReport
    )
    crystal_network_coverage: CrystalNetworkCoverageReport = Field(
        default_factory=CrystalNetworkCoverageReport
    )
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport = Field(
        default_factory=RegulatorFeedbackCoverageReport
    )
    rc_filter_coverage: RcFilterCoverageReport = Field(default_factory=RcFilterCoverageReport)
    connector_return_distribution: ConnectorReturnDistributionCoverageReport = Field(
        default_factory=ConnectorReturnDistributionCoverageReport
    )
    pcb_decoupling: PcbDecouplingCoverageReport = Field(default_factory=PcbDecouplingCoverageReport)
    pcb_protection_path: PcbProtectionPathCoverageReport = Field(
        default_factory=PcbProtectionPathCoverageReport
    )
    pcb_track_width: PcbTrackWidthCoverageReport = Field(
        default_factory=PcbTrackWidthCoverageReport
    )
    pcb_reference_plane: PcbReferencePlaneCoverageReport = Field(
        default_factory=PcbReferencePlaneCoverageReport
    )
    pcb_switching_loop: PcbSwitchingLoopCoverageReport = Field(
        default_factory=PcbSwitchingLoopCoverageReport
    )
    pcb_differential_pair_rules: PcbDifferentialPairRuleCoverageReport = Field(
        default_factory=PcbDifferentialPairRuleCoverageReport
    )
    pcb_signal_path_rules: PcbSignalPathRuleCoverageReport = Field(
        default_factory=PcbSignalPathRuleCoverageReport
    )
    pcb_keepout_coverage: PcbKeepoutCoverageReport = Field(default_factory=PcbKeepoutCoverageReport)
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport = Field(
        default_factory=PcbRfModuleAntennaCoverageReport
    )
    stale_ignores: tuple[DesignLintIgnore, ...] = ()
    rule_overrides: tuple[DesignLintRuleOverride, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def findings_are_catalogued(self) -> DesignLintReport:
        if (
            self.netlist_sha256 is not None
            and self.control_input_bias_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.control_input_bias_coverage.netlist_sha256
        ):
            raise ValueError("Control-input bias coverage must use this report's native netlist")
        if (
            self.netlist_sha256 is not None
            and self.i2c_pullup_heuristic_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.i2c_pullup_heuristic_coverage.netlist_sha256
        ):
            raise ValueError("I2C pull-up coverage must use this report's native netlist")
        if (
            self.netlist_sha256 is not None
            and self.pcb_rf_module_antenna_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.pcb_rf_module_antenna_coverage.netlist_sha256
        ):
            raise ValueError("RF module antenna coverage must use this report's native netlist")
        run_ids = [item.rule_id for item in self.mapped_check_runs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Mapped-check execution entries must use unique rule IDs")
        for run in self.mapped_check_runs:
            if (
                self.netlist_sha256 is not None
                and run.netlist_sha256 is not None
                and self.netlist_sha256 != run.netlist_sha256
            ):
                raise ValueError("Mapped-check execution must use this report's native netlist")
            expected_finding_count = sum(
                finding.rule_id == run.rule_id for finding in self.findings
            )
            if run.finding_count != expected_finding_count:
                raise ValueError(
                    "Mapped-check execution finding count must match the report findings"
                )
        voltage_coverage_ids = [item.rule_id for item in self.digital_peer_voltage_coverage]
        if len(voltage_coverage_ids) != len(set(voltage_coverage_ids)):
            raise ValueError("Digital-peer voltage coverage entries must use unique rule IDs")
        for item in self.digital_peer_voltage_coverage:
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Digital-peer voltage coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("Digital-peer voltage candidate counts must match report findings")
        component_peer_pin_rule_ids = [item.rule_id for item in self.component_peer_pin_coverage]
        if len(component_peer_pin_rule_ids) != len(set(component_peer_pin_rule_ids)):
            raise ValueError("Component peer-pin coverage entries must use unique rule IDs")
        expected_component_peer_pin_rule_ids = {
            "component.peer_power_output_unconnected",
            "component.peer_signal_output_unconnected",
            "component.peer_signal_input_unconnected",
            "component.peer_bidirectional_pin_unconnected",
        }
        if component_peer_pin_rule_ids and set(component_peer_pin_rule_ids) != (
            expected_component_peer_pin_rule_ids
        ):
            raise ValueError("Component peer-pin coverage must include every supported rule")
        for item in self.component_peer_pin_coverage:
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Component peer-pin coverage must use this report's netlist")
            expected_findings = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.finding_count != expected_findings:
                raise ValueError("Component peer-pin findings must match report findings")
        if self.usb_peer_reference_coverage is not None:
            item = self.usb_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("USB peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("USB peer-reference candidate counts must match report findings")
        if self.serial_peer_reference_coverage is not None:
            item = self.serial_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Serial peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError(
                    "Serial peer-reference candidate counts must match report findings"
                )
        if self.connector_peer_pin_coverage is not None:
            item = self.connector_peer_pin_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError(
                    "Connector peer-pin coverage must use this report's native netlist"
                )
            expected_counts = (
                (
                    "connector.repeated_pin_function",
                    item.repeated_function_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_outlier",
                    item.peer_pin_outlier_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_divergence",
                    item.peer_pin_divergence_finding_count,
                ),
            )
            for rule_id, expected_count in expected_counts:
                actual_count = sum(finding.rule_id == rule_id for finding in self.findings)
                if actual_count != expected_count:
                    raise ValueError(
                        f"Connector peer-pin coverage count must match {rule_id} findings"
                    )
            part_id_expected_counts = (
                (
                    "connector.peer_pin_assignment_outlier",
                    item.part_id_alias_coverage.outlier_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_divergence",
                    item.part_id_alias_coverage.divergence_finding_count,
                ),
            )
            for rule_id, expected_count in part_id_expected_counts:
                actual_count = sum(
                    finding.rule_id == rule_id
                    and finding.evidence.get("peer_identity_basis") == ("part_id",)
                    for finding in self.findings
                )
                if actual_count != expected_count:
                    raise ValueError(
                        f"Connector PART_ID peer coverage count must match {rule_id} findings"
                    )
        if self.rule_catalog is None:
            return self
        known = {item.rule_id for item in self.rule_catalog.rules if item.status == "active"}
        unknown = sorted({item.rule_id for item in self.findings} - known)
        if unknown:
            raise ValueError(
                f"Design-lint findings use rules absent from the active catalog: {unknown}"
            )
        return self


class McpArtifactEntry(StrictModel):
    path: RepositoryPath
    kind: Literal["file", "directory"]
    size_bytes: NonNegativeCount | None = None
    sha256: Digest | None = None


class McpArtifactList(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    directory: RepositoryPath
    entries: tuple[McpArtifactEntry, ...]
    offset: NonNegativeCount
    total_entries: NonNegativeCount
    truncated: bool
    next_offset: NonNegativeCount | None = None


class McpFileContent(StrictModel):
    """Bounded Unicode text or metadata; offsets count characters, never bytes."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    path: RepositoryPath
    sha256: Digest
    size_bytes: NonNegativeCount
    content_kind: Literal["text", "binary", "metadata_only"]
    text: str | None = None
    offset: NonNegativeCount
    total_characters: NonNegativeCount | None = None
    truncated: bool = False
    next_offset: NonNegativeCount | None = None
    note: str | None = None


class McpEditPreview(StrictModel):
    """A proposed exact replacement, without a claim of engineering validation."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    diff: str
    validation: Literal["JSON_MODEL", "TEXT_ONLY"]
    next_command: NonEmptyText


class McpEditResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    status: Literal["APPLIED"] = "APPLIED"
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    readback_sha256: Digest
    next_command: NonEmptyText


class McpScopeReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    run_directory: NonEmptyText
    report: StaticPipelineReport | ProjectStaticPipelineReport


class McpGenerationReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS"] = "PASS"
    directory: RepositoryPath
    files: tuple[RepositoryPath, ...]


Resolution = Literal[
    "source_present",
    "toolchain_dependent",
    "embedded_present",
    "broken",
]
InventoryStatus = Literal["READY", "REVIEW", "FAIL"]
ExportMode = Literal["inspect", "generate"]
ExportStatus = Literal["PASS", "FAIL", "ERROR"]
SelectedRunner = Literal["none", "local", "container"]
ThreeDView = Literal[
    "top",
    "bottom",
    "left",
    "right",
    "front",
    "back",
    "angled",
    "angled-90",
    "angled-180",
    "angled-270",
]
THREE_D_VIEWS: tuple[ThreeDView, ...] = (
    "top",
    "bottom",
    "left",
    "right",
    "front",
    "back",
    "angled",
    "angled-90",
    "angled-180",
    "angled-270",
)
DEFAULT_THREE_D_VIEWS: tuple[ThreeDView, ...] = THREE_D_VIEWS


class ModelAssignment(StrictModel):
    """A raw observed model reference and its static source-resolution finding."""

    # Keep raw paths, including empty/nonportable input, so failed references can
    # be reported faithfully. Only a resolved source_path is a repository path.
    path: str
    line: PositiveCount
    resolution: Resolution
    source_path: RepositoryPath | None = None
    hidden: bool = False
    reason: str | None = None


class FootprintModels(StrictModel):
    """Observed footprint metadata; malformed identifiers remain diagnosable."""

    reference: str
    footprint_id: str
    line: PositiveCount
    models: tuple[ModelAssignment, ...]
    candidate_assets: tuple[RepositoryPath, ...]
    status: InventoryStatus


class ModelInventoryReport(StrictModel):
    """Static model assignments, without native geometry or manufacturing approval."""

    schema_version: Literal["1"] = "1"
    scope: Literal["static_inventory"] = "static_inventory"
    build_authorized: Literal[False] = False
    project_id: Identifier
    board: RepositoryPath
    status: InventoryStatus
    footprints: tuple[FootprintModels, ...]
    findings: tuple[DiagnosticFinding, ...]
    next_actions: tuple[NonEmptyText, ...]


class ThreeDReport(StrictModel):
    """A versioned 3D receipt for one board and source snapshot, never an approval."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    project_id: Identifier
    mode: ExportMode
    assembly_variant: NonEmptyText | None = None
    status: ExportStatus
    run_directory: NonEmptyText
    toolchain_id: Identifier | None = None
    kicad_version: NonEmptyText | None = None
    runner: SelectedRunner = "none"
    board: RepositoryPath | None = None
    source_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    models: ModelInventoryReport | None = None
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    next_actions: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class ModelMapAssignment(StrictModel):
    """An exact placed-footprint reference mapped to reviewed model source."""

    reference: str = Field(min_length=1)
    model: str
    candidate_assets: tuple[RepositoryPath, ...] = ()
    model_sha256: Digest | None = None


class McpModelMapAssignment(StrictModel):
    """MCP JSON-array input, converted to an immutable assignment at the adapter."""

    reference: str = Field(min_length=1)
    model: str
    candidate_assets: list[RepositoryPath] = Field(default_factory=list)
    model_sha256: Digest | None = None


class ModelMap(StrictModel):
    """Explicit assignments bound to the board bytes that the author reviewed."""

    schema_version: Literal["1"] = "1"
    project_id: Identifier
    board_sha256: Digest
    manifest_sha256: Digest
    assignments: tuple[ModelMapAssignment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_references(self) -> ModelMap:
        references = [item.reference for item in self.assignments]
        if len(references) != len(set(references)):
            raise ValueError("Map has duplicate footprint references")
        return self


class ModelPopulationReport(StrictModel):
    """A model-assignment plan or source edit that still requires engineering checks."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    status: Literal["DRAFT", "PLAN", "APPLIED", "FAIL", "ERROR"]
    project_id: Identifier
    run_directory: NonEmptyText
    board: RepositoryPath | None = None
    manifest: RepositoryPath | None = None
    board_sha256: Digest | None = None
    manifest_sha256: Digest | None = None
    draft_map: str | None = None
    locked_map: str | None = None
    model_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    board_diff: str = ""
    manifest_diff: str = ""
    review_notice: NonEmptyText = (
        "A mapped path does not verify package identity, dimensions, orientation, "
        "offset or enclosure fit; inspect the generated geometry in KiCad."
    )
    next_commands: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class PurchasingSchemaModel(StrictModel):
    schema_version: Literal["1"] = "1"

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema_version(cls, value: str) -> str:
        if type(value) is not str or value != "1":
            raise ValueError("Unsupported purchasing schema version")
        return value


class PurchasingPreferences(PurchasingSchemaModel):
    """User-selected quantities and exact supplier IDs; no sourcing authority."""

    boards: PositiveCount = 1
    spare_percent: Annotated[int, Field(ge=0, le=100)] = 0
    spare_minimum: NonNegativeCount = 0
    digikey_skus: Mapping[Identifier, Annotated[str, StringConstraints(min_length=1)]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def exact_supplier_identifiers(self) -> PurchasingPreferences:
        for identifier in self.digikey_skus.values():
            if identifier != identifier.strip() or any(
                ord(character) < 32 or ord(character) == 127 for character in identifier
            ):
                raise ValueError(
                    "DigiKey identifiers must be exact text without padding or control characters"
                )
        return self


class PurchasingComponent(StrictModel):
    reference: Identifier
    value: str
    footprint: str
    part_id: str | None = None
    dnp: bool = False
    exclude_from_bom: bool = False


class PurchasingLine(StrictModel):
    part_id: Identifier
    revision: Identifier
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    footprint: NonEmptyText
    references: tuple[Identifier, ...]
    per_board: PositiveCount
    required: PositiveCount
    spares: NonNegativeCount
    quantity: PositiveCount
    order_number: NonEmptyText
    order_number_kind: Literal["MPN", "DigiKey"]
    search_url: NonEmptyText


class PurchasingFinding(StrictModel):
    code: Identifier
    references: tuple[Identifier, ...] = ()
    message: NonEmptyText
    action: NonEmptyText


class PurchasingPlan(PurchasingSchemaModel):
    """Metadata readiness for human ordering review, never electrical approval."""

    schema_version: Literal["1"] = "1"
    status: Literal["NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    preferences: PurchasingPreferences
    components: tuple[PurchasingComponent, ...]
    lines: tuple[PurchasingLine, ...]
    findings: tuple[PurchasingFinding, ...]
    excluded_references: tuple[Identifier, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class DigiKeyHandoffQuantity(StrictModel):
    quantity: PositiveCount


class DigiKeyHandoffPart(StrictModel):
    requested_part_number: NonEmptyText = Field(alias="requestedPartNumber")
    quantities: Annotated[tuple[DigiKeyHandoffQuantity, ...], Field(min_length=1)]
    customer_reference: str = Field(alias="customerReference")
    notes: str


class DigiKeyHandoffPayload(RootModel[tuple[DigiKeyHandoffPart, ...]]):
    """DigiKey's third-party API accepts a root array of order lines."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffUrl(RootModel[str]):
    """DigiKey returns a JSON string, validated as an allowed URL by the adapter."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffReply(StrictModel):
    single_use_url: Annotated[
        str,
        StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
    ]


class DigiKeyHandoffResult(StrictModel):
    status: Literal["READY", "BLOCKED", "ERROR"]
    single_use_url: str | None = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False


class PurchasingReport(PurchasingSchemaModel):
    """Source-bound local parts assistant receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PARTS_TO_ORDER"] = "PARTS_TO_ORDER"
    project_id: Identifier
    status: Literal["BLOCKED", "NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False
    plan: PurchasingPlan | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    input_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    selected_runner: Literal["local", "container"] | None = None
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    artifacts: tuple[str, ...] = ()
    evidence: ContractCoachReport | None = None


class McpPurchasingPreferencesResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    status: Literal["CREATED", "UPDATED"]
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest | None = None
    after_sha256: Digest
    readback_sha256: Digest
    preferences: PurchasingPreferences


SurfaceAlignment = Literal["aligned", "partial", "cli_only", "mcp_only"]


class ToolCliSnapshot(StrictModel):
    module: NonEmptyText
    commands: tuple[NonEmptyText, ...] = ()
    options: tuple[NonEmptyText, ...] = ()


class ToolMcpSnapshot(StrictModel):
    name: Identifier
    parameters: tuple[Identifier, ...] = ()


class ToolSurfaceMapping(StrictModel):
    id: Identifier
    cli: tuple[NonEmptyText, ...] = ()
    mcp: tuple[Identifier, ...] = ()
    alignment: SurfaceAlignment
    reason: NonEmptyText
    scope: Literal["core", "administration", "adapter"]
    gaps: tuple[NonEmptyText, ...] = ()
    constraints: tuple[NonEmptyText, ...] = ()
    exception: NonEmptyText | None = None
    parity_tests: tuple[NonEmptyText, ...] = ()


class ToolSurfacesCatalog(StrictModel):
    schema_version: Literal["2"] = "2"
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]


class ToolSurfaceReport(StrictModel):
    schema_version: Literal["2"] = "2"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    coverage_status: Literal["PASS", "FAIL"]
    parity_status: Literal["PASS", "FAIL"]
    behavior_verification: Literal["NOT_RUN"] = "NOT_RUN"
    mcp_verification: Literal["LIVE", "STATIC_ONLY", "UNAVAILABLE"]
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]
    issues: tuple[PolicyIssue, ...] = ()
    notes: tuple[NonEmptyText, ...] = ()


class McpNativeScopeReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    run_directory: NonEmptyText
    report: CheckAllSummary


# Electrical analysis uses explicit engineering limits and model-review bindings.
FiniteMeasure = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeMeasure = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ElectricalPositive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
SpiceExpression = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_().,+*/ ^-]+$", min_length=1),
]


class AnalysisPending(StrictModel):
    """An unanswered engineering question; this can never supply passing evidence."""

    mode: Literal["pending"] = "pending"
    reason: NonEmptyText


class AnalysisNotApplicable(StrictModel):
    mode: Literal["not_applicable"]
    reason: NonEmptyText


class GroundDomain(StrictModel):
    net: NetName
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]


class GroundingAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    domains: Annotated[tuple[GroundDomain, ...], Field(min_length=1)]
    exempt_components: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)
    reviewed_return_exceptions: Mapping[NetName, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def distinct_domains(self) -> GroundingAnalysis:
        names = [domain.net for domain in self.domains]
        pins = [pin for domain in self.domains for pin in domain.pins]
        if len(set(names)) != len(names) or len(set(pins)) != len(pins):
            raise ValueError("Ground domains and their pins must be unique")
        if any(name.startswith("/") for name in (*names, *self.reviewed_return_exceptions)):
            raise ValueError("Use net names without the leading slash, as in the native contract")
        if set(names) & set(self.reviewed_return_exceptions):
            raise ValueError("A return net cannot be both a ground domain and an exception")
        return self


class PcbReturnEndpointRequirement(StrictModel):
    """One exact PCB pad and its independently reviewed expected net/footprint."""

    pad: Reference
    net: NetName
    footprint: NonEmptyText

    @model_validator(mode="after")
    def exact_pad_reference(self) -> PcbReturnEndpointRequirement:
        if self.pad.count(".") != 1:
            raise ValueError("PCB return endpoints must use an exact reference.pad number")
        if self.net.startswith("/"):
            raise ValueError("Use the native net name without a leading slash")
        return self


class PcbReturnBondRequirement(StrictModel):
    """One reviewed, fitted KiCad net-tie footprint and its exact bridge groups."""

    reference: Identifier
    footprint: NonEmptyText
    pad_groups: Annotated[tuple[tuple[Reference, ...], ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_bridge_groups(self) -> PcbReturnBondRequirement:
        if not self.pad_groups or any(len(group) < 2 for group in self.pad_groups):
            raise ValueError("Each declared PCB return bond group needs at least two exact pads")
        pads = [pad for group in self.pad_groups for pad in group]
        if any(pad.count(".") != 1 for pad in pads):
            raise ValueError("PCB return bond groups must use exact reference.pad numbers")
        if len({pad.casefold() for pad in pads}) != len(pads):
            raise ValueError("PCB return bond pads must occur in exactly one declared group")
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in pads):
            raise ValueError("PCB return bond pads must belong to the declared component")
        return self


class PcbReturnDomainRequirement(StrictModel):
    """A required physical return domain; separate domains declare isolation."""

    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "bonded"]
    endpoints: Annotated[tuple[PcbReturnEndpointRequirement, ...], Field(min_length=2)]
    bonds: tuple[PcbReturnBondRequirement, ...] = ()

    @model_validator(mode="after")
    def valid_return_topology(self) -> PcbReturnDomainRequirement:
        pads = [item.pad.casefold() for item in self.endpoints]
        if len(set(pads)) != len(pads):
            raise ValueError("PCB return domain endpoints must be unique")
        if len({item.reference.casefold() for item in self.bonds}) != len(self.bonds):
            raise ValueError("PCB return bond component references must be unique")
        if self.topology == "direct":
            if self.bonds:
                raise ValueError("Direct PCB return domains cannot declare net-tie bonds")
            if len({item.net.casefold() for item in self.endpoints}) != 1:
                raise ValueError("Direct PCB return endpoints must declare one common net")
        else:
            if not self.bonds:
                raise ValueError("Bonded PCB return domains must declare exact net-tie groups")
            if len({item.net.casefold() for item in self.endpoints}) < 2:
                raise ValueError(
                    "Bonded PCB return domains must declare at least two distinct nets"
                )
        return self


class PcbReturnPathsAnalysis(StrictModel):
    """Source-bound PCB copper connectivity requirements for reviewed returns."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    domains: Annotated[tuple[PcbReturnDomainRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_domains_and_endpoints(self) -> PcbReturnPathsAnalysis:
        if len({domain.id.casefold() for domain in self.domains}) != len(self.domains):
            raise ValueError("PCB return domain IDs must be unique")
        pads = [item.pad.casefold() for domain in self.domains for item in domain.endpoints]
        bonds = [bond.reference.casefold() for domain in self.domains for bond in domain.bonds]
        if len(set(pads)) != len(pads):
            raise ValueError("PCB return endpoint pads must belong to one domain only")
        if len(set(bonds)) != len(bonds):
            raise ValueError("PCB return bond components must belong to one domain only")
        return self


class PcbZoneIdentity(StrictModel):
    """Native KiCad identity for one copper zone on one board layer."""

    uuid: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    layer: NonEmptyText


class PcbZoneFilledIslandObservation(StrictModel):
    """Canonical integer-nanometer outline and holes for one filled zone island."""

    island_index: NonNegativeCount
    outline_nm: tuple[tuple[int, int], ...]
    holes_nm: tuple[tuple[tuple[int, int], ...], ...] = ()

    @model_validator(mode="after")
    def valid_zone_contours(self) -> PcbZoneFilledIslandObservation:
        for label, ring in (
            ("outline", self.outline_nm),
            *(("hole", hole) for hole in self.holes_nm),
        ):
            if len(ring) < 3 or len(set(ring)) < 3 or ring[0] == ring[-1]:
                raise ValueError(
                    f"Native PCB filled-island {label} needs three distinct open-ring vertices"
                )
            area_twice = sum(
                first[0] * ring[(index + 1) % len(ring)][1]
                - ring[(index + 1) % len(ring)][0] * first[1]
                for index, first in enumerate(ring)
            )
            if area_twice == 0:
                raise ValueError(f"Native PCB filled-island {label} has zero area")
        return self


class PcbRuleAreaPolygonObservation(StrictModel):
    """Canonical authored outline and holes for one native PCB rule area."""

    outline_nm: tuple[tuple[int, int], ...]
    holes_nm: tuple[tuple[tuple[int, int], ...], ...] = ()

    @model_validator(mode="after")
    def valid_rule_area_contours(self) -> PcbRuleAreaPolygonObservation:
        for label, ring in (
            ("outline", self.outline_nm),
            *(("hole", hole) for hole in self.holes_nm),
        ):
            if len(ring) < 3 or len(set(ring)) < 3 or ring[0] == ring[-1]:
                raise ValueError(
                    f"Native PCB rule-area {label} needs three distinct open-ring vertices"
                )
            area_twice = sum(
                first[0] * ring[(index + 1) % len(ring)][1]
                - ring[(index + 1) % len(ring)][0] * first[1]
                for index, first in enumerate(ring)
            )
            if area_twice == 0:
                raise ValueError(f"Native PCB rule-area {label} has zero area")
        return self


class PcbRuleAreaObservation(StrictModel):
    """Native KiCad keepout or placement rule area and its effective restrictions."""

    uuid: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    name: str
    layers: tuple[NonEmptyText, ...]
    net: NetName | None
    polygons: Annotated[tuple[PcbRuleAreaPolygonObservation, ...], Field(min_length=1)]
    forbids_tracks: bool
    forbids_vias: bool
    forbids_pads: bool
    forbids_zone_fills: bool
    forbids_footprints: bool

    @model_validator(mode="after")
    def unique_rule_area_layers(self) -> PcbRuleAreaObservation:
        if len({item.casefold() for item in self.layers}) != len(self.layers):
            raise ValueError("Native PCB rule-area layers must be unique")
        if len({(item.outline_nm, item.holes_nm) for item in self.polygons}) != len(self.polygons):
            raise ValueError("Native PCB rule-area polygons must be unique")
        return self


class PcbZoneObservation(PcbZoneIdentity):
    """Filled copper zone metadata and connected island count from KiCad."""

    name: str
    net: NetName | None
    filled_island_count: NonNegativeCount
    unanchored_pad_island_indexes: tuple[NonNegativeCount, ...] = ()
    filled_islands: tuple[PcbZoneFilledIslandObservation, ...] = ()

    @model_validator(mode="after")
    def unique_unanchored_islands(self) -> PcbZoneObservation:
        if len(set(self.unanchored_pad_island_indexes)) != len(self.unanchored_pad_island_indexes):
            raise ValueError("Native PCB unanchored-to-pad island indexes must be unique")
        island_indexes = {item.island_index for item in self.filled_islands}
        if len(island_indexes) != len(self.filled_islands):
            raise ValueError("Native PCB filled-island contours must have unique indexes")
        if any(index >= self.filled_island_count for index in island_indexes):
            raise ValueError("Native PCB filled-island contour index exceeds the island count")
        return self


class PcbZoneIslandIdentity(PcbZoneIdentity):
    """Exact filled-island index within one native zone and layer."""

    island_index: NonNegativeCount


class PcbViaObservation(StrictModel):
    """Stable native via geometry and layer transition in one connected component."""

    id: Digest
    net: NetName | None
    x_nm: int
    y_nm: int
    start_layer: NonEmptyText
    end_layer: NonEmptyText
    diameter_nm: PositiveCount
    drill_nm: PositiveCount
    kind: Literal["through", "blind", "buried", "micro"]
    multiplicity: PositiveCount

    @model_validator(mode="after")
    def distinct_layer_transition(self) -> PcbViaObservation:
        if self.start_layer.casefold() == self.end_layer.casefold():
            raise ValueError("Native via evidence must span at least two copper layers")
        return self


PcbTrackUuid = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
]


class PcbTrackObservation(StrictModel):
    """Native geometry and endpoint contacts for one KiCad copper track item."""

    uuid: PcbTrackUuid
    net: NetName | None
    layer: NonEmptyText
    width_nm: PositiveCount
    start_nm: tuple[int, int]
    end_nm: tuple[int, int]
    geometry_kind: Literal["segment", "arc"] | None = None
    start_pads: tuple[Reference, ...] = ()
    end_pads: tuple[Reference, ...] = ()
    start_vias: tuple[Digest, ...] = ()
    end_vias: tuple[Digest, ...] = ()
    start_tracks: tuple[PcbTrackUuid, ...] = ()
    end_tracks: tuple[PcbTrackUuid, ...] = ()

    @model_validator(mode="after")
    def unique_endpoint_contacts(self) -> PcbTrackObservation:
        for label, contacts in (
            ("start pads", self.start_pads),
            ("end pads", self.end_pads),
            ("start vias", self.start_vias),
            ("end vias", self.end_vias),
            ("start tracks", self.start_tracks),
            ("end tracks", self.end_tracks),
        ):
            if len({item.casefold() for item in contacts}) != len(contacts):
                raise ValueError(f"Native PCB track {label} must be unique")
        if any(
            item.casefold() == self.uuid.casefold()
            for item in (*self.start_tracks, *self.end_tracks)
        ):
            raise ValueError("Native PCB track endpoint contacts cannot refer to the track itself")
        return self


class PcbPadConnectivityObservation(StrictModel):
    """Native pad identity, copper-component members, and directly touched zone islands."""

    pad: Reference
    net: NetName | None
    footprint: NonEmptyText
    dnp: bool
    connected_pads: tuple[Reference, ...]
    connected_zones: tuple[PcbZoneIdentity, ...]
    connected_islands: tuple[PcbZoneIslandIdentity, ...]
    connected_vias: tuple[Digest, ...] = ()
    positions_nm: tuple[tuple[int, int], ...] = ()

    @model_validator(mode="after")
    def complete_pad_reference(self) -> PcbPadConnectivityObservation:
        if self.pad.count(".") != 1 or self.pad.casefold() not in {
            item.casefold() for item in self.connected_pads
        }:
            raise ValueError(
                "Native PCB pad evidence needs its exact reference and own connectivity"
            )
        if len({item.casefold() for item in self.connected_pads}) != len(self.connected_pads):
            raise ValueError("Native PCB connected pad references must be unique")
        if len(set(self.connected_vias)) != len(self.connected_vias):
            raise ValueError("Native PCB connected via identities must be unique")
        if len(set(self.positions_nm)) != len(self.positions_nm):
            raise ValueError("Native PCB physical pad centers must be unique")
        zone_keys = {(item.uuid.casefold(), item.layer.casefold()) for item in self.connected_zones}
        if len(zone_keys) != len(self.connected_zones):
            raise ValueError("Native PCB connected zone identities must be unique")
        island_keys = {
            (item.uuid.casefold(), item.layer.casefold(), item.island_index)
            for item in self.connected_islands
        }
        if len(island_keys) != len(self.connected_islands):
            raise ValueError("Native PCB connected island identities must be unique")
        return self


class PcbFootprintPlacementObservation(StrictModel):
    """Native placement transform and identity for one referenced PCB footprint."""

    reference: Reference
    footprint: NonEmptyText
    dnp: bool
    position_nm: tuple[int, int]
    orientation_microdegrees: Annotated[int, Field(ge=0, lt=360_000_000)]
    side: Literal["F.Cu", "B.Cu"]


class PcbAccessProbeObservation(StrictModel):
    """Target aperture and nearest different-net pad for one configured probe surface."""

    endpoint: Reference
    side: Literal["front", "back"]
    target_net: NetName | None
    target_exposed: bool
    obstacle: Reference | None
    obstacle_net: NetName | None
    distance_nm: NonNegativeCount | None
    target_aperture_shape: Literal["circle", "unsupported"] | None = None
    target_aperture_diameter_nm: NonNegativeCount | None = None

    @model_validator(mode="after")
    def complete_nearest_obstacle(self) -> PcbAccessProbeObservation:
        if self.obstacle is None:
            if self.obstacle_net is not None or self.distance_nm is not None:
                raise ValueError("Native probe obstacle fields must be present together")
            if not self.target_exposed and self.distance_nm is not None:
                raise ValueError("An unavailable target side cannot have an obstacle distance")
        elif self.distance_nm is None:
            raise ValueError("Native probe obstacle needs its measured distance")
        elif not self.target_exposed:
            raise ValueError("An unavailable target side cannot have an obstacle")
        elif self.obstacle.casefold() == self.endpoint.casefold():
            raise ValueError("Native probe obstacle cannot be the target endpoint")
        elif self.target_net is not None and self.obstacle_net == self.target_net:
            raise ValueError("Native probe obstacle must be on another net or unconnected")
        if self.target_aperture_shape == "circle":
            if self.target_aperture_diameter_nm is None or self.target_aperture_diameter_nm <= 0:
                raise ValueError("Circular native probe aperture needs a positive diameter")
        elif self.target_aperture_diameter_nm is not None:
            raise ValueError("Native probe aperture diameter requires a supported circular shape")
        if not self.target_exposed and self.target_aperture_shape is not None:
            raise ValueError("Unavailable target side cannot have aperture geometry")
        return self


class PcbNetTieObservation(StrictModel):
    """Native KiCad net-tie pad groups for one placed footprint."""

    reference: Identifier
    footprint: NonEmptyText
    dnp: bool
    pad_groups: tuple[tuple[Reference, ...], ...]

    @model_validator(mode="after")
    def scoped_unique_pad_groups(self) -> PcbNetTieObservation:
        pads = [pad for group in self.pad_groups for pad in group]
        if any(len(group) < 2 for group in self.pad_groups):
            raise ValueError("Native net-tie groups need at least two pads")
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in pads):
            raise ValueError("Native net-tie pad groups must belong to their footprint")
        if len({pad.casefold() for pad in pads}) != len(pads):
            raise ValueError("Native net-tie pads must occur in exactly one group")
        return self


class PcbConnectivitySnapshot(StrictModel):
    """Retained, deterministic native connectivity evidence for an exact board."""

    schema_version: Literal["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"] = "3"
    board_sha256: Digest
    kicad_version: NonEmptyText
    image: NonEmptyText
    probe_sha256: Digest
    zones_refilled: bool
    pads: tuple[PcbPadConnectivityObservation, ...]
    net_ties: tuple[PcbNetTieObservation, ...]
    zones: tuple[PcbZoneObservation, ...]
    vias: tuple[PcbViaObservation, ...] = ()
    access_probe_observations: tuple[PcbAccessProbeObservation, ...] = ()
    access_probe_requests_sha256: Digest | None = None
    tracks: tuple[PcbTrackObservation, ...] = ()
    copper_layers: tuple[NonEmptyText, ...] = ()
    rule_areas: tuple[PcbRuleAreaObservation, ...] = ()
    footprints: tuple[PcbFootprintPlacementObservation, ...] = ()

    @model_validator(mode="after")
    def unique_observed_items(self) -> PcbConnectivitySnapshot:
        if len({item.pad.casefold() for item in self.pads}) != len(self.pads):
            raise ValueError("Native PCB evidence contains duplicate pad references")
        if len({item.reference.casefold() for item in self.net_ties}) != len(self.net_ties):
            raise ValueError("Native PCB evidence contains duplicate net-tie references")
        via_ids = [item.id for item in self.vias]
        if len(set(via_ids)) != len(via_ids):
            raise ValueError("Native PCB evidence contains duplicate via identities")
        track_ids = [item.uuid.casefold() for item in self.tracks]
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("Native PCB evidence contains duplicate track identities")
        if self.schema_version in {"3", "4", "5", "6", "7", "8", "9", "10", "11", "12"}:
            if "vias" not in self.model_fields_set:
                raise ValueError("Native PCB schema v3 requires an explicit via inventory")
            if any("connected_vias" not in item.model_fields_set for item in self.pads):
                raise ValueError("Native PCB schema v3 requires explicit per-pad via evidence")
            if any(
                "unanchored_pad_island_indexes" not in item.model_fields_set for item in self.zones
            ):
                raise ValueError(
                    "Native PCB schema v3 requires explicit zone island-anchor evidence"
                )
        zone_keys = {(item.uuid.casefold(), item.layer.casefold()) for item in self.zones}
        if len(zone_keys) != len(self.zones):
            raise ValueError("Native PCB evidence contains duplicate zone identities")
        known = {item.pad for item in self.pads}
        pads_by_name = {item.pad.casefold(): item for item in self.pads}
        if any(not set(item.connected_pads) <= known for item in self.pads):
            raise ValueError("Native PCB connectivity refers to a pad absent from the board")
        vias_by_id = {item.id: item for item in self.vias}
        for pad in self.pads:
            if not set(pad.connected_vias) <= vias_by_id.keys():
                raise ValueError("Native PCB connectivity refers to a via absent from the board")
            for via_id in pad.connected_vias:
                via = vias_by_id[via_id]
                if via.net != pad.net:
                    raise ValueError("Native PCB pad and connected via have different nets")
        zones_by_key = {(item.uuid.casefold(), item.layer.casefold()): item for item in self.zones}
        mapped_islands_by_zone: dict[tuple[str, str], set[int]] = {}
        for pad in self.pads:
            connected_zone_keys = {
                (identity.uuid.casefold(), identity.layer.casefold())
                for identity in pad.connected_zones
            }
            mapped_zone_keys: set[tuple[str, str]] = set()
            for identity in pad.connected_zones:
                zone = zones_by_key.get((identity.uuid.casefold(), identity.layer.casefold()))
                if zone is None:
                    raise ValueError("Native PCB pad refers to a zone absent from the board")
                if zone.net != pad.net:
                    raise ValueError("Native PCB pad and connected zone have different nets")
            for island in pad.connected_islands:
                key = (island.uuid.casefold(), island.layer.casefold())
                zone = zones_by_key.get(key)
                if zone is None:
                    raise ValueError(
                        "Native PCB pad refers to an island in a zone absent from the board"
                    )
                if key not in connected_zone_keys:
                    raise ValueError("Native PCB pad island is not in its connected zone evidence")
                if island.island_index >= zone.filled_island_count:
                    raise ValueError(
                        "Native PCB pad island index exceeds the filled zone island count"
                    )
                mapped_zone_keys.add(key)
                mapped_islands_by_zone.setdefault(key, set()).add(island.island_index)
            if mapped_zone_keys != connected_zone_keys:
                raise ValueError("Native PCB connected zones need exact filled-island evidence")
        if self.schema_version in {"3", "4", "5", "6", "7", "8", "9", "10", "11", "12"}:
            for key, zone in zones_by_key.items():
                expected_unanchored = set(range(zone.filled_island_count)) - (
                    mapped_islands_by_zone.get(key, set())
                )
                if set(zone.unanchored_pad_island_indexes) != expected_unanchored:
                    raise ValueError(
                        "Native PCB zone unanchored-to-pad island indexes do not match "
                        "the pad-to-island evidence"
                    )
        if self.schema_version in {"4", "5", "6", "7", "8", "9", "10", "11", "12"}:
            if "access_probe_observations" not in self.model_fields_set:
                raise ValueError("Native PCB schema v4+ requires explicit probe observations")
            if "access_probe_requests_sha256" not in self.model_fields_set:
                raise ValueError("Native PCB schema v4+ requires explicit probe request evidence")
            if bool(self.access_probe_observations) != (
                self.access_probe_requests_sha256 is not None
            ):
                raise ValueError("Native PCB probe observations need matching request evidence")
        if self.schema_version in {"5", "6", "7", "8", "9", "10", "11", "12"} and any(
            "positions_nm" not in item.model_fields_set or not item.positions_nm
            for item in self.pads
        ):
            raise ValueError("Native PCB schema v5+ requires physical pad-center positions")
        if (
            self.schema_version in {"6", "7", "8", "9", "10", "11", "12"}
            and "tracks" not in self.model_fields_set
        ):
            raise ValueError(
                f"Native PCB schema v{self.schema_version} requires an explicit track inventory"
            )
        if self.schema_version in {"7", "8", "9", "10", "11", "12"}:
            if "copper_layers" not in self.model_fields_set or len(self.copper_layers) < 2:
                raise ValueError(
                    f"Native PCB schema v{self.schema_version} requires the actual copper stack inventory"
                )
            if len({item.casefold() for item in self.copper_layers}) != len(self.copper_layers):
                raise ValueError("Native PCB copper stack contains duplicate layer names")
        if self.schema_version in {"8", "9", "10", "11", "12"}:
            tracks_by_uuid = {item.uuid.casefold(): item for item in self.tracks}
            for track in self.tracks:
                if any(
                    field not in track.model_fields_set
                    for field in (
                        "geometry_kind",
                        "start_pads",
                        "end_pads",
                        "start_vias",
                        "end_vias",
                        "start_tracks",
                        "end_tracks",
                    )
                ):
                    raise ValueError(
                        f"Native PCB schema v{self.schema_version} requires explicit track geometry and endpoint contacts"
                    )
                if track.geometry_kind is None:
                    raise ValueError(
                        f"Native PCB schema v{self.schema_version} track geometry kind cannot be unavailable"
                    )
                if any(
                    pad.casefold() not in pads_by_name
                    for pad in (*track.start_pads, *track.end_pads)
                ):
                    raise ValueError("Native PCB track endpoint refers to an absent pad")
                if any(
                    pads_by_name[pad.casefold()].net != track.net
                    for pad in (*track.start_pads, *track.end_pads)
                ):
                    raise ValueError("Native PCB track endpoint pad has a different net")
                if any(via not in vias_by_id for via in (*track.start_vias, *track.end_vias)):
                    raise ValueError("Native PCB track endpoint refers to an absent via")
                if any(
                    vias_by_id[via].net != track.net for via in (*track.start_vias, *track.end_vias)
                ):
                    raise ValueError("Native PCB track endpoint via has a different net")
                if any(
                    contact.casefold() not in tracks_by_uuid
                    for contact in (*track.start_tracks, *track.end_tracks)
                ):
                    raise ValueError("Native PCB track endpoint refers to an absent track")
                if any(
                    tracks_by_uuid[contact.casefold()].net != track.net
                    for contact in (*track.start_tracks, *track.end_tracks)
                ):
                    raise ValueError("Native PCB track endpoint contact has a different net")
        if self.schema_version in {"9", "10", "11", "12"}:
            for zone in self.zones:
                if "filled_islands" not in zone.model_fields_set:
                    raise ValueError(
                        "Native PCB schema v9 requires explicit filled-island contour geometry"
                    )
                indexes = {item.island_index for item in zone.filled_islands}
                if indexes != set(range(zone.filled_island_count)):
                    raise ValueError(
                        "Native PCB schema v9 needs one contour for every filled zone island"
                    )
        probe_keys = [
            (item.endpoint.casefold(), item.side.casefold())
            for item in self.access_probe_observations
        ]
        if len(set(probe_keys)) != len(probe_keys):
            raise ValueError("Native PCB probe endpoint and side identities must be unique")
        for item in self.access_probe_observations:
            target = pads_by_name.get(item.endpoint.casefold())
            if target is None:
                raise ValueError("Native PCB probe observation refers to an unobserved pad")
            if target.net != item.target_net:
                raise ValueError("Native PCB probe target net differs from its pad inventory")
            if item.obstacle is not None:
                obstacle = pads_by_name.get(item.obstacle.casefold())
                if obstacle is None:
                    raise ValueError(
                        "Native PCB probe observation refers to an unobserved obstacle pad"
                    )
                if obstacle.net != item.obstacle_net:
                    raise ValueError("Native PCB probe obstacle net differs from its pad inventory")
            if self.schema_version in {"10", "11", "12"} and any(
                field not in item.model_fields_set
                for field in ("target_aperture_shape", "target_aperture_diameter_nm")
            ):
                raise ValueError(
                    "Native PCB schema v10+ requires explicit target aperture evidence"
                )
        if self.schema_version in {"11", "12"}:
            if "rule_areas" not in self.model_fields_set:
                raise ValueError(
                    f"Native PCB schema v{self.schema_version} requires explicit rule-area evidence"
                )
            rule_area_ids = [item.uuid.casefold() for item in self.rule_areas]
            if len(set(rule_area_ids)) != len(rule_area_ids):
                raise ValueError("Native PCB evidence contains duplicate rule-area identities")
            for area in self.rule_areas:
                if "name" not in area.model_fields_set:
                    raise ValueError("Native PCB schema v11 requires explicit rule-area names")
                copper_layers = {layer.casefold() for layer in self.copper_layers}
                if any(layer.casefold() not in copper_layers for layer in area.layers):
                    raise ValueError("Native PCB rule-area layers are outside the copper stack")
        if self.schema_version == "12":
            if "footprints" not in self.model_fields_set:
                raise ValueError(
                    "Native PCB schema v12 requires explicit footprint placement evidence"
                )
            footprint_rows = {item.reference.casefold(): item for item in self.footprints}
            if len(footprint_rows) != len(self.footprints):
                raise ValueError("Native PCB evidence contains duplicate footprint references")
            if any(item.side not in self.copper_layers for item in self.footprints):
                raise ValueError("Native PCB footprint side is outside the copper stack")
            for pad in self.pads:
                reference = pad.pad.rsplit(".", 1)[0].casefold()
                footprint = footprint_rows.get(reference)
                if footprint is None:
                    raise ValueError("Native PCB pad refers to an unobserved footprint placement")
                if footprint.footprint != pad.footprint or footprint.dnp != pad.dnp:
                    raise ValueError("Native PCB pad identity differs from its footprint placement")
        for tie in self.net_ties:
            for member in (pad for group in tie.pad_groups for pad in group):
                observed = pads_by_name.get(member.casefold())
                if (
                    observed is None
                    or observed.footprint != tie.footprint
                    or observed.dnp != tie.dnp
                ):
                    raise ValueError(
                        "Native net-tie group differs from its observed footprint pads"
                    )
        return self


class PinRelationshipRule(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["common_net", "separate_nets", "unconnected"]
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    net: NetName | None = None

    @model_validator(mode="after")
    def valid_relationship(self) -> PinRelationshipRule:
        if len(set(self.pins)) != len(self.pins):
            raise ValueError("Pin relationship pins must be unique")
        if self.topology in {"common_net", "separate_nets"} and len(self.pins) < 2:
            raise ValueError("Connected pin relationships need at least two pins")
        if self.topology != "common_net" and self.net is not None:
            raise ValueError("Only common-net relationships can name one net")
        if self.net is not None and self.net.startswith("/"):
            raise ValueError("Use the native net name without a leading slash")
        return self


class PinConnectivityAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    rules: Annotated[tuple[PinRelationshipRule, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_rules(self) -> PinConnectivityAnalysis:
        identifiers = [rule.id for rule in self.rules]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Pin relationship IDs must be unique")
        return self


class I2cPullupArrayChannelRequirement(StrictModel):
    """Reviewed pin and nominal resistance mapping for one array channel."""

    id: Identifier
    signal_pin: Reference
    rail_pin: Reference
    signal_net: NetName
    rail_net: NetName
    resistance_ohms: ElectricalPositive
    basis: NonEmptyText

    @model_validator(mode="after")
    def distinct_channel_endpoints(self) -> I2cPullupArrayChannelRequirement:
        if self.signal_pin.casefold() == self.rail_pin.casefold():
            raise ValueError("I2C resistor-array channel signal and rail pins must differ")
        if self.signal_net == self.rail_net:
            raise ValueError("I2C resistor-array channel signal and rail nets must differ")
        return self


class I2cPullupArrayRequirement(StrictModel):
    """Exact component and complete pin disposition for a mapped resistor array."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_value: NonEmptyText
    basis: NonEmptyText
    channels: Annotated[tuple[I2cPullupArrayChannelRequirement, ...], Field(min_length=1)]
    unmapped_pin_reasons: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def component_pin_dispositions_are_unique(self) -> I2cPullupArrayRequirement:
        prefix = f"{self.reference}."
        channel_pins = [
            pin for channel in self.channels for pin in (channel.signal_pin, channel.rail_pin)
        ]
        all_pins = (*channel_pins, *self.unmapped_pin_reasons)
        if any(not pin.casefold().startswith(prefix.casefold()) for pin in all_pins):
            raise ValueError("I2C resistor-array pins must belong to its component")
        normalized = [pin.casefold() for pin in all_pins]
        if len(set(normalized)) != len(normalized):
            raise ValueError("I2C resistor-array channel and unlisted pins must be unique")
        if len({channel.id.casefold() for channel in self.channels}) != len(self.channels):
            raise ValueError("I2C resistor-array channel IDs must be unique")
        return self


class I2cPullupInputVoltageLimit(StrictModel):
    """Reviewed maximum bus voltage for one exact native I2C input pin."""

    pin: Reference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    limit_kind: Literal["operating", "absolute_maximum"]
    maximum_bus_voltage_v: ElectricalPositive
    limit_basis: NonEmptyText

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("I2C voltage-limit pins must use COMPONENT.PIN form")
        return value


class I2cPullupVoltageCompatibilityRequirement(StrictModel):
    """Project-authored rail ceiling and exact input limits for one bus line."""

    input_scope_basis: NonEmptyText
    maximum_rail_voltage_v: ElectricalPositive
    rail_basis: NonEmptyText
    input_limits: Annotated[tuple[I2cPullupInputVoltageLimit, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_input_pins(self) -> I2cPullupVoltageCompatibilityRequirement:
        if len({item.pin.casefold() for item in self.input_limits}) != len(self.input_limits):
            raise ValueError("I2C voltage-limit input pins must be unique")
        return self


class I2cPullupElectricalWindow(StrictModel):
    """Reviewed I2C pull-up limits for sink current and RC rise time."""

    maximum_pullup_voltage_v: ElectricalPositive
    pullup_voltage_basis: NonEmptyText
    maximum_low_level_voltage_v: NonNegativeMeasure
    low_level_voltage_basis: NonEmptyText
    minimum_sink_current_ma: ElectricalPositive
    sink_current_basis: NonEmptyText
    maximum_bus_capacitance_pf: CapacitancePf
    bus_capacitance_basis: NonEmptyText
    maximum_rise_time_ns: ElectricalPositive
    rise_time_basis: NonEmptyText
    maximum_per_resistor_tolerance_percent: (
        Annotated[float, Field(gt=0, lt=100, allow_inf_nan=False)] | None
    ) = None
    resistor_tolerance_basis: NonEmptyText | None = None

    @model_validator(mode="after")
    def valid_pullup_voltage_window(self) -> I2cPullupElectricalWindow:
        if self.maximum_pullup_voltage_v <= self.maximum_low_level_voltage_v:
            raise ValueError(
                "I2C pull-up maximum voltage must exceed the maximum low-level voltage"
            )
        if (self.maximum_per_resistor_tolerance_percent is None) != (
            self.resistor_tolerance_basis is None
        ):
            raise ValueError("I2C resistor tolerance and its basis must be supplied together")
        return self


class I2cPullupLineRequirement(StrictModel):
    """Reviewed local pull-up topology and nominal equivalent range for one line."""

    net: NetName
    rail: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive
    voltage_compatibility: I2cPullupVoltageCompatibilityRequirement | None = None
    electrical_window: I2cPullupElectricalWindow | None = None

    @model_validator(mode="after")
    def valid_range(self) -> I2cPullupLineRequirement:
        if self.net == self.rail:
            raise ValueError("An I2C signal net and its pull-up rail must be distinct")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("I2C pull-up maximum resistance is below its minimum")
        if (
            self.electrical_window is not None
            and self.voltage_compatibility is not None
            and self.electrical_window.maximum_pullup_voltage_v
            != self.voltage_compatibility.maximum_rail_voltage_v
        ):
            raise ValueError(
                "I2C pull-up electrical-window and voltage-compatibility rail ceilings must match"
            )
        return self


class I2cPullupSeriesResistorRequirement(StrictModel):
    """Exact symbol, footprint, directed path, and nominal range for one chain leg."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    from_net: NetName
    to_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_series_leg(self) -> I2cPullupSeriesResistorRequirement:
        if self.from_net == self.to_net:
            raise ValueError("I2C series pull-up resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("I2C series resistor maximum is below its minimum")
        return self


class I2cPullupSeriesPathRequirement(StrictModel):
    """Reviewed ordered chain from one I2C signal net to its pull-up rail."""

    id: Identifier
    basis: NonEmptyText
    signal_net: NetName
    rail_net: NetName
    resistors: Annotated[tuple[I2cPullupSeriesResistorRequirement, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def ordered_simple_path(self) -> I2cPullupSeriesPathRequirement:
        if self.signal_net == self.rail_net:
            raise ValueError("I2C series pull-up signal and rail nets must differ")
        references = [item.reference.casefold() for item in self.resistors]
        if len(set(references)) != len(references):
            raise ValueError("I2C series pull-up resistor references must be unique")
        if self.resistors[0].from_net != self.signal_net:
            raise ValueError("I2C series pull-up path must start at its signal net")
        if self.resistors[-1].to_net != self.rail_net:
            raise ValueError("I2C series pull-up path must end at its declared rail")
        for first, second in zip(self.resistors, self.resistors[1:], strict=False):
            if first.to_net != second.from_net:
                raise ValueError("I2C series pull-up resistor legs must form one ordered path")
        path_nets = (self.signal_net, *(item.to_net for item in self.resistors))
        if len({net.casefold() for net in path_nets}) != len(path_nets):
            raise ValueError("I2C series pull-up path cannot revisit a net")
        return self


class I2cPullupBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    sda: I2cPullupLineRequirement
    scl: I2cPullupLineRequirement

    @model_validator(mode="after")
    def distinct_bus_nets(self) -> I2cPullupBusRequirement:
        if self.sda.net == self.scl.net:
            raise ValueError("I2C SDA and SCL requirements must name distinct signal nets")
        if self.sda.net == self.scl.rail or self.scl.net == self.sda.rail:
            raise ValueError("An I2C pull-up rail cannot be the other bus signal net")
        return self


class I2cPullupAnalysis(StrictModel):
    """Project-authored direct, series, and mapped-array I2C pull-up requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[I2cPullupBusRequirement, ...], Field(min_length=1)]
    arrays: tuple[I2cPullupArrayRequirement, ...] = ()
    series_paths: tuple[I2cPullupSeriesPathRequirement, ...] = ()

    @model_validator(mode="after")
    def unique_bus_ids_and_nets(self) -> I2cPullupAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("I2C pull-up bus IDs must be unique")
        signal_nets = [net for bus in self.buses for net in (bus.sda.net, bus.scl.net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("I2C pull-up signal nets must be unique across configured buses")
        line_pairs = {(line.net, line.rail) for bus in self.buses for line in (bus.sda, bus.scl)}
        array_references = [array.reference.casefold() for array in self.arrays]
        if len(set(array_references)) != len(array_references):
            raise ValueError("I2C resistor-array references must be unique")
        series_path_ids = [path.id.casefold() for path in self.series_paths]
        if len(set(series_path_ids)) != len(series_path_ids):
            raise ValueError("I2C series pull-up path IDs must be unique")
        series_references = [
            resistor.reference.casefold()
            for path in self.series_paths
            for resistor in path.resistors
        ]
        if len(set(series_references)) != len(series_references):
            raise ValueError("I2C series pull-up resistor references must be unique")
        if set(array_references) & set(series_references):
            raise ValueError("I2C resistor arrays and series paths cannot reuse a component")
        for array in self.arrays:
            for channel in array.channels:
                if (channel.signal_net, channel.rail_net) not in line_pairs:
                    raise ValueError(
                        "I2C resistor-array channels must match a configured signal/rail pair"
                    )
        for path in self.series_paths:
            if (path.signal_net, path.rail_net) not in line_pairs:
                raise ValueError(
                    "I2C series pull-up paths must match a configured signal/rail pair"
                )
        return self


class SpiPinNetRequirement(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiPinUnconnectedRequirement(StrictModel):
    mode: Literal["unconnected"] = "unconnected"
    pin: Reference

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiMisoConnectedRequirement(StrictModel):
    mode: Literal["connected"]
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiPinNotPresent(StrictModel):
    mode: Literal["not_present"]
    reason: NonEmptyText


SpiMisoRequirement = Annotated[
    SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement | SpiPinNotPresent,
    Field(discriminator="mode"),
]


class SpiControllerRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    sck: SpiPinNetRequirement
    mosi: SpiPinNetRequirement
    miso: SpiMisoRequirement
    chip_selects: Annotated[tuple[SpiPinNetRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def controller_pin_ownership_and_selects(self) -> SpiControllerRequirement:
        signals: tuple[
            SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ...,
        ] = (
            self.sck,
            self.mosi,
            *((self.miso,) if not isinstance(self.miso, SpiPinNotPresent) else ()),
            *self.chip_selects,
        )
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in signals
        ):
            raise ValueError("SPI controller pins must belong to the declared controller")
        pins = [item.pin.casefold() for item in signals]
        if len(set(pins)) != len(pins):
            raise ValueError("SPI controller signal and chip-select pins must be unique")
        select_nets = [item.net for item in self.chip_selects]
        if len(set(select_nets)) != len(select_nets):
            raise ValueError("SPI controller chip-select nets must be unique")
        data_nets = [self.sck.net, self.mosi.net]
        if isinstance(self.miso, SpiMisoConnectedRequirement):
            data_nets.append(self.miso.net)
        if len(set(data_nets)) != len(data_nets):
            raise ValueError("SPI clock and connected data nets must be distinct")
        if set(data_nets) & set(select_nets):
            raise ValueError("SPI chip-select nets must be separate from clock and data nets")
        return self


class SpiDeviceRequirement(StrictModel):
    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    sck: SpiPinNetRequirement
    mosi: SpiPinNetRequirement
    miso: SpiMisoRequirement
    chip_select: SpiPinNetRequirement
    shared_select_group: Identifier | None = None

    @model_validator(mode="after")
    def device_pin_ownership_and_uniqueness(self) -> SpiDeviceRequirement:
        signals: tuple[
            SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ...,
        ] = (
            self.sck,
            self.mosi,
            *((self.miso,) if not isinstance(self.miso, SpiPinNotPresent) else ()),
            self.chip_select,
        )
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in signals
        ):
            raise ValueError("SPI device pins must belong to the declared device")
        if len({item.pin.casefold() for item in signals}) != len(signals):
            raise ValueError("SPI device signal and chip-select pins must be unique")
        return self


class SpiBridgePathRequirement(StrictModel):
    signal: Literal["sck", "mosi", "miso"]
    from_pin: Reference
    from_net: NetName
    to_pin: Reference
    to_net: NetName

    @model_validator(mode="after")
    def distinct_path_ends(self) -> SpiBridgePathRequirement:
        if "." not in self.from_pin or "." not in self.to_pin:
            raise ValueError("SPI bridge pins must use COMPONENT.PIN form")
        if self.from_pin == self.to_pin or self.from_net == self.to_net:
            raise ValueError("SPI bridge paths need distinct pins and distinct nets")
        return self


class SpiBridgeRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    paths: Annotated[tuple[SpiBridgePathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def bridge_pins_belong_to_component(self) -> SpiBridgeRequirement:
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for path in self.paths
            for pin in (path.from_pin, path.to_pin)
        ):
            raise ValueError("SPI bridge pins must belong to the declared bridge component")
        assignments = [
            (pin.casefold(), net)
            for path in self.paths
            for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net))
        ]
        pin_nets: dict[str, str] = {}
        for pin, net in assignments:
            if pin in pin_nets and pin_nets[pin] != net:
                raise ValueError("An SPI bridge pin cannot map to multiple nets")
            pin_nets[pin] = net
        return self


class SpiBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    controller: SpiControllerRequirement
    devices: Annotated[tuple[SpiDeviceRequirement, ...], Field(min_length=1)]
    bridges: tuple[SpiBridgeRequirement, ...] = ()

    @model_validator(mode="after")
    def valid_bus_membership(self) -> SpiBusRequirement:
        device_ids = [item.id for item in self.devices]
        device_references = [item.reference.casefold() for item in self.devices]
        bridge_references = [item.reference.casefold() for item in self.bridges]
        if len(set(device_ids)) != len(device_ids):
            raise ValueError("SPI device IDs must be unique within a bus")
        if len(set(device_references)) != len(device_references):
            raise ValueError("An SPI device reference can appear only once per bus")
        if self.controller.reference.casefold() in {*device_references, *bridge_references}:
            raise ValueError("SPI controller, devices, and bridges must be distinct components")
        if len(set(bridge_references)) != len(bridge_references):
            raise ValueError("SPI bridge component references must be unique within a bus")
        if set(device_references) & set(bridge_references):
            raise ValueError("SPI devices and bridges must be distinct components")

        controller_nets = {self.controller.sck.net, self.controller.mosi.net}
        controller_miso = self.controller.miso
        if isinstance(controller_miso, SpiMisoConnectedRequirement):
            controller_nets.add(controller_miso.net)
        select_nets = {item.net for item in self.controller.chip_selects}
        if controller_nets & select_nets:
            raise ValueError("SPI chip-select nets must be separate from clock and data nets")

        device_selects: dict[str, list[SpiDeviceRequirement]] = {}
        for device in self.devices:
            device_selects.setdefault(device.chip_select.net, []).append(device)
            if device.chip_select.net not in select_nets:
                raise ValueError(
                    f"SPI device {device.id} chip-select net has no declared controller pin"
                )
            device_data_nets = {device.sck.net, device.mosi.net}
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                device_data_nets.add(device.miso.net)
            if device.chip_select.net in device_data_nets:
                raise ValueError(
                    f"SPI device {device.id} chip-select must be separate from data nets"
                )
            if device_data_nets & select_nets:
                raise ValueError(
                    f"SPI device {device.id} data nets overlap a controller chip-select net"
                )
            if device.sck.net != self.controller.sck.net and not self._has_route(
                "sck", self.controller.sck.net, device.sck.net
            ):
                raise ValueError(
                    f"SPI device {device.id} SCK has no declared path to the controller"
                )
            if device.mosi.net != self.controller.mosi.net and not self._has_route(
                "mosi", self.controller.mosi.net, device.mosi.net
            ):
                raise ValueError(
                    f"SPI device {device.id} MOSI has no declared path to the controller"
                )
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                if not isinstance(controller_miso, SpiMisoConnectedRequirement):
                    raise ValueError(  # noqa: TRY004 - malformed contract relationship
                        f"SPI device {device.id} has MISO but the controller MISO is not connected"
                    )
                if device.miso.net != controller_miso.net and not self._has_route(
                    "miso", controller_miso.net, device.miso.net
                ):
                    raise ValueError(
                        f"SPI device {device.id} MISO has no declared path to the controller"
                    )

        for net, devices in device_selects.items():
            if len(devices) == 1:
                if devices[0].shared_select_group is not None:
                    raise ValueError("An SPI shared-select group must name at least two devices")
                continue
            groups = {device.shared_select_group for device in devices}
            if len(groups) != 1 or None in groups:
                raise ValueError(
                    f"SPI chip-select net {net} is shared without one explicit shared-select group"
                )
        missing_membership = select_nets - set(device_selects)
        if missing_membership:
            raise ValueError(
                "Every declared SPI controller chip-select net must map to a device: "
                + ", ".join(sorted(missing_membership))
            )
        return self

    def _has_route(self, signal: str, source: str, destination: str) -> bool:
        graph: dict[str, set[str]] = {}
        for bridge in self.bridges:
            for path in bridge.paths:
                if path.signal == signal:
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
        pending = [source]
        reached: set[str] = set()
        while pending:
            net = pending.pop()
            if net == destination:
                return True
            if net in reached:
                continue
            reached.add(net)
            pending.extend(graph.get(net, ()))
        return False


class SpiAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[SpiBusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids(self) -> SpiAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("SPI bus IDs must be unique")
        return self


class SerialPinNetRequirement(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("Serial pin mappings must use COMPONENT.PIN form")
        return value


class SerialLogicOutputLimits(StrictModel):
    """Guaranteed logic-output ranges copied from a reviewed device source."""

    low_minimum_v: FiniteMeasure
    low_maximum_v: FiniteMeasure
    high_minimum_v: FiniteMeasure
    high_maximum_v: FiniteMeasure
    source: NonEmptyText
    conditions: NonEmptyText

    @model_validator(mode="after")
    def ordered_logic_output_ranges(self) -> SerialLogicOutputLimits:
        if not (
            self.low_minimum_v <= self.low_maximum_v < self.high_minimum_v <= self.high_maximum_v
        ):
            raise ValueError("Serial output voltage ranges must be ordered and non-overlapping")
        return self


class SerialLogicInputLimits(StrictModel):
    """Logic receiver thresholds and absolute input limits from a reviewed source."""

    absolute_minimum_v: FiniteMeasure
    low_maximum_v: FiniteMeasure
    high_minimum_v: FiniteMeasure
    absolute_maximum_v: FiniteMeasure
    source: NonEmptyText
    conditions: NonEmptyText

    @model_validator(mode="after")
    def ordered_logic_input_ranges(self) -> SerialLogicInputLimits:
        if not (
            self.absolute_minimum_v
            <= self.low_maximum_v
            < self.high_minimum_v
            <= self.absolute_maximum_v
        ):
            raise ValueError("Serial input absolute limits and logic thresholds must be ordered")
        return self


class SerialLogicLimits(StrictModel):
    """Reviewed electrical limits for UART TX and RX pins."""

    output: SerialLogicOutputLimits
    input: SerialLogicInputLimits


class DigitalLogicOutputLimits(SerialLogicOutputLimits):
    """Guaranteed output ranges for a mapped direct digital peer."""


class DigitalLogicInputLimits(SerialLogicInputLimits):
    """Receiver thresholds and absolute limits for a mapped digital peer."""


class SerialLabelFixtureExpectedNets(StrictModel):
    """Exact expected signal assignments for the synthetic serial-label lane."""

    rx: Annotated[tuple[Reference, ...], Field(alias="UART.0.RX", min_length=1)]
    tx: Annotated[tuple[Reference, ...], Field(alias="UART.0.TX", min_length=1)]

    @model_validator(mode="after")
    def pins_are_not_shared(self) -> SerialLabelFixtureExpectedNets:
        if set(self.rx) & set(self.tx):
            raise ValueError("UART RX and TX expected-net fixture pins must be distinct")
        return self


class DigitalPeerPinRequirement(StrictModel):
    """Exact, source-bound identity and net assignment for one peer pin."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    net: NetName

    @model_validator(mode="after")
    def pin_belongs_to_component(self) -> DigitalPeerPinRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Digital peer pin must be qualified by its declared component")
        return self


class DigitalPeerVoltageLink(StrictModel):
    """One reviewed, directly connected output-to-input relationship."""

    id: Identifier
    basis: NonEmptyText
    driver: DigitalPeerPinRequirement
    receiver: DigitalPeerPinRequirement
    output_limits: DigitalLogicOutputLimits | None = None
    input_limits: DigitalLogicInputLimits | None = None

    @model_validator(mode="after")
    def direct_peer_pin_map(self) -> DigitalPeerVoltageLink:
        if self.driver.reference.casefold() == self.receiver.reference.casefold():
            raise ValueError("Digital peer endpoints must be distinct components")
        if self.driver.pin.casefold() == self.receiver.pin.casefold():
            raise ValueError("Digital peer endpoints must use distinct pins")
        if self.driver.net != self.receiver.net:
            raise ValueError("Direct digital peer endpoints must declare the same net")
        return self


class DigitalPeerVoltageAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    links: Annotated[tuple[DigitalPeerVoltageLink, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_link_ids(self) -> DigitalPeerVoltageAnalysis:
        if len({link.id.casefold() for link in self.links}) != len(self.links):
            raise ValueError("Digital peer link IDs must be unique")
        return self


class ComponentVoltageRatingRequirement(StrictModel):
    """Reviewed voltage rating and operating-stress envelope for one exact part."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pins: Annotated[tuple[Reference, Reference], Field(min_length=2, max_length=2)]
    nets: Annotated[tuple[NetName, NetName], Field(min_length=2, max_length=2)]
    rated_working_voltage_v: ElectricalPositive
    maximum_expected_voltage_v: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_component_pin_pair(self) -> ComponentVoltageRatingRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Component voltage-rating pins must belong to the declared reference")
        if len({pin.casefold() for pin in self.pins}) != 2:
            raise ValueError("Component voltage-rating pins must be unique")
        return self


class ComponentVoltageRatingAnalysis(StrictModel):
    """Project-owned exact-part voltage-rating and stress comparisons."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ComponentVoltageRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_parts(self) -> ComponentVoltageRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Component voltage-rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each component may have one voltage-rating requirement")
        return self


class ComponentPowerRatingRequirement(StrictModel):
    """Reviewed power rating and dissipation envelope for one exact two-pin part."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pins: Annotated[tuple[Reference, Reference], Field(min_length=2, max_length=2)]
    nets: Annotated[tuple[NetName, NetName], Field(min_length=2, max_length=2)]
    rated_power_w: ElectricalPositive
    derated_allowable_power_w: ElectricalPositive
    maximum_expected_power_w: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    derating_basis: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_component_pin_pair(self) -> ComponentPowerRatingRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Component power-rating pins must belong to the declared reference")
        if len({pin.casefold() for pin in self.pins}) != 2:
            raise ValueError("Component power-rating pins must be unique")
        if self.derated_allowable_power_w > self.rated_power_w:
            raise ValueError("Derated allowable power cannot exceed the source-rated power")
        return self


class ComponentPowerRatingAnalysis(StrictModel):
    """Project-owned exact-part power-rating and dissipation comparisons."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ComponentPowerRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_parts(self) -> ComponentPowerRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Component power-rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each component may have one power-rating requirement")
        return self


class ConnectorContactCurrentRequirement(StrictModel):
    """One exact connector contact's sourced rating and authored current load."""

    id: Identifier
    pin_number: NonEmptyText
    expected_function: NonEmptyText
    expected_net: NetName
    rated_current_a: ElectricalPositive
    derated_allowable_current_a: ElectricalPositive
    maximum_expected_current_a: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    derating_basis: NonEmptyText
    load_basis: NonEmptyText

    @model_validator(mode="after")
    def allowable_contact_current_within_rating(self) -> ConnectorContactCurrentRequirement:
        if self.derated_allowable_current_a > self.rated_current_a:
            raise ValueError(
                "Derated allowable current cannot exceed the source-rated contact current"
            )
        return self


class ConnectorContactRatingRequirement(StrictModel):
    """Exact native connector identity and one or more authored contact limits."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    native_pin_numbers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    contacts: Annotated[tuple[ConnectorContactCurrentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_connector_pin_inventory(self) -> ConnectorContactRatingRequirement:
        if len({pin.casefold() for pin in self.native_pin_numbers}) != len(self.native_pin_numbers):
            raise ValueError("Connector contact rating pin inventory must be unique")
        if len({contact.id.casefold() for contact in self.contacts}) != len(self.contacts):
            raise ValueError("Connector contact rating IDs must be unique per connector")
        contact_pins = [contact.pin_number.casefold() for contact in self.contacts]
        if len(set(contact_pins)) != len(contact_pins):
            raise ValueError("A connector pin may have only one contact current requirement")
        inventory = {pin.casefold() for pin in self.native_pin_numbers}
        if any(pin not in inventory for pin in contact_pins):
            raise ValueError("Rated connector contacts must be in the exact native pin inventory")
        return self


class ConnectorContactRatingAnalysis(StrictModel):
    """Project-owned comparison of per-contact current to reviewed connector ratings."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ConnectorContactRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_connectors(self) -> ConnectorContactRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Connector contact rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each connector may have one contact rating requirement")
        return self


class MosfetVoltageInterval(StrictModel):
    """Authored lower and upper net-potential bounds for one operating state."""

    minimum_v: FiniteMeasure
    maximum_v: FiniteMeasure

    @model_validator(mode="after")
    def ordered_bounds(self) -> MosfetVoltageInterval:
        if self.minimum_v > self.maximum_v:
            raise ValueError("MOSFET state-potential minimum cannot exceed its maximum")
        return self


class MosfetOperatingState(StrictModel):
    """One reviewed state and the net potentials supplied for that state."""

    id: Identifier
    net_potentials: Mapping[NetName, MosfetVoltageInterval] = Field(default_factory=dict)


class MosfetStressRequirement(StrictModel):
    """Exact three-pin MOSFET identity and sourced VDS/VGS limits."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    drain_pin: Reference
    drain_function: NonEmptyText
    drain_net: NetName
    gate_pin: Reference
    gate_function: NonEmptyText
    gate_net: NetName
    source_pin: Reference
    source_function: NonEmptyText
    source_net: NetName
    rated_maximum_vds_v: ElectricalPositive
    rated_maximum_vgs_v: ElectricalPositive
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_three_pin_terminals(self) -> MosfetStressRequirement:
        terminals = (
            ("drain", self.drain_pin, self.drain_function, self.drain_net),
            ("gate", self.gate_pin, self.gate_function, self.gate_net),
            ("source", self.source_pin, self.source_function, self.source_net),
        )
        expected_functions = (
            ("drain", {"d", "drain"}),
            ("gate", {"g", "gate"}),
            ("source", {"s", "source"}),
        )
        for (terminal_role, pin, function, _), (role, accepted) in zip(
            terminals, expected_functions, strict=True
        ):
            if function.casefold() not in accepted:
                raise ValueError(
                    f"MOSFET {role} function must be D/DRAIN, G/GATE, or S/SOURCE as appropriate"
                )
            if pin.count(".") != 1:
                raise ValueError("MOSFET terminal pins must use an exact reference.pin number")
            if pin.rsplit(".", maxsplit=1)[0].casefold() != self.reference.casefold():
                raise ValueError(
                    f"MOSFET {terminal_role} pin must belong to the declared reference"
                )
        if len({terminal[1].casefold() for terminal in terminals}) != 3:
            raise ValueError("MOSFET terminal pins must be distinct")
        if len({terminal[3].casefold() for terminal in terminals}) != 3:
            raise ValueError("MOSFET drain, gate, and source nets must be distinct")
        return self


class MosfetStressAnalysis(StrictModel):
    """Project-authored, state-aware stress bounds for exact three-pin MOSFETs."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    required_states: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    states: tuple[MosfetOperatingState, ...] = ()
    requirements: Annotated[tuple[MosfetStressRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_states_and_parts(self) -> MosfetStressAnalysis:
        required = {state.casefold() for state in self.required_states}
        state_ids = {state.id.casefold() for state in self.states}
        requirement_ids = {item.id.casefold() for item in self.requirements}
        references = {item.reference.casefold() for item in self.requirements}
        if len(required) != len(self.required_states):
            raise ValueError("Required MOSFET operating-state IDs must be unique")
        if len(state_ids) != len(self.states):
            raise ValueError("MOSFET operating-state IDs must be unique")
        if not state_ids <= required:
            raise ValueError("MOSFET states may only define declared required states")
        if len(requirement_ids) != len(self.requirements):
            raise ValueError("MOSFET stress requirement IDs must be unique")
        if len(references) != len(self.requirements):
            raise ValueError("Each MOSFET reference may have one stress requirement")
        return self


class SerialEndpointRequirement(StrictModel):
    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    logic_domain: Identifier
    tx: SerialPinNetRequirement
    rx: SerialPinNetRequirement
    reference_pins: tuple[SerialPinNetRequirement, ...] = ()
    logic_limits: SerialLogicLimits | None = None

    @model_validator(mode="after")
    def endpoint_pin_ownership_and_roles(self) -> SerialEndpointRequirement:
        assignments = (self.tx, self.rx, *self.reference_pins)
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for item in assignments
        ):
            raise ValueError("Serial endpoint pins must belong to the declared component")
        pins = [item.pin.casefold() for item in assignments]
        if len(set(pins)) != len(pins):
            raise ValueError("Serial TX, RX, and reference pins must be distinct")
        if self.tx.net == self.rx.net:
            raise ValueError("Serial TX and RX must use distinct signal nets")
        return self


class SerialBridgePathRequirement(StrictModel):
    direction: Literal["a_tx_to_b_rx", "b_tx_to_a_rx"]
    from_pin: Reference
    from_net: NetName
    to_pin: Reference
    to_net: NetName

    @model_validator(mode="after")
    def distinct_path_ends(self) -> SerialBridgePathRequirement:
        if "." not in self.from_pin or "." not in self.to_pin:
            raise ValueError("Serial bridge pins must use COMPONENT.PIN form")
        if self.from_pin == self.to_pin or self.from_net == self.to_net:
            raise ValueError("Serial bridge paths need distinct pins and distinct nets")
        return self


class SerialBridgeRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    paths: Annotated[tuple[SerialBridgePathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def bridge_pin_ownership(self) -> SerialBridgeRequirement:
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for path in self.paths
            for pin in (path.from_pin, path.to_pin)
        ):
            raise ValueError("Serial bridge pins must belong to the declared bridge component")
        pins = [pin.casefold() for path in self.paths for pin in (path.from_pin, path.to_pin)]
        if len(set(pins)) != len(pins):
            raise ValueError("Each serial bridge pin must belong to exactly one declared path")
        assignments = [
            (pin.casefold(), net)
            for path in self.paths
            for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net))
        ]
        pin_nets: dict[str, str] = {}
        for pin, net in assignments:
            if pin in pin_nets and pin_nets[pin] != net:
                raise ValueError("A serial bridge pin cannot map to multiple nets")
            pin_nets[pin] = net
        return self


class SerialDirectPeerRequirement(StrictModel):
    mode: Literal["direct"]
    endpoint: SerialEndpointRequirement


class SerialShiftedPeerRequirement(StrictModel):
    mode: Literal["level_shifted"]
    endpoint: SerialEndpointRequirement
    bridges: Annotated[tuple[SerialBridgeRequirement, ...], Field(min_length=1)]


class SerialExternalPeerRequirement(StrictModel):
    mode: Literal["external"]
    reason: NonEmptyText


SerialPeerRequirement = Annotated[
    SerialDirectPeerRequirement | SerialShiftedPeerRequirement | SerialExternalPeerRequirement,
    Field(discriminator="mode"),
]


class SerialPeerLinkRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    endpoint: SerialEndpointRequirement
    peer: SerialPeerRequirement
    reference_policy: Literal[
        "common_net", "bonded", "separate_nets", "external_unverified", "not_applicable"
    ]
    reference_bond: ReferenceBondRequirement | None = None

    @model_validator(mode="after")
    def compatible_peer_map(self) -> SerialPeerLinkRequirement:
        peer = self.peer
        if isinstance(peer, SerialExternalPeerRequirement):
            if self.reference_policy not in {"external_unverified", "not_applicable"}:
                raise ValueError(
                    "An external serial peer needs external_unverified or not_applicable reference policy"
                )
            if self.reference_policy == "not_applicable" and self.endpoint.reference_pins:
                raise ValueError(
                    "not_applicable reference policy cannot declare endpoint reference pins"
                )
            if self.reference_bond is not None:
                raise ValueError("External serial peers cannot declare an on-board reference bond")
            return self

        remote = peer.endpoint
        if self.endpoint.reference.casefold() == remote.reference.casefold():
            raise ValueError("Serial peer endpoints must be distinct components")
        bridge_refs = (
            tuple(item.reference.casefold() for item in peer.bridges)
            if isinstance(peer, SerialShiftedPeerRequirement)
            else ()
        )
        if len(set(bridge_refs)) != len(bridge_refs):
            raise ValueError("Serial bridge component references must be unique")
        if {self.endpoint.reference.casefold(), remote.reference.casefold()} & set(bridge_refs):
            raise ValueError("Serial endpoint and bridge components must be distinct")
        if self.reference_bond is not None and self.reference_bond.reference.casefold() in {
            self.endpoint.reference.casefold(),
            remote.reference.casefold(),
            *bridge_refs,
        }:
            raise ValueError("Serial reference bond cannot reuse an endpoint or bridge component")

        if isinstance(peer, SerialDirectPeerRequirement):
            if self.endpoint.tx.net != remote.rx.net or self.endpoint.rx.net != remote.tx.net:
                raise ValueError("Direct serial peer maps must cross TX to RX in both directions")
            if self.endpoint.logic_domain != remote.logic_domain:
                raise ValueError(
                    "Direct serial peer endpoints must declare the same logic voltage domain"
                )
        else:
            if self.endpoint.logic_domain == remote.logic_domain:
                raise ValueError(
                    "Level-shifted serial peers must declare different logic voltage domains"
                )
            if not self._has_route(peer, "a_tx_to_b_rx", self.endpoint.tx.net, remote.rx.net):
                raise ValueError("Serial shifted peer map has no A TX to B RX path")
            if not self._has_route(peer, "b_tx_to_a_rx", remote.tx.net, self.endpoint.rx.net):
                raise ValueError("Serial shifted peer map has no B TX to A RX path")

        left_references = {item.net for item in self.endpoint.reference_pins}
        right_references = {item.net for item in remote.reference_pins}
        if self.reference_policy == "common_net":
            if not left_references or not right_references:
                raise ValueError("common_net serial reference policy needs pins on both endpoints")
            if len(left_references) != 1 or left_references != right_references:
                raise ValueError("common_net serial reference pins must share one declared net")
            if self.reference_bond is not None:
                raise ValueError("common_net serial reference policy cannot declare a bond")
        elif self.reference_policy == "separate_nets":
            if not left_references or not right_references:
                raise ValueError(
                    "separate_nets serial reference policy needs pins on both endpoints"
                )
            if len(left_references) != 1 or len(right_references) != 1:
                raise ValueError("Each serial endpoint must use one declared reference net")
            if left_references == right_references:
                raise ValueError("separate_nets serial reference policy needs distinct nets")
            if self.reference_bond is not None:
                raise ValueError("separate_nets serial reference policy cannot declare a bond")
        elif self.reference_policy == "bonded":
            if not left_references or not right_references:
                raise ValueError("bonded serial reference policy needs pins on both endpoints")
            if len(left_references) != 1 or len(right_references) != 1:
                raise ValueError("Each bonded serial endpoint must use one declared reference net")
            if left_references == right_references:
                raise ValueError("bonded serial reference policy needs distinct nets")
            if self.reference_bond is None:
                raise ValueError("bonded serial reference policy needs one exact bond component")
            if {
                self.reference_bond.side_a_net.casefold(),
                self.reference_bond.side_b_net.casefold(),
            } != {net.casefold() for net in left_references | right_references}:
                raise ValueError("Serial reference bond must join the two mapped endpoint nets")
        elif self.reference_bond is not None:
            raise ValueError("Serial reference bond requires the bonded reference policy")
        elif self.reference_policy == "not_applicable":
            if self.endpoint.reference_pins or remote.reference_pins:
                raise ValueError(
                    "not_applicable serial reference policy cannot declare reference pins"
                )
        elif self.reference_policy == "external_unverified":
            raise ValueError("external_unverified reference policy only applies to external peers")
        return self

    @staticmethod
    def _has_route(
        peer: SerialShiftedPeerRequirement,
        direction: Literal["a_tx_to_b_rx", "b_tx_to_a_rx"],
        source: str,
        destination: str,
    ) -> bool:
        if source == destination:
            return False
        graph: dict[str, set[str]] = {}
        for bridge in peer.bridges:
            for path in bridge.paths:
                if path.direction == direction:
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
        pending = [source]
        reached: set[str] = set()
        while pending:
            net = pending.pop()
            if net == destination:
                return True
            if net in reached:
                continue
            reached.add(net)
            pending.extend(graph.get(net, ()))
        return False


class SerialPeerAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    links: Annotated[tuple[SerialPeerLinkRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_link_ids(self) -> SerialPeerAnalysis:
        if len({link.id.casefold() for link in self.links}) != len(self.links):
            raise ValueError("Serial peer link IDs must be unique")
        return self


class Rs485EndpointPinRequirement(StrictModel):
    """One reviewed differential-line, control, or reference pin assignment."""

    role: Literal[
        "bus_line_1",
        "bus_line_2",
        "driver_input",
        "receiver_output",
        "driver_enable",
        "receiver_enable",
        "reference",
    ]
    pin: Reference
    net: NetName
    pair_id: Identifier | None = None

    @model_validator(mode="after")
    def line_roles_name_pair(self) -> Rs485EndpointPinRequirement:
        if "." not in self.pin:
            raise ValueError("RS-485 pin mappings must use COMPONENT.PIN form")
        if self.role in {"bus_line_1", "bus_line_2"} and self.pair_id is None:
            raise ValueError("RS-485 differential line pins must name a pair_id")
        if self.role not in {"bus_line_1", "bus_line_2"} and self.pair_id is not None:
            raise ValueError("Only RS-485 differential line pins can name a pair_id")
        return self


class Rs485EndpointRequirement(StrictModel):
    """Exact local symbol identity and pin roles for one bus participant."""

    id: Identifier
    kind: Literal["transceiver", "connector", "other"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[Rs485EndpointPinRequirement, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def endpoint_pin_roles(self) -> Rs485EndpointRequirement:
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in self.pins
        ):
            raise ValueError("RS-485 endpoint pins must belong to the declared component")
        pin_names = [item.pin.casefold() for item in self.pins]
        if len(set(pin_names)) != len(pin_names):
            raise ValueError("RS-485 endpoint pin assignments must be unique")
        role_keys = [
            (item.role, item.pair_id, item.pin.casefold() if item.role == "reference" else None)
            for item in self.pins
        ]
        if len(set(role_keys)) != len(role_keys):
            raise ValueError("RS-485 endpoint pin roles must be unique")
        pair_roles: dict[str, set[str]] = {}
        for item in self.pins:
            if item.pair_id is not None:
                pair_roles.setdefault(item.pair_id, set()).add(item.role)
        if any(roles != {"bus_line_1", "bus_line_2"} for roles in pair_roles.values()):
            raise ValueError("Each RS-485 endpoint pair needs one pin for each bus line")
        if self.kind == "transceiver":
            roles = {item.role for item in self.pins}
            if not {"driver_input", "receiver_output"} <= roles:
                raise ValueError(
                    "RS-485 transceivers need mapped driver_input and receiver_output pins"
                )
            if not pair_roles:
                raise ValueError("RS-485 transceivers need at least one mapped differential pair")
        return self


class Rs485TerminationResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    first_net: NetName
    second_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_path_and_range(self) -> Rs485TerminationResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("An RS-485 termination resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("RS-485 termination maximum resistance is below its minimum")
        return self


class Rs485DnpResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    first_net: NetName
    second_net: NetName

    @model_validator(mode="after")
    def distinct_option_nets(self) -> Rs485DnpResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("An RS-485 DNP resistor option must connect distinct nets")
        return self


class Rs485TerminationEndpointRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "split", "external", "not_required"]
    resistors: tuple[Rs485TerminationResistorRequirement, ...] = ()
    midpoint_net: NetName | None = None
    expected_dnp_resistors: tuple[Rs485DnpResistorRequirement, ...] = ()

    @model_validator(mode="after")
    def topology_has_matching_paths(self) -> Rs485TerminationEndpointRequirement:
        refs = [item.reference.casefold() for item in self.resistors]
        dnp_refs = [item.reference.casefold() for item in self.expected_dnp_resistors]
        if len(set(refs)) != len(refs) or len(set(dnp_refs)) != len(dnp_refs):
            raise ValueError("RS-485 termination resistor references must be unique")
        if set(refs) & set(dnp_refs):
            raise ValueError("An RS-485 resistor cannot be both fitted and DNP")
        if self.topology == "direct":
            if len(self.resistors) != 1 or self.midpoint_net is not None:
                raise ValueError("Direct RS-485 termination needs one resistor and no midpoint")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted direct termination cannot require DNP resistors")
        elif self.topology == "split":
            if len(self.resistors) != 2 or self.midpoint_net is None:
                raise ValueError("Split RS-485 termination needs two resistors and a midpoint")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted split termination cannot require DNP resistors")
        elif self.resistors or self.midpoint_net is not None:
            raise ValueError(
                "External or not-required termination cannot claim fitted resistor paths"
            )
        return self


class Rs485BiasResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    bus_net: NetName
    rail_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_bias_path(self) -> Rs485BiasResistorRequirement:
        if self.bus_net == self.rail_net:
            raise ValueError("An RS-485 bias resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("RS-485 bias maximum resistance is below its minimum")
        return self


class Rs485LocalBiasRequirement(StrictModel):
    mode: Literal["local"]
    basis: NonEmptyText
    pull_up: Rs485BiasResistorRequirement
    pull_down: Rs485BiasResistorRequirement

    @model_validator(mode="after")
    def distinct_bias_components(self) -> Rs485LocalBiasRequirement:
        if self.pull_up.reference.casefold() == self.pull_down.reference.casefold():
            raise ValueError("RS-485 pull-up and pull-down must be separate components")
        if self.pull_up.bus_net == self.pull_down.bus_net:
            raise ValueError("RS-485 bias resistors must apply to different bus lines")
        if self.pull_up.rail_net == self.pull_down.rail_net:
            raise ValueError("RS-485 pull-up rail and pull-down reference must be distinct")
        return self


class Rs485RemoteBiasRequirement(StrictModel):
    mode: Literal["remote"]
    basis: NonEmptyText
    reason: NonEmptyText


class Rs485InternalFailSafeRequirement(StrictModel):
    mode: Literal["internal_failsafe"]
    basis: NonEmptyText
    transceiver_references: Annotated[tuple[Identifier, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_transceivers(self) -> Rs485InternalFailSafeRequirement:
        if len({reference.casefold() for reference in self.transceiver_references}) != len(
            self.transceiver_references
        ):
            raise ValueError("RS-485 internal-failsafe transceivers must be unique")
        return self


class Rs485NoBiasRequirement(StrictModel):
    mode: Literal["not_required"]
    basis: NonEmptyText
    reason: NonEmptyText


Rs485BiasRequirement = Annotated[
    Rs485LocalBiasRequirement
    | Rs485RemoteBiasRequirement
    | Rs485InternalFailSafeRequirement
    | Rs485NoBiasRequirement,
    Field(discriminator="mode"),
]


class Rs485SignalPairRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    purpose: Literal["bidirectional", "board_to_peer", "peer_to_board"]
    line_1_net: NetName
    line_2_net: NetName
    terminations: Annotated[tuple[Rs485TerminationEndpointRequirement, ...], Field(min_length=1)]
    bias: Rs485BiasRequirement

    @model_validator(mode="after")
    def distinct_pair_nets_and_topology_ids(self) -> Rs485SignalPairRequirement:
        if self.line_1_net == self.line_2_net:
            raise ValueError("RS-485 differential pair line nets must be distinct")
        if len({item.id.casefold() for item in self.terminations}) != len(self.terminations):
            raise ValueError("RS-485 termination endpoint IDs must be unique within a pair")
        return self


class Rs485BusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["two_wire_half_duplex", "four_wire_full_duplex"]
    pairs: Annotated[tuple[Rs485SignalPairRequirement, ...], Field(min_length=1)]
    endpoints: Annotated[tuple[Rs485EndpointRequirement, ...], Field(min_length=1)]
    external_peers: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def topology_and_endpoint_maps(self) -> Rs485BusRequirement:
        if self.topology == "two_wire_half_duplex":
            if len(self.pairs) != 1 or self.pairs[0].purpose != "bidirectional":
                raise ValueError("Two-wire RS-485 needs one bidirectional differential pair")
        elif len(self.pairs) != 2 or {item.purpose for item in self.pairs} != {
            "board_to_peer",
            "peer_to_board",
        }:
            raise ValueError("Four-wire RS-485 needs board-to-peer and peer-to-board pairs")
        pair_by_id = {item.id: item for item in self.pairs}
        if len(pair_by_id) != len(self.pairs):
            raise ValueError("RS-485 pair IDs must be unique within a bus")
        nets = [net for pair in self.pairs for net in (pair.line_1_net, pair.line_2_net)]
        if len(set(nets)) != len(nets):
            raise ValueError("RS-485 bus pair nets must be distinct")
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("RS-485 endpoint IDs must be unique within a bus")
        pin_assignments: list[str] = []
        transceiver_references = {
            item.reference.casefold() for item in self.endpoints if item.kind == "transceiver"
        }
        covered_pairs: set[str] = set()
        for endpoint in self.endpoints:
            for pin in endpoint.pins:
                pin_assignments.append(pin.pin.casefold())
                if pin.pair_id is None:
                    continue
                pair = pair_by_id.get(pin.pair_id)
                if pair is None:
                    raise ValueError(f"RS-485 endpoint references unknown pair {pin.pair_id}")
                expected_net = pair.line_1_net if pin.role == "bus_line_1" else pair.line_2_net
                if pin.net != expected_net:
                    raise ValueError("RS-485 endpoint line pins must use their declared pair nets")
                if endpoint.kind == "transceiver":
                    covered_pairs.add(pair.id)
        if len(set(pin_assignments)) != len(pin_assignments):
            raise ValueError("An RS-485 endpoint pin cannot be assigned more than once")
        if covered_pairs != set(pair_by_id):
            raise ValueError("Every RS-485 signal pair needs mapped local transceiver pins")
        termination_refs: list[str] = []
        bias_refs: list[str] = []
        for pair in self.pairs:
            line_nets = {pair.line_1_net, pair.line_2_net}
            for endpoint in pair.terminations:
                termination_refs.extend(
                    item.reference.casefold()
                    for item in (*endpoint.resistors, *endpoint.expected_dnp_resistors)
                )
                paths = tuple(
                    frozenset((item.first_net, item.second_net)) for item in endpoint.resistors
                )
                if endpoint.topology == "direct" and paths != (frozenset(line_nets),):
                    raise ValueError("Direct RS-485 termination must bridge the declared pair")
                if endpoint.topology == "split":
                    midpoint = endpoint.midpoint_net
                    assert midpoint is not None
                    if midpoint in line_nets:
                        raise ValueError("RS-485 termination midpoint must differ from pair nets")
                    if set(paths) != {
                        frozenset((pair.line_1_net, midpoint)),
                        frozenset((pair.line_2_net, midpoint)),
                    }:
                        raise ValueError(
                            "Split RS-485 termination must connect each pair line to one midpoint"
                        )
                for option in endpoint.expected_dnp_resistors:
                    if {option.first_net, option.second_net} != line_nets:
                        raise ValueError("Expected DNP termination options must bridge the pair")
            if isinstance(pair.bias, Rs485LocalBiasRequirement):
                up, down = pair.bias.pull_up, pair.bias.pull_down
                if {up.bus_net, down.bus_net} != line_nets:
                    raise ValueError(
                        "Local RS-485 bias must declare one resistor on each pair line"
                    )
                if up.rail_net in line_nets or down.rail_net in line_nets:
                    raise ValueError("RS-485 bias supply/reference nets must differ from pair nets")
                bias_refs.extend((up.reference.casefold(), down.reference.casefold()))
            elif isinstance(pair.bias, Rs485InternalFailSafeRequirement):
                if {item.casefold() for item in pair.bias.transceiver_references} != (
                    transceiver_references
                ):
                    raise ValueError(
                        "Internal-failsafe declaration must name every local RS-485 transceiver"
                    )
        all_resistor_refs = [*termination_refs, *bias_refs]
        if len(set(all_resistor_refs)) != len(all_resistor_refs):
            raise ValueError("An RS-485 resistor cannot be reused across termination or bias roles")
        endpoint_refs = {item.reference.casefold() for item in self.endpoints}
        if endpoint_refs & set(all_resistor_refs):
            raise ValueError("RS-485 endpoint and resistor components must be distinct")
        return self


class Rs485Analysis(StrictModel):
    """Project-authored termination, bias, and endpoint maps for RS-485."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[Rs485BusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids_and_resistors(self) -> Rs485Analysis:
        if len({bus.id.casefold() for bus in self.buses}) != len(self.buses):
            raise ValueError("RS-485 bus IDs must be unique")
        pair_nets = [
            net
            for bus in self.buses
            for pair in bus.pairs
            for net in (pair.line_1_net, pair.line_2_net)
        ]
        if len(set(pair_nets)) != len(pair_nets):
            raise ValueError("RS-485 pair nets cannot be reused across buses")
        resistor_references = [
            item.reference.casefold()
            for bus in self.buses
            for pair in bus.pairs
            for termination in pair.terminations
            for item in (*termination.resistors, *termination.expected_dnp_resistors)
        ]
        resistor_references.extend(
            resistor.reference.casefold()
            for bus in self.buses
            for pair in bus.pairs
            if isinstance(pair.bias, Rs485LocalBiasRequirement)
            for resistor in (pair.bias.pull_up, pair.bias.pull_down)
        )
        if len(set(resistor_references)) != len(resistor_references):
            raise ValueError("RS-485 resistor references cannot be reused across buses")
        return self


ControlElectricalType = Literal[
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "passive",
    "free",
    "unspecified",
    "power_in",
    "power_out",
    "open_collector",
    "open_emitter",
    "no_connect",
]


class ControlPinRequirement(StrictModel):
    """One exact control-signal endpoint and its KiCad library pin type."""

    role: Literal["controlled_input", "approved_driver", "external_interface"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    electrical_type: ControlElectricalType

    @model_validator(mode="after")
    def pin_belongs_to_reference(self) -> ControlPinRequirement:
        if self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
            raise ValueError("Control-signal pin must belong to its declared component")
        if self.role == "controlled_input" and self.electrical_type not in {
            "input",
            "bidirectional",
            "tri_state",
            "passive",
            "unspecified",
            "power_in",
        }:
            raise ValueError("A controlled input cannot use a power/output-only pin type")
        if self.role == "approved_driver" and self.electrical_type not in {
            "output",
            "bidirectional",
            "tri_state",
            "power_out",
            "open_collector",
            "open_emitter",
        }:
            raise ValueError("An approved control driver needs an output-capable pin type")
        return self


class ControlBiasResistorRequirement(StrictModel):
    """One exact fitted resistor path used to bias a declared control signal."""

    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    signal_net: NetName
    bias_net: NetName
    direction: Literal["pull_up", "pull_down"]
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_bias_path(self) -> ControlBiasResistorRequirement:
        if self.signal_net == self.bias_net:
            raise ValueError("A control-bias resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("Control-bias maximum resistance is below its minimum")
        return self


class ControlLocalBiasRequirement(StrictModel):
    mode: Literal["local"]
    basis: NonEmptyText
    resistors: Annotated[tuple[ControlBiasResistorRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_resistors(self) -> ControlLocalBiasRequirement:
        if len({item.reference.casefold() for item in self.resistors}) != len(self.resistors):
            raise ValueError("Control-bias resistor references must be unique")
        return self


class ControlInternalBiasRequirement(StrictModel):
    mode: Literal["internal"]
    basis: NonEmptyText
    reason: NonEmptyText


class ControlExternalBiasRequirement(StrictModel):
    mode: Literal["external"]
    basis: NonEmptyText
    reason: NonEmptyText


class ControlNoBiasRequirement(StrictModel):
    mode: Literal["not_required"]
    basis: NonEmptyText
    reason: NonEmptyText


ControlBiasRequirement = Annotated[
    ControlLocalBiasRequirement
    | ControlInternalBiasRequirement
    | ControlExternalBiasRequirement
    | ControlNoBiasRequirement,
    Field(discriminator="mode"),
]


class ControlSignalRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    signal_net: NetName
    driver_policy: Literal["none", "single", "shared_open_drain", "reviewed_multiple"]
    driver_basis: NonEmptyText | None = None
    endpoints: Annotated[tuple[ControlPinRequirement, ...], Field(min_length=1)]
    bias: ControlBiasRequirement

    @model_validator(mode="after")
    def valid_endpoints_and_policy(self) -> ControlSignalRequirement:
        pins = [item.pin.casefold() for item in self.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Control-signal endpoint pins must be unique")
        if not any(item.role == "controlled_input" for item in self.endpoints):
            raise ValueError("A control signal needs at least one controlled input endpoint")
        drivers = [item for item in self.endpoints if item.role == "approved_driver"]
        if self.driver_policy == "none" and drivers:
            raise ValueError("A no-driver control signal cannot list approved drivers")
        if self.driver_policy == "single" and len(drivers) != 1:
            raise ValueError("A single-driver control signal needs exactly one approved driver")
        if self.driver_policy == "shared_open_drain":
            if len(drivers) < 2:
                raise ValueError("Shared open-drain control needs at least two approved drivers")
            if any(
                item.electrical_type not in {"open_collector", "open_emitter"} for item in drivers
            ):
                raise ValueError("Shared open-drain drivers need open-collector/emitter pin types")
        if self.driver_policy == "reviewed_multiple" and len(drivers) < 2:
            raise ValueError("Reviewed multiple-driver control needs at least two approved drivers")
        if self.driver_policy in {"shared_open_drain", "reviewed_multiple"}:
            if self.driver_basis is None:
                raise ValueError("A shared or multiple-driver control needs a review basis")
        elif self.driver_basis is not None:
            raise ValueError("A driver basis is only valid for shared or reviewed multiple drivers")
        if isinstance(self.bias, ControlLocalBiasRequirement) and any(
            item.signal_net != self.signal_net for item in self.bias.resistors
        ):
            raise ValueError("Local control-bias resistor signal nets must match the control net")
        return self


class ControlInputsAnalysis(StrictModel):
    """Project-authored reset, enable, and boot-strap connectivity requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    signals: Annotated[tuple[ControlSignalRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_signals_and_resistors(self) -> ControlInputsAnalysis:
        if len({item.id.casefold() for item in self.signals}) != len(self.signals):
            raise ValueError("Control-signal IDs must be unique")
        if len({item.signal_net for item in self.signals}) != len(self.signals):
            raise ValueError("Each control-signal net must have one requirement group")
        pins = [endpoint.pin.casefold() for signal in self.signals for endpoint in signal.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Control-signal endpoint pins cannot be reused")
        resistor_refs = [
            resistor.reference.casefold()
            for signal in self.signals
            if isinstance(signal.bias, ControlLocalBiasRequirement)
            for resistor in signal.bias.resistors
        ]
        if len(set(resistor_refs)) != len(resistor_refs):
            raise ValueError("Control-bias resistor references cannot be reused")
        return self


class TestAccessProbeEnvelope(StrictModel):
    """Project-approved circular probe tip and edge-clearance envelope."""

    tip_diameter_mm: ElectricalPositive
    clearance_mm: NonNegativeMeasure


class PcbAccessProbeRequest(StrictModel):
    """One exact test-access pad surface requested from the native PCB probe."""

    endpoint: Reference
    net: NetName
    side: Literal["front", "back"]


class PcbAccessProbeRequestSet(StrictModel):
    """Canonical set of native geometry requests retained with a PCB receipt."""

    schema_version: Literal["1"] = "1"
    requests: Annotated[tuple[PcbAccessProbeRequest, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_endpoint_surfaces(self) -> PcbAccessProbeRequestSet:
        keys = [(item.endpoint.casefold(), item.side.casefold()) for item in self.requests]
        if len(set(keys)) != len(keys):
            raise ValueError("Native probe requests must have unique endpoint surfaces")
        return self


class TestAccessEndpointRequirement(StrictModel):
    """Exact schematic pin and PCB approach surface for an approved access point."""

    kind: Literal["test_point", "programming_connector", "factory_connector"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    electrical_type: NonEmptyText
    approach_side: Literal["front", "back", "either"] = Field(
        default="either",
        description="Required outer PCB surface with copper and solder-mask access.",
    )
    probe_envelope: TestAccessProbeEnvelope | None = None

    @model_validator(mode="after")
    def pin_belongs_to_component(self) -> TestAccessEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Test-access pin must belong to its named component")
        return self


class RequiredTestAccess(StrictModel):
    """One exact required net and its approved schematic access endpoint(s)."""

    mode: Literal["required"]
    id: Identifier
    basis: NonEmptyText
    net: NetName
    selection: Literal["all", "any"] = "all"
    endpoints: Annotated[tuple[TestAccessEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_endpoint_pins(self) -> RequiredTestAccess:
        pins = [item.pin.casefold() for item in self.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Test-access endpoint pins must be unique")
        return self


class ExcludedTestAccess(StrictModel):
    """Explicitly reviewed net for which this board does not require test access."""

    mode: Literal["not_required"]
    id: Identifier
    basis: NonEmptyText
    net: NetName
    reason: NonEmptyText


TestAccessDecision = Annotated[
    RequiredTestAccess | ExcludedTestAccess,
    Field(discriminator="mode"),
]


class PcbAccessAnalysis(StrictModel):
    """Require exact approved schematic endpoints to map to PCB pad layers."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText


class TestAccessAnalysis(StrictModel):
    """Project-authored schematic test-point and programming-access requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    decisions: Annotated[tuple[TestAccessDecision, ...], Field(min_length=1)]
    pcb_accessibility: Annotated[
        PcbAccessAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]

    @model_validator(mode="after")
    def unique_ids_and_scoped_nets(self) -> TestAccessAnalysis:
        if len({item.id.casefold() for item in self.decisions}) != len(self.decisions):
            raise ValueError("Test-access decision IDs must be unique")
        if len({item.net.casefold() for item in self.decisions}) != len(self.decisions):
            raise ValueError("Each test-access net needs one explicit decision")
        if any(
            endpoint.probe_envelope is not None
            for decision in self.decisions
            if isinstance(decision, RequiredTestAccess)
            for endpoint in decision.endpoints
        ) and not isinstance(self.pcb_accessibility, PcbAccessAnalysis):
            raise ValueError("Probe envelopes require the PCB accessibility stage")
        return self


class CanTerminationResistorRequirement(StrictModel):
    """One project-authored resistor path in a local CAN termination network."""

    reference: ResistorReference
    first_net: NetName
    second_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_resistor_path(self) -> CanTerminationResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("A CAN termination resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("CAN termination maximum resistance is below its minimum")
        return self


class CanTerminationMidpointCapacitorRequirement(StrictModel):
    """Reviewed identity, pins, and nominal value for a split-termination capacitor."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    midpoint_pin: Reference
    reference_pin: Reference
    reference_net: NetName
    minimum_nominal_capacitance_pf: CapacitancePf
    maximum_nominal_capacitance_pf: CapacitancePf

    @model_validator(mode="after")
    def exact_component_pins_and_range(self) -> CanTerminationMidpointCapacitorRequirement:
        prefix = f"{self.reference}.".casefold()
        if not self.midpoint_pin.casefold().startswith(
            prefix
        ) or not self.reference_pin.casefold().startswith(prefix):
            raise ValueError("CAN midpoint-capacitor pins must belong to the declared component")
        if self.midpoint_pin.casefold() == self.reference_pin.casefold():
            raise ValueError("CAN midpoint-capacitor pins must differ")
        if self.maximum_nominal_capacitance_pf < self.minimum_nominal_capacitance_pf:
            raise ValueError("CAN midpoint-capacitor nominal capacitance range is reversed")
        return self


class CanTerminationEndpointRequirement(StrictModel):
    """Reviewed termination topology at one logical bus endpoint."""

    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "split", "external"]
    resistors: tuple[CanTerminationResistorRequirement, ...] = ()
    midpoint_net: NetName | None = None
    midpoint_capacitor: CanTerminationMidpointCapacitorRequirement | None = None
    expected_dnp_resistors: tuple[ResistorReference, ...] = ()

    @model_validator(mode="after")
    def topology_has_matching_parts(self) -> CanTerminationEndpointRequirement:
        references = [item.reference.casefold() for item in self.resistors]
        if self.midpoint_capacitor is not None:
            references.append(self.midpoint_capacitor.reference.casefold())
        dnp_references = [item.casefold() for item in self.expected_dnp_resistors]
        if len(set(references)) != len(references) or len(set(dnp_references)) != len(
            dnp_references
        ):
            raise ValueError("CAN termination component references must be unique")
        if set(references) & set(dnp_references):
            raise ValueError("A CAN termination resistor cannot be both fitted and DNP")
        if self.topology == "direct":
            if len(self.resistors) != 1 or self.midpoint_net is not None:
                raise ValueError("Direct CAN termination needs one resistor and no midpoint net")
            if self.midpoint_capacitor is not None:
                raise ValueError("Only split CAN termination can declare a midpoint capacitor")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted direct termination cannot require DNP resistors")
        elif self.topology == "split":
            if len(self.resistors) != 2 or self.midpoint_net is None:
                raise ValueError("Split CAN termination needs two resistors and a midpoint net")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted split termination cannot require DNP resistors")
            if (
                self.midpoint_capacitor is not None
                and self.midpoint_capacitor.reference_net == self.midpoint_net
            ):
                raise ValueError("CAN midpoint capacitor must connect distinct nets")
        elif self.resistors or self.midpoint_net is not None:
            raise ValueError("External CAN termination cannot claim local fitted resistor paths")
        elif self.midpoint_capacitor is not None:
            raise ValueError("Only split CAN termination can declare a midpoint capacitor")
        return self


class CanTerminationBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    high_net: NetName
    low_net: NetName
    high_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    low_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    endpoints: Annotated[tuple[CanTerminationEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def endpoints_match_bus_nets(self) -> CanTerminationBusRequirement:
        if self.high_net == self.low_net:
            raise ValueError("CAN high and low nets must be distinct")
        pins = (*self.high_pins, *self.low_pins)
        if len(set(pins)) != len(pins):
            raise ValueError("CAN high/low pin assignments must be unique")
        if len({item.id for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("CAN termination endpoint IDs must be unique within a bus")
        refs = [
            reference.casefold()
            for endpoint in self.endpoints
            for reference in (
                *(item.reference for item in endpoint.resistors),
                *(
                    (endpoint.midpoint_capacitor.reference,)
                    if endpoint.midpoint_capacitor is not None
                    else ()
                ),
                *endpoint.expected_dnp_resistors,
            )
        ]
        if len(set(refs)) != len(refs):
            raise ValueError("CAN termination component references cannot be reused")
        for endpoint in self.endpoints:
            paths = tuple(
                frozenset((item.first_net, item.second_net)) for item in endpoint.resistors
            )
            if endpoint.topology == "direct" and paths != (
                frozenset((self.high_net, self.low_net)),
            ):
                raise ValueError(
                    "Direct CAN termination must connect the declared high and low nets"
                )
            if endpoint.topology == "split":
                midpoint = endpoint.midpoint_net
                assert midpoint is not None
                if midpoint in {self.high_net, self.low_net}:
                    raise ValueError("Split CAN termination midpoint must differ from bus nets")
                expected = {
                    frozenset((self.high_net, midpoint)),
                    frozenset((self.low_net, midpoint)),
                }
                if set(paths) != expected:
                    raise ValueError(
                        "Split CAN termination resistors must connect each bus net to one midpoint"
                    )
        return self


class CanTerminationAnalysis(StrictModel):
    """Project-authored local CAN termination topology requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[CanTerminationBusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids_and_nets(self) -> CanTerminationAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("CAN termination bus IDs must be unique")
        signal_nets = [net for bus in self.buses for net in (bus.high_net, bus.low_net)]
        if len(set(signal_nets)) != len(signal_nets):
            raise ValueError("CAN termination signal nets must be unique across configured buses")
        component_references = [
            reference.casefold()
            for bus in self.buses
            for endpoint in bus.endpoints
            for reference in (
                *(item.reference for item in endpoint.resistors),
                *(
                    (endpoint.midpoint_capacitor.reference,)
                    if endpoint.midpoint_capacitor is not None
                    else ()
                ),
                *endpoint.expected_dnp_resistors,
            )
        ]
        if len(set(component_references)) != len(component_references):
            raise ValueError("CAN termination component references cannot be reused across buses")
        return self


class UsbCcResistorAttachment(StrictModel):
    """A project-authored Rp or Rd resistor on one connector CC line."""

    kind: Literal["resistor"]
    behavior: Literal["rp", "rd"]
    reference: ResistorReference
    rail_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_range(self) -> UsbCcResistorAttachment:
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("USB-C CC maximum resistance is below its minimum")
        return self


class UsbCcControllerAttachment(StrictModel):
    """An exact CC pin on an external USB-C controller."""

    kind: Literal["controller"]
    controller_pin: Reference

    @field_validator("controller_pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C controller pins must use COMPONENT.PIN form")
        return value


UsbCcAttachment = Annotated[
    UsbCcResistorAttachment | UsbCcControllerAttachment,
    Field(discriminator="kind"),
]


class UsbCcLineRequirement(StrictModel):
    connector_pin: Reference
    net: NetName
    attachment: UsbCcAttachment

    @field_validator("connector_pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C connector pins must use COMPONENT.PIN form")
        return value


class UsbCControllerRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText


class UsbCNetPinAssignment(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C pin mappings must use COMPONENT.PIN form")
        return value


class UsbCVbusPathElement(StrictModel):
    """One project-mapped component boundary in a USB-C VBUS path."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    port_side_net: NetName
    system_side_net: NetName
    port_side_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    system_side_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    pin_assignments: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def valid_pin_mapping(self) -> UsbCVbusPathElement:
        port_pins = {pin.casefold() for pin in self.port_side_pins}
        system_pins = {pin.casefold() for pin in self.system_side_pins}
        if len(port_pins) != len(self.port_side_pins):
            raise ValueError("USB-C VBUS path port-side pins must be unique")
        if len(system_pins) != len(self.system_side_pins):
            raise ValueError("USB-C VBUS path system-side pins must be unique")
        if port_pins & system_pins:
            raise ValueError("USB-C VBUS path component sides must use distinct pins")
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for pin in (*self.port_side_pins, *self.system_side_pins)
        ):
            raise ValueError("USB-C VBUS path pins must belong to the named component")
        mapped: dict[str, str] = {}
        for assignment in self.pin_assignments:
            if assignment.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("USB-C VBUS path pin mappings must belong to the named component")
            key = assignment.pin.casefold()
            if key in mapped:
                raise ValueError("USB-C VBUS path pin mappings must be unique")
            mapped[key] = assignment.net
        for pin in self.port_side_pins:
            if mapped.get(pin.casefold()) != self.port_side_net:
                raise ValueError("USB-C VBUS path port-side pins must map to the port-side net")
        for pin in self.system_side_pins:
            if mapped.get(pin.casefold()) != self.system_side_net:
                raise ValueError("USB-C VBUS path system-side pins must map to the system-side net")
        if self.port_side_net == self.system_side_net:
            raise ValueError("USB-C VBUS path element must span distinct nets")
        return self


class UsbCVbusPathRequirement(StrictModel):
    """An exact, ordered schematic map from a USB-C connector to a board pin."""

    id: Identifier
    basis: NonEmptyText
    connector_pin: Reference
    connector_net: NetName
    board_pin: Reference
    board_net: NetName
    elements: Annotated[tuple[UsbCVbusPathElement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def continuous_path(self) -> UsbCVbusPathRequirement:
        if self.connector_pin.casefold() == self.board_pin.casefold():
            raise ValueError("USB-C VBUS path endpoint pins must be distinct")
        if self.connector_net == self.board_net:
            raise ValueError("USB-C VBUS path endpoint nets must be distinct")
        references = [item.reference.casefold() for item in self.elements]
        if len(set(references)) != len(references):
            raise ValueError("USB-C VBUS path component references must be unique")
        nets = [self.connector_net]
        expected_net = self.connector_net
        for element in self.elements:
            if element.port_side_net != expected_net:
                raise ValueError("USB-C VBUS path elements must form one ordered net chain")
            expected_net = element.system_side_net
            nets.append(expected_net)
        if expected_net != self.board_net:
            raise ValueError("USB-C VBUS path must end on the declared board-side net")
        if len(set(nets)) != len(nets):
            raise ValueError("USB-C VBUS path nets must not repeat")
        return self


class UsbCProtectionComponentRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def pins_belong_to_component(self) -> UsbCProtectionComponentRequirement:
        if len({item.pin for item in self.pins}) != len(self.pins):
            raise ValueError("USB-C protection pin mappings must be unique")
        if any(item.pin.rsplit(".", 1)[0] != self.reference for item in self.pins):
            raise ValueError("USB-C protection pin mappings must belong to the named component")
        return self


class UsbCProtectionAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    components: Annotated[tuple[UsbCProtectionComponentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_components(self) -> UsbCProtectionAnalysis:
        refs = [item.reference.casefold() for item in self.components]
        if len(set(refs)) != len(refs):
            raise ValueError("USB-C protection component references must be unique")
        return self


class UsbCVbusCapacitorRequirement(StrictModel):
    """One exact fitted capacitor mapped across the port-side VBUS and return nets."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[UsbCNetPinAssignment, UsbCNetPinAssignment], Field(min_length=2)]

    @model_validator(mode="after")
    def valid_pin_map(self) -> UsbCVbusCapacitorRequirement:
        if len({item.pin.casefold() for item in self.pins}) != 2:
            raise ValueError("USB-C VBUS capacitor must map two unique pins")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for item in self.pins
        ):
            raise ValueError("USB-C VBUS capacitor pins must belong to the named component")
        if self.pins[0].net.casefold() == self.pins[1].net.casefold():
            raise ValueError("USB-C VBUS capacitor pins must connect to distinct nets")
        return self


class UsbCVbusCapacitanceRequirement(StrictModel):
    """Project-sourced nominal total capacitance limits for one USB-C port."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    minimum_nf: NonNegativeMeasure
    maximum_nf: ElectricalPositive
    capacitors: Annotated[tuple[UsbCVbusCapacitorRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def valid_range_and_unique_components(self) -> UsbCVbusCapacitanceRequirement:
        if self.maximum_nf < self.minimum_nf:
            raise ValueError("USB-C VBUS capacitance maximum is below its minimum")
        references = [item.reference.casefold() for item in self.capacitors]
        if len(set(references)) != len(references):
            raise ValueError("USB-C VBUS capacitor references must be unique")
        return self


class UsbCPortRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    connector: Identifier
    role: Literal["source", "sink", "dual_role", "debug_accessory"]
    cc1: UsbCcLineRequirement
    cc2: UsbCcLineRequirement
    vbus_net: NetName
    vbus_pins: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=2)]
    ground_net: NetName
    ground_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    vbus_capacitance: Annotated[
        UsbCVbusCapacitanceRequirement | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]
    source_rail: NetName | None = None
    controller: UsbCControllerRequirement | None = None
    vbus_path: UsbCVbusPathRequirement | None = None
    protection: Annotated[
        UsbCProtectionAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]

    @model_validator(mode="after")
    def valid_port_topology(self) -> UsbCPortRequirement:
        nets = (self.cc1.net, self.cc2.net, self.vbus_net, self.ground_net)
        if len(set(nets)) != len(nets):
            raise ValueError("USB-C CC1, CC2, VBUS, and ground nets must be distinct")
        connector_prefix = f"{self.connector}."
        connector_pins = (self.cc1.connector_pin, self.cc2.connector_pin)
        if any(not pin.startswith(connector_prefix) for pin in connector_pins):
            raise ValueError("USB-C CC pins must belong to the declared connector")
        if not any(
            assignment.pin.startswith(connector_prefix) and assignment.net == self.vbus_net
            for assignment in self.vbus_pins
        ):
            raise ValueError("USB-C VBUS pins must include a pin on the declared connector")
        if all(assignment.pin.startswith(connector_prefix) for assignment in self.vbus_pins):
            raise ValueError("USB-C VBUS pins must include a board-side pin")
        if any(
            assignment.pin.startswith(connector_prefix) and assignment.net != self.vbus_net
            for assignment in self.vbus_pins
        ):
            raise ValueError("USB-C connector VBUS pins must use the declared VBUS net")
        if len({assignment.pin for assignment in self.vbus_pins}) != len(self.vbus_pins):
            raise ValueError("USB-C VBUS pin declarations must be unique")
        if self.vbus_path is not None:
            path = self.vbus_path
            mapped_vbus = {(item.pin, item.net) for item in self.vbus_pins}
            if not path.connector_pin.startswith(connector_prefix):
                raise ValueError("USB-C VBUS path connector endpoint must belong to the port")
            if path.connector_net != self.vbus_net:
                raise ValueError("USB-C VBUS path connector endpoint must use the port VBUS net")
            if path.board_pin.startswith(connector_prefix):
                raise ValueError("USB-C VBUS path board endpoint must be a board-side pin")
            if (path.connector_pin, path.connector_net) not in mapped_vbus or (
                path.board_pin,
                path.board_net,
            ) not in mapped_vbus:
                raise ValueError(
                    "USB-C VBUS path endpoints must match declared VBUS pin assignments"
                )
        if not any(pin.startswith(connector_prefix) for pin in self.ground_pins):
            raise ValueError("USB-C ground pins must include a pin on the declared connector")
        if all(pin.startswith(connector_prefix) for pin in self.ground_pins):
            raise ValueError("USB-C ground pins must include a board-side return pin")
        all_pins = (
            *connector_pins,
            *(assignment.pin for assignment in self.vbus_pins),
            *self.ground_pins,
        )
        if len(set(all_pins)) != len(all_pins):
            raise ValueError("USB-C CC, VBUS, and ground pin declarations must be unique")
        if self.source_rail in {self.cc1.net, self.cc2.net, self.ground_net}:
            raise ValueError("USB-C source rail must be distinct from CC and ground nets")
        if self.role != "source" and self.source_rail is not None:
            raise ValueError("Only USB-C source ports may declare a source rail")

        attachments = (self.cc1.attachment, self.cc2.attachment)
        resistor_attachments = tuple(
            item for item in attachments if isinstance(item, UsbCcResistorAttachment)
        )
        controller_attachments = tuple(
            item for item in attachments if isinstance(item, UsbCcControllerAttachment)
        )
        if len({item.reference.casefold() for item in resistor_attachments}) != len(
            resistor_attachments
        ):
            raise ValueError("USB-C CC resistor references must be unique across both lines")
        if self.role == "source":
            if any(item.behavior != "rp" for item in resistor_attachments):
                raise ValueError("USB-C source CC resistors must be declared as Rp")
            if resistor_attachments and self.source_rail is None:
                raise ValueError("USB-C source Rp requirements must name the source rail")
            if self.source_rail is not None and any(
                item.rail_net != self.source_rail for item in resistor_attachments
            ):
                raise ValueError("USB-C source Rp resistors must use the declared source rail")
        elif self.role == "sink":
            if any(item.behavior != "rd" for item in resistor_attachments):
                raise ValueError("USB-C sink CC resistors must be declared as Rd")
            if any(item.rail_net != self.ground_net for item in resistor_attachments):
                raise ValueError("USB-C sink Rd resistors must connect to the declared ground net")
        elif self.role == "dual_role" and len(controller_attachments) != 2:
            raise ValueError("USB-C dual-role ports require controller pins for both CC lines")

        if controller_attachments:
            if self.controller is None:
                raise ValueError("USB-C controller pin mappings need a controller identity")
            if any(
                item.controller_pin.rsplit(".", 1)[0].casefold()
                != self.controller.reference.casefold()
                for item in controller_attachments
            ):
                raise ValueError("USB-C CC controller pins must belong to the declared controller")
            if len({item.controller_pin.casefold() for item in controller_attachments}) != len(
                controller_attachments
            ):
                raise ValueError("USB-C CC controller pins must be unique")
        elif self.controller is not None:
            raise ValueError("USB-C controller identity has no mapped CC pins")
        if (
            self.role in {"source", "sink"}
            and len(attachments) == 2
            and type(attachments[0]) is not type(attachments[1])
        ):
            raise ValueError(
                "USB-C source or sink CC lines must both use resistors or controller pins"
            )
        if self.role == "dual_role" and any(
            not isinstance(item, UsbCcControllerAttachment) for item in attachments
        ):
            raise ValueError("USB-C dual-role ports require controller pins for both CC lines")
        return self


class UsbCAnalysis(StrictModel):
    """Project-authored USB-C port role, CC, VBUS, ground, and protection requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    ports: Annotated[tuple[UsbCPortRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_ports_and_cc_nets(self) -> UsbCAnalysis:
        if len({port.id for port in self.ports}) != len(self.ports):
            raise ValueError("USB-C port IDs must be unique")
        if len({port.connector.casefold() for port in self.ports}) != len(self.ports):
            raise ValueError("USB-C connector references must be unique")
        cc_nets = [net for port in self.ports for net in (port.cc1.net, port.cc2.net)]
        if len(set(cc_nets)) != len(cc_nets):
            raise ValueError("USB-C CC nets must be unique across configured ports")
        return self


class PowerLoad(StrictModel):
    id: Identifier
    basis: NonEmptyText
    steady_a: NonNegativeMeasure
    startup_a: NonNegativeMeasure
    startup_s: NonNegativeMeasure


class PowerRail(StrictModel):
    id: Identifier
    basis: NonEmptyText
    voltage_v: ElectricalPositive
    continuous_limit_a: ElectricalPositive
    peak_limit_a: ElectricalPositive
    peak_duration_limit_s: ElectricalPositive
    loads: Annotated[tuple[PowerLoad, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_loads(self) -> PowerRail:
        if len({load.id for load in self.loads}) != len(self.loads):
            raise ValueError("Load IDs must be unique within a rail")
        if self.peak_limit_a < self.continuous_limit_a:
            raise ValueError("Peak rating cannot be below continuous rating")
        return self


class PowerPinEndpointRequirement(StrictModel):
    """Reviewed component identity and pins assigned to one authored rail role."""

    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def endpoint_pins_are_local_and_unique(self) -> PowerPinEndpointRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Power endpoint pins must belong to the declared component")
        if len({pin.casefold() for pin in self.pins}) != len(self.pins):
            raise ValueError("Power endpoint pins must be unique")
        return self


class PowerSourceGroupRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    selection: Literal["all", "any"]
    endpoints: Annotated[tuple[PowerPinEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_source_endpoints(self) -> PowerSourceGroupRequirement:
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("Power source endpoint IDs must be unique within a group")
        if len({item.reference.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("A power source group cannot repeat a component reference")
        return self


class PowerLoadConnectivityRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    endpoints: Annotated[tuple[PowerPinEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_load_endpoints(self) -> PowerLoadConnectivityRequirement:
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("Power load endpoint IDs must be unique within a load")
        if len({item.reference.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("A power load cannot repeat a component reference")
        return self


class PowerConnectivityRailRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    net: NetName
    source_groups: Annotated[tuple[PowerSourceGroupRequirement, ...], Field(min_length=1)]
    loads: Annotated[tuple[PowerLoadConnectivityRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_rail_relationships(self) -> PowerConnectivityRailRequirement:
        if len({item.id.casefold() for item in self.source_groups}) != len(self.source_groups):
            raise ValueError("Power source group IDs must be unique within a rail")
        if len({item.id.casefold() for item in self.loads}) != len(self.loads):
            raise ValueError("Power load IDs must be unique within a rail")
        pins = [
            pin.casefold()
            for group in self.source_groups
            for endpoint in group.endpoints
            for pin in endpoint.pins
        ]
        pins.extend(
            pin.casefold()
            for load in self.loads
            for endpoint in load.endpoints
            for pin in endpoint.pins
        )
        if len(set(pins)) != len(pins):
            raise ValueError("A power endpoint pin cannot be assigned more than once per rail")
        return self


class PowerConnectivityAnalysis(StrictModel):
    """Project-authored source and load pin membership for named power rails."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    rails: Annotated[tuple[PowerConnectivityRailRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_rails_and_endpoint_pins(self) -> PowerConnectivityAnalysis:
        if len({item.id.casefold() for item in self.rails}) != len(self.rails):
            raise ValueError("Power connectivity rail IDs must be unique")
        if len({item.net for item in self.rails}) != len(self.rails):
            raise ValueError("Power connectivity rails must use distinct net names")
        pins = [
            pin.casefold()
            for rail in self.rails
            for group in rail.source_groups
            for endpoint in group.endpoints
            for pin in endpoint.pins
        ]
        pins.extend(
            pin.casefold()
            for rail in self.rails
            for load in rail.loads
            for endpoint in load.endpoints
            for pin in endpoint.pins
        )
        if len(set(pins)) != len(pins):
            raise ValueError("A power endpoint pin cannot be assigned to multiple rails or roles")
        return self


class SimulationMeasure(StrictModel):
    id: Identifier
    expression: SpiceExpression
    statistic: Literal["min", "max", "avg", "rms", "pp"]
    unit: Literal["V", "A", "W", "dB", "rad", "ratio"]
    start: NonNegativeMeasure
    stop: ElectricalPositive
    minimum: FiniteMeasure | None = None
    maximum: FiniteMeasure | None = None

    @model_validator(mode="after")
    def bounded_window(self) -> SimulationMeasure:
        if self.stop <= self.start:
            raise ValueError("Measurement stop must exceed start")
        if self.minimum is None and self.maximum is None:
            raise ValueError("A measurement needs at least one acceptance limit")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Measurement minimum exceeds maximum")
        return self


class SimulationModel(StrictModel):
    id: Identifier
    basis: NonEmptyText
    deck: RepositoryPath
    # All paths are repository-relative. Includes must be explicitly inventoried.
    model_sha256: Mapping[RepositoryPath, Digest]
    source_sha256: Mapping[RepositoryPath, Digest]
    measures: Annotated[tuple[SimulationMeasure, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def complete_model_binding(self) -> SimulationModel:
        if self.deck not in self.model_sha256 or not self.source_sha256:
            raise ValueError("Bind the deck, all model dependencies, and reviewed design sources")
        if len({item.id for item in self.measures}) != len(self.measures):
            raise ValueError("Measurement IDs must be unique")
        return self


class TransientAnalysis(SimulationModel):
    analysis: Literal["tran"] = "tran"
    step_s: ElectricalPositive
    stop_s: ElectricalPositive

    @model_validator(mode="after")
    def transient_windows(self) -> TransientAnalysis:
        if self.step_s >= self.stop_s:
            raise ValueError("Transient step must be smaller than stop")
        for measure in self.measures:
            if measure.stop > self.stop_s or measure.stop - measure.start < self.step_s:
                raise ValueError(
                    "Transient measurement window is outside the run or below its step"
                )
        return self


class FrequencyAnalysis(SimulationModel):
    analysis: Literal["ac"] = "ac"
    start_hz: ElectricalPositive
    stop_hz: ElectricalPositive
    points_per_decade: Annotated[int, Field(ge=10, le=10000)] = 100

    @model_validator(mode="after")
    def frequency_windows(self) -> FrequencyAnalysis:
        if self.stop_hz <= self.start_hz:
            raise ValueError("Frequency stop must exceed start")
        for measure in self.measures:
            if measure.start < self.start_hz or measure.stop > self.stop_hz:
                raise ValueError("Frequency measurement window is outside the sweep")
        return self


class PowerAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    rails: Annotated[tuple[PowerRail, ...], Field(min_length=1)]
    startup: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]
    steady_state: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_rails(self) -> PowerAnalysis:
        if len({rail.id for rail in self.rails}) != len(self.rails):
            raise ValueError("Power rail IDs must be unique")
        for case in self.startup:
            if not any(m.unit == "A" and m.statistic == "max" for m in case.measures):
                raise ValueError("Every startup case needs a peak current limit")
        for case in self.steady_state:
            if not all(
                any(m.unit == unit and m.statistic == "avg" for m in case.measures)
                for unit in ("A", "W")
            ):
                raise ValueError("Every steady-state case needs average current and power limits")
        return self


class HighFrequencyAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    frequency_hz: ElectricalPositive
    rise_time_s: ElectricalPositive
    sweeps: Annotated[tuple[FrequencyAnalysis, ...], Field(min_length=1)]
    waveforms: Annotated[tuple[TransientAnalysis, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def waveform_resolution(self) -> HighFrequencyAnalysis:
        for case in self.waveforms:
            if case.step_s > min(self.rise_time_s / 10, 1 / (20 * self.frequency_hz)):
                raise ValueError(
                    "Waveform step needs at least 10 samples per rise and 20 per cycle"
                )
            if case.stop_s < 2 / self.frequency_hz:
                raise ValueError("Waveform run must cover at least two nominal cycles")
        return self


class ElectricalAnalysisContract(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    ngspice_version: NonEmptyText
    ngspice_source_sha256: Digest | None = None
    grounding: Annotated[
        GroundingAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]
    pcb_return_paths: Annotated[
        PcbReturnPathsAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ] = Field(
        default_factory=lambda: AnalysisPending(
            reason="Review exact PCB return pads, their copper connectivity, and any intentional isolation."
        )
    )
    pin_connectivity: (
        Annotated[
            PinConnectivityAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    i2c_pullups: (
        Annotated[
            I2cPullupAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    can_termination: (
        Annotated[
            CanTerminationAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    usb_c: (
        Annotated[
            UsbCAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    spi: (
        Annotated[
            SpiAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    serial_peers: (
        Annotated[
            SerialPeerAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    digital_peer_voltages: (
        Annotated[
            DigitalPeerVoltageAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    component_voltage_ratings: (
        Annotated[
            ComponentVoltageRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    component_power_ratings: (
        Annotated[
            ComponentPowerRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    connector_contact_ratings: (
        Annotated[
            ConnectorContactRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    mosfet_stress: (
        Annotated[
            MosfetStressAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    rs485: (
        Annotated[
            Rs485Analysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    control_inputs: (
        Annotated[
            ControlInputsAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    test_access: (
        Annotated[
            TestAccessAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    power: Annotated[
        PowerAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]
    power_connectivity: (
        Annotated[
            PowerConnectivityAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    high_frequency: Annotated[
        HighFrequencyAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]

    @model_validator(mode="after")
    def unique_cases(self) -> ElectricalAnalysisContract:
        cases: list[SimulationModel] = []
        if isinstance(self.power, PowerAnalysis):
            cases.extend((*self.power.startup, *self.power.steady_state))
        if isinstance(self.high_frequency, HighFrequencyAnalysis):
            cases.extend((*self.high_frequency.sweeps, *self.high_frequency.waveforms))
        if len({case.id.casefold() for case in cases}) != len(cases):
            raise ValueError("Simulation IDs must be unique across all lanes")
        if isinstance(self.power_connectivity, PowerConnectivityAnalysis) and isinstance(
            self.power, PowerAnalysis
        ):
            budget_rails = {rail.id: {load.id for load in rail.loads} for rail in self.power.rails}
            mapped_rails = {
                rail.id: {load.id for load in rail.loads} for rail in self.power_connectivity.rails
            }
            if set(mapped_rails) != set(budget_rails):
                raise ValueError(
                    "Power connectivity rail IDs must cover the authored power budget rails"
                )
            if mapped_rails != budget_rails:
                raise ValueError(
                    "Power connectivity load IDs must match the authored rail budget loads"
                )
        return self


class ElectricalCheck(StrictModel):
    id: NonEmptyText
    status: Literal["PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE", "NOT_CONFIGURED"]
    detail: NonEmptyText
    observed: FiniteMeasure | None = None
    unit: str | None = None


class ElectricalAnalysisReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_ANALYSIS"] = "ELECTRICAL_ANALYSIS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    source: SourceState | None = None
    status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    run_directory: str = ""
    input_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
    checks: tuple[ElectricalCheck, ...]
    limits: tuple[str, ...] = (
        "Grounding covers declared schematic pins; copper return paths and physical bonds need review.",
        "PCB return paths report native pad/zone connectivity and declared net ties; they do not prove manufactured continuity or first-article acceptance.",
        "Pin relationships compare schematic nets; net ties and physical continuity need separate review.",
        (
            "I2C pull-up ranges compare direct resistors, exact mapped series chains, and mapped array channels; "
            "optional authored rail-to-input voltage checks compare declared limits and exact pin identity, "
            "but do not verify source values, transients, array internals, or off-board networks."
        ),
        (
            "Optional I2C resistor-window checks use project-authored rail, low-level, sink-current, "
            "bus-capacitance and rise-time inputs with an ideal 30%-to-70% RC model; they do not include "
            "component tolerances, nonlinear or active pull-ups, off-board loading, or measured waveforms."
        ),
        (
            "CAN checks compare declared bus pins, local direct/split paths, DNP options, and any mapped "
            "split midpoint capacitor's nominal value and pins; external hardware, physical bus-end placement, "
            "and capacitor placement, derating, impedance, and EMC need separate evidence."
        ),
        (
            "USB-C checks compare declared CC/VBUS/GND pin assignments, fitted Rp/Rd resistors, exact "
            "controller/protection identity, any authored VBUS component/net map, and an explicitly mapped "
            "nominal port-side VBUS capacitance range; it does not verify capacitor derating, tolerance, "
            "dynamic behavior, device conduction, or PCB/contact continuity, while controller behavior, "
            "PD and protection performance need separate evidence."
        ),
        (
            "Direct serial voltage checks compare authored guaranteed output ranges with receiver thresholds "
            "and absolute limits; cited sources, operating conditions, transients, and device behavior are "
            "not independently validated."
        ),
        (
            "Component voltage-rating checks compare exact mapped part identity and pin/net assignments, "
            "a project-authored maximum stress envelope, a datasheet working rating, and a project-selected "
            "utilization limit; the sources and stress derivation are not independently validated."
        ),
        "Simulation results apply only to the reviewed models, cases, timestep and frequency grid.",
        "Power budgets use simultaneous worst-case loads and engineer-supplied derated path ratings.",
        "Physical startup, thermal behavior, RF/EMC and manufacturing acceptance remain unverified.",
        (
            "Test-access contracts check exact schematic pins and separately check PCB footprint/pad, "
            "net and outer-mask declarations; probe clearance, nearby obstructions, covers and "
            "manufacturing test coverage remain unverified."
        ),
    )


class ElectricalSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[ElectricalAnalysisReport, ...]


class ElectricalSetupReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["CREATED"] = "CREATED"
    project_id: Identifier
    contract: RepositoryPath
    changed: tuple[RepositoryPath, ...]
    next_actions: tuple[NonEmptyText, ...]


class ElectricalInputInventory(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["UNREVIEWED"] = "UNREVIEWED"
    build_authorized: Literal[False] = False
    project_id: Identifier
    run_directory: NonEmptyText
    source_sha256: Mapping[RepositoryPath, Digest]
    model_sha256: Mapping[RepositoryPath, Digest]
    next_actions: tuple[NonEmptyText, ...]


class PartCadComponent(StrictModel):
    reference: Identifier
    symbol_id: str
    value: str
    footprint: str
    part_id: str | None = None
    source_path: RepositoryPath
    uuid: NonEmptyText
    dnp: bool = False
    exclude_from_bom: bool = False


class PartSourceEdit(StrictModel):
    path: RepositoryPath
    before: str | None
    after: str


class PartCadChanges(StrictModel):
    edits: tuple[PartSourceEdit, ...] = ()
    pending_references: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class PartSelectionAssignment(StrictModel):
    reference: Identifier
    part_id: Identifier


class PartSelectionMap(PurchasingSchemaModel):
    project_id: Identifier
    preconditions: Mapping[RepositoryPath, Digest | None]
    assignments: tuple[PartSelectionAssignment, ...] = ()
    locked: bool = False
    after_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_assignments(self) -> PartSelectionMap:
        references = [item.reference for item in self.assignments]
        if len(references) != len(set(references)):
            raise ValueError("Part selection repeats a component reference")
        return self


class PartPickerItem(StrictModel):
    component: PartCadComponent
    choice_ids: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class PartPickerReport(PurchasingSchemaModel):
    lane: Literal["PART_PICKER"] = "PART_PICKER"
    status: Literal["READY", "NEEDS_CATALOG", "BLOCKED"]
    project_id: Identifier
    items: tuple[PartPickerItem, ...] = ()
    choices: tuple[PartRecord, ...] = ()
    selection_template: PartSelectionMap | None = None
    issues: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    evidence: ContractCoachReport | None = None
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class PartSelectionReport(PurchasingSchemaModel):
    lane: Literal["PART_SELECTION"] = "PART_SELECTION"
    status: Literal["PLAN", "APPLIED", "APPLIED_NEEDS_PCB_UPDATE", "BLOCKED"]
    project_id: Identifier
    edits: tuple[PartSourceEdit, ...] = ()
    pending_references: tuple[Identifier, ...] = ()
    locked_map: str | None = None
    issues: tuple[NonEmptyText, ...] = ()
    next_commands: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class AutoCadItem(StrictModel):
    reference: NonEmptyText
    footprint: str
    status: Literal["READY", "ALREADY_PRESENT", "NEEDS_REVIEW"]
    detail: NonEmptyText


class AutoCadPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    preconditions: dict[RepositoryPath, Digest | None]
    after_hashes: dict[RepositoryPath, Digest]


class AutoCadAsset(StrictModel):
    source: NonEmptyText
    sha256: Digest
    destination: RepositoryPath


class AutoCadProvenance(StrictModel):
    schema_version: Literal["1"] = "1"
    footprint: NonEmptyText
    source: NonEmptyText
    source_sha256: Digest
    models: tuple[AutoCadAsset, ...]
    alignment_basis: Literal["matching_pad_geometry_and_authored_model_transforms"] = (
        "matching_pad_geometry_and_authored_model_transforms"
    )
    physical_fit_verified: Literal[False] = False


class AutoCadReport(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    status: Literal["PLAN", "APPLIED", "NEEDS_REVIEW", "BLOCKED"]
    items: tuple[AutoCadItem, ...] = ()
    files: tuple[RepositoryPath, ...] = ()
    issues: tuple[str, ...] = ()
    plan_path: str | None = None
    receipt_directory: str
    diff: str = ""
    build_authorized: Literal[False] = False


class SupplierHandoffPlan(StrictModel):
    """Reviewed, source-bound BOM payload for one explicit supplier submission."""

    schema_version: Literal["1"] = "1"
    supplier: Literal["digikey"] = "digikey"
    project_id: Identifier
    parts_report: RepositoryPath
    report_sha256: Digest
    payload: DigiKeyHandoffPayload
    payload_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    preconditions: Mapping[RepositoryPath, Digest | None]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class SupplierHandoffReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["PREPARED", "SENT", "UNCERTAIN", "BLOCKED"]
    project_id: Identifier
    supplier: Literal["digikey"] = "digikey"
    handoff: RepositoryPath
    handoff_sha256: Digest
    payload_sha256: Digest
    attempt_receipt: RepositoryPath | None = None
    single_use_url: (
        Annotated[
            str,
            StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
        ]
        | None
    ) = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


ForeignFormat = Literal[
    "auto", "pads", "altium", "eagle", "cadstar", "fabmaster", "pcad", "solidworks"
]


class ForeignPcbReport(StrictModel):
    """Conversion evidence is intentionally weaker than an accepted native design."""

    schema_version: Literal["1"] = "1"
    status: Literal["PASS", "FAIL"]
    review_required: Literal[True] = True
    build_authorized: Literal[False] = False
    project_id: str
    toolchain_id: str
    input_format: str
    source_file: str
    source_sha256: Digest | None = None
    run_directory: str
    runner: Literal["none", "local", "container"] = "none"
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    native_summary: KiCadForeignImportSummary | None = None
    board_sha256: Digest | None = None
    import_preview: ProjectImportReport | None = None
    next_command: str | None = None
    next_actions: tuple[str, ...] = ()
    error: str | None = None

    @model_validator(mode="after")
    def successful_selection_is_valid(self) -> ForeignPcbReport:
        if self.status == "PASS" and (
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.project_id) is None
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.toolchain_id) is None
            or self.input_format not in ForeignFormat.__args__
        ):
            raise ValueError("Successful conversion needs valid project, toolchain and format IDs")
        return self


class ElectricalChartCase(StrictModel):
    """One chart and numeric export derived from a retained simulation case."""

    id: Identifier
    status: Literal["PASS", "SKIPPED", "FAIL"]
    samples: Annotated[int, Field(ge=0)] = 0
    waveform_sha256: Digest | None = None
    csv: RepositoryPath | None = None
    png: RepositoryPath | None = None
    svg: RepositoryPath | None = None
    detail: NonEmptyText


class ElectricalChartsReport(StrictModel):
    """Chart output remains secondary evidence bound to an analysis receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS"] = "ELECTRICAL_CHARTS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    status: Literal["PASS", "PARTIAL", "FAIL"]
    source_analysis_status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    source_receipt: NonEmptyText
    source_report_sha256: Digest
    run_directory: NonEmptyText
    cases: tuple[ElectricalChartCase, ...]
    grounding_csv: RepositoryPath | None = None
    power_csv: RepositoryPath | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    next_actions: tuple[NonEmptyText, ...] = ()


class ElectricalChartsSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS_SUITE"] = "ELECTRICAL_CHARTS_SUITE"
    status: Literal["PASS", "PARTIAL", "FAIL"]
    run_directory: NonEmptyText
    reports: tuple[ElectricalChartsReport, ...]


class CadProviderIdentity(StrictModel):
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    component_supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_name: NonEmptyText
    model_uuid: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
    model_title: str = ""


class CadSourceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest
    source_url: str | None = None


class CadSourceBundle(StrictModel):
    schema_version: Literal["1"] = "1"
    provider: Literal["easyeda"] = "easyeda"
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_file: RepositoryPath
    symbol_name: NonEmptyText
    footprint_file: RepositoryPath
    footprint_name: NonEmptyText
    model_file: RepositoryPath
    files: tuple[CadSourceFile, ...]
    source_url: NonEmptyText
    source_sha256: Digest
    retrieved_at: NonEmptyText
    converter_version: Literal["1.0.1"] = "1.0.1"
    converter_sha256: Digest | None = None
    issues: tuple[NonEmptyText, ...] = ()


class CadSourceReport(StrictModel):
    status: Literal["READY", "BLOCKED"]
    supplier_id: str
    bundle_directory: str | None = None
    bundle: CadSourceBundle | None = None
    cache_hit: bool = False
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str


class CadStepReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["REVIEW", "BLOCKED"]
    project_id: Identifier
    supplier_id: str
    source_bundle_sha256: Digest | None = None
    source_step_sha256: Digest | None = None
    kicad_version: str | None = None
    image: str | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str
    alignment_verified: Literal[False] = False
    physical_fit_verified: Literal[False] = False


class CadBundleCheck(StrictModel):
    status: Literal["READY", "BLOCKED"]
    symbol_pins: tuple[str, ...] = ()
    footprint_pads: tuple[str, ...] = ()
    model_references: tuple[str, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    physical_fit_verified: Literal[False] = False


class CadImportPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    bundle_dir: str
    bundle_sha256: Digest
    preconditions: Mapping[RepositoryPath, Digest | None]
    after_hashes: Mapping[RepositoryPath, Digest]


class CadImportReport(StrictModel):
    status: Literal["PLAN", "APPLIED", "BLOCKED"]
    project_id: Identifier
    symbol_id: str | None = None
    footprint_id: str | None = None
    files: tuple[RepositoryPath, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    check: CadBundleCheck | None = None
    plan_path: str | None = None
    receipt_directory: str
    diff: str = ""
    build_authorized: Literal[False] = False


class CadSourcingReview(StrictModel):
    source: CadSourceReport
    import_plan: CadImportReport | None = None
    review_id: str
