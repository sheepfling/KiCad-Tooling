"""Pure projections for deterministic product and repository outputs."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from .contracts import read_model, repo_path
from .discovery import load_registry
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .models import (
    LibrariesCatalog,
    LibrarySbom,
    TemplateAdoptionRecord,
    TemplateContract,
    TemplateUpgradesCatalog,
)
from .part_catalog_models import PartRecord
from .product import load_repository
from .product_models import (
    AssemblyKind,
    BomRow,
    ConnectionKind,
    ElectricalConnectionView,
    ElectricalView,
    HarnessSchedule,
    HarnessScheduleRow,
    ProductIndex,
    ProductRecord,
    SystemConnectionView,
    SystemView,
    Variant,
)
from .product_occurrences import (
    ProductOccurrenceIndex,
    excluded,
    occurrences,
    occurrences_for,
    product_occurrence_index,
)
from .product_repository_models import ProductRepository
from .project_models import ProjectManifest, ProjectTestContract
from .release_contract_models import ReleaseManifest, ReleasePoliciesCatalog
from .sourcing_models import SourcingSnapshot


def csv_cell(value: str) -> str:
    """Protect every textual CSV value from spreadsheet formula evaluation."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def model_json_bytes(model: BaseModel) -> bytes:
    return (
        model.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def schema_json_bytes(model: type[BaseModel]) -> bytes:
    return (
        json.dumps(
            model.model_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def bom_rows(
    product: ProductRecord,
    parts: Mapping[str, PartRecord],
    variant: Variant,
    *,
    occurrence_index: ProductOccurrenceIndex | None = None,
) -> tuple[BomRow, ...]:
    """Expand built/phantom members but retain purchased assemblies as one row."""
    assemblies = {assembly.id: assembly for assembly in product.assemblies}
    totals: dict[str, tuple[int, list[str]]] = {}
    instance_index = (
        occurrences(product)
        if occurrence_index is None
        else occurrences_for(product, occurrence_index)
    )
    for path, occurrence in instance_index.items():
        if excluded(path, variant):
            continue
        identifier = occurrence.item
        assembly = assemblies.get(identifier)
        if assembly is not None:
            if assembly.kind is not AssemblyKind.PURCHASED:
                continue
            if assembly.purchase_part is None:
                raise ValueError(f"Purchased assembly missing part: {assembly.id}")
            identifier = assembly.purchase_part
        count, instances = totals.get(identifier, (0, []))
        totals[identifier] = (count + occurrence.quantity, [*instances, path or "ROOT"])

    rows: list[BomRow] = []
    for identifier in sorted(totals):
        quantity, instances = totals[identifier]
        part = parts[identifier]
        rows.append(
            BomRow(
                part_id=identifier,
                revision=part.revision,
                quantity=quantity,
                unit=part.unit,
                instances=";".join(sorted(instances)),
                manufacturer=part.manufacturer,
                mpn=part.mpn,
                disposition="NOT FOR MANUFACTURE",
            )
        )
    return tuple(rows)


def csv_bytes(rows: tuple[BomRow, ...]) -> bytes:
    stream = io.StringIO(newline="")
    columns = (
        "part_id",
        "revision",
        "quantity",
        "unit",
        "instances",
        "manufacturer",
        "mpn",
        "disposition",
    )
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "part_id": csv_cell(row.part_id),
                "revision": csv_cell(row.revision),
                "quantity": row.quantity,
                "unit": csv_cell(row.unit),
                "instances": csv_cell(row.instances),
                "manufacturer": csv_cell(row.manufacturer),
                "mpn": csv_cell(row.mpn),
                "disposition": csv_cell(row.disposition),
            }
        )
    return stream.getvalue().encode("utf-8")


def harness_schedule(product: ProductRecord, variant: Variant) -> HarnessSchedule:
    """Project typed harness attributes and endpoints without inventing a purchasable part."""
    terminals = {terminal.id: terminal for terminal in product.terminals}
    rows: list[HarnessScheduleRow] = []
    for harness in sorted(product.harnesses, key=lambda item: item.id):
        if excluded(harness.instance, variant):
            continue
        connections = tuple(
            sorted(
                (
                    connection
                    for connection in product.connections
                    if connection.kind is ConnectionKind.ELECTRICAL
                    and connection.harness == harness.id
                    and variant.id in connection.variants
                ),
                key=lambda item: item.id,
            )
        )
        if not connections:
            continue
        endpoints = tuple(
            sorted(
                {
                    terminal_id
                    for connection in connections
                    for terminal_id in (connection.from_terminal, connection.to_terminal)
                }
            )
        )
        if not set(endpoints) <= set(terminals):
            raise ValueError(f"Harness {harness.id} references an unknown terminal")
        rows.append(
            HarnessScheduleRow(
                harness_id=harness.id,
                revision=harness.revision,
                instance=harness.instance,
                length_mm=harness.length_mm,
                conductor_area_mm2=harness.conductor_area_mm2,
                electrical_connection_ids=tuple(connection.id for connection in connections),
                endpoint_terminal_ids=endpoints,
                assurance=harness.assurance,
                evidence=tuple(sorted(harness.evidence)),
                disposition="NOT FOR MANUFACTURE",
            )
        )
    return HarnessSchedule(
        product=product.id,
        revision=product.revision,
        variant=variant.id,
        variant_revision=variant.revision,
        rows=tuple(rows),
    )


def harness_schedule_csv_bytes(schedule: HarnessSchedule) -> bytes:
    """Render the typed schedule as a review CSV, not a purchase authorization."""
    stream = io.StringIO(newline="")
    columns = (
        "harness_id",
        "revision",
        "instance",
        "length_mm",
        "conductor_area_mm2",
        "electrical_connection_ids",
        "endpoint_terminal_ids",
        "assurance",
        "evidence",
        "disposition",
    )
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in schedule.rows:
        writer.writerow(
            {
                "harness_id": csv_cell(row.harness_id),
                "revision": csv_cell(row.revision),
                "instance": csv_cell(row.instance),
                "length_mm": row.length_mm,
                "conductor_area_mm2": row.conductor_area_mm2,
                "electrical_connection_ids": csv_cell(";".join(row.electrical_connection_ids)),
                "endpoint_terminal_ids": csv_cell(";".join(row.endpoint_terminal_ids)),
                "assurance": csv_cell(row.assurance.value),
                "evidence": csv_cell(";".join(row.evidence)),
                "disposition": csv_cell(row.disposition),
            }
        )
    return stream.getvalue().encode("utf-8")


def electrical_view(product: ProductRecord, variant: Variant) -> ElectricalView:
    terminals = {terminal.id: terminal for terminal in product.terminals}
    connections = tuple(
        ElectricalConnectionView(
            id=connection.id,
            **{
                "from": terminals[connection.from_terminal],
                "to": terminals[connection.to_terminal],
            },
            harness=connection.harness,
            assurance=connection.assurance,
            evidence=tuple(sorted(connection.evidence)),
        )
        for connection in sorted(product.connections, key=lambda item: item.id)
        if connection.kind.value == "electrical" and variant.id in connection.variants
    )
    return ElectricalView(
        product=product.id,
        revision=product.revision,
        variant=variant.id,
        variant_revision=variant.revision,
        connections=connections,
    )


def system_view(product: ProductRecord, variant: Variant) -> SystemView:
    """Project every explicit semantic relation without recasting it as a wire."""
    terminals = {terminal.id: terminal for terminal in product.terminals}
    connections = tuple(
        SystemConnectionView(
            id=connection.id,
            kind=connection.kind,
            **{
                "from": terminals[connection.from_terminal],
                "to": terminals[connection.to_terminal],
            },
            harness=connection.harness,
            assurance=connection.assurance,
            evidence=tuple(sorted(connection.evidence)),
        )
        for connection in sorted(product.connections, key=lambda item: item.id)
        if variant.id in connection.variants
    )
    return SystemView(
        product=product.id,
        revision=product.revision,
        variant=variant.id,
        variant_revision=variant.revision,
        connections=connections,
    )


def library_sbom(root: Path) -> LibrarySbom:
    """Project the controlled shared-CAD-library inventory with evidence hashes."""
    registry = load_registry(root)
    catalog = read_model(repo_path(root, registry.catalogs.libraries), LibrariesCatalog)
    return LibrarySbom(libraries=tuple(sorted(catalog.libraries, key=lambda item: item.id)))


def expected_outputs(
    root: Path, selected_project_ids: tuple[str, ...] | None = None
) -> dict[str, bytes]:
    """Build full outputs or just the projections owned by selected projects."""
    repository = load_repository(root, selected_project_ids)
    return expected_outputs_from_repository(root, repository, selected_project_ids)


def expected_outputs_from_repository(
    root: Path,
    repository: ProductRepository,
    selected_project_ids: tuple[str, ...] | None = None,
) -> dict[str, bytes]:
    """Project generation artifacts from one validated repository capture."""
    if repository.issues:
        raise ValueError(f"Cannot generate from invalid records: {repository.issues}")
    index_document = repository.product_index_document
    if index_document is None:
        raise ValueError("Cannot generate without a captured product index")
    outputs: dict[str, bytes] = {}
    if selected_project_ids is None:
        outputs = {
            "schemas/product-v1.schema.json": schema_json_bytes(ProductRecord),
            "schemas/product-index-v1.schema.json": schema_json_bytes(ProductIndex),
            "schemas/project-manifest-v1.schema.json": schema_json_bytes(ProjectManifest),
            "schemas/project-tests-v1.schema.json": schema_json_bytes(ProjectTestContract),
            "schemas/electrical-analysis-v1.schema.json": schema_json_bytes(
                ElectricalAnalysisContract
            ),
            "schemas/release-manifest-v1.schema.json": schema_json_bytes(ReleaseManifest),
            "schemas/release-policies-v1.schema.json": schema_json_bytes(ReleasePoliciesCatalog),
            "schemas/template-adoption-v1.schema.json": schema_json_bytes(TemplateAdoptionRecord),
            "schemas/template-contract-v1.schema.json": schema_json_bytes(TemplateContract),
            "schemas/template-upgrades-v1.schema.json": schema_json_bytes(TemplateUpgradesCatalog),
            "generated/library-sbom-v1.json": model_json_bytes(library_sbom(root)),
            "schemas/sourcing-snapshot-v1.schema.json": schema_json_bytes(SourcingSnapshot),
        }
    index = index_document.value
    product_paths = {entry.id: Path(entry.path).parent.as_posix() for entry in index.products}
    for product in repository.products:
        occurrence_index = product_occurrence_index(repository.product_sources[product.id])
        for variant in product.variants:
            prefix = f"{product_paths[product.id]}/build/{variant.id}"
            outputs[prefix + ".bom.csv"] = csv_bytes(
                bom_rows(
                    product,
                    repository.parts,
                    variant,
                    occurrence_index=occurrence_index,
                )
            )
            outputs[prefix + ".electrical.json"] = model_json_bytes(
                electrical_view(product, variant)
            )
            outputs[prefix + ".system.json"] = model_json_bytes(system_view(product, variant))
            schedule = harness_schedule(product, variant)
            outputs[prefix + ".harness-schedule.json"] = model_json_bytes(schedule)
            outputs[prefix + ".harness-schedule.csv"] = harness_schedule_csv_bytes(schedule)
    return outputs
