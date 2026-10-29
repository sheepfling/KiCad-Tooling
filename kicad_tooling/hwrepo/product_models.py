"""Product, assembly, assurance, and generated product-view contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NonEmptyText,
    PositiveCount,
    PositiveMeasure,
    Reference,
    RepositoryPath,
    StrictModel,
)
from .policy_issue_models import PolicyIssue


class Assurance(str, Enum):
    UNKNOWN = "unknown"
    ASSUMED = "assumed"
    INFERRED = "inferred"
    OBSERVED = "observed"
    MANUFACTURER_DOCUMENTED = "manufacturer_documented"
    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"


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
    from_terminal: Annotated[Identifier, Field(alias="from")]
    to_terminal: Annotated[Identifier, Field(alias="to")]
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
    from_terminal: Annotated[Terminal, Field(alias="from")]
    to_terminal: Annotated[Terminal, Field(alias="to")]
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
    from_terminal: Annotated[Terminal, Field(alias="from")]
    to_terminal: Annotated[Terminal, Field(alias="to")]
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
