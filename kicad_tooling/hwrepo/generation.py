"""Deterministic typed review projections; procurement rows never authorize a build."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from . import __version__
from .contracts import read_model, repo_path, write_model
from .discovery import load_registry
from .models import (
    AssemblyKind,
    BomRow,
    ConnectionKind,
    ElectricalAnalysisContract,
    ElectricalConnectionView,
    ElectricalView,
    HarnessSchedule,
    HarnessScheduleRow,
    LibrariesCatalog,
    LibrarySbom,
    PartRecord,
    ProductIndex,
    ProductRecord,
    ProjectManifest,
    ProjectTestContract,
    ReleaseManifest,
    ReleasePoliciesCatalog,
    SnapshotManifest,
    SnapshotVerification,
    SourcingSnapshot,
    SystemConnectionView,
    SystemView,
    TemplateAdoptionRecord,
    TemplateContract,
    TemplateUpgradesCatalog,
    Variant,
)
from .product import excluded, load_repository, occurrences
from .repository import ephemeral


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
) -> tuple[BomRow, ...]:
    """Expand built/phantom members but retain purchased assemblies as one row."""
    assemblies = {assembly.id: assembly for assembly in product.assemblies}
    totals: dict[str, tuple[int, list[str]]] = {}
    for path, occurrence in occurrences(product).items():
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
    if repository.issues:
        raise ValueError(f"Cannot generate from invalid records: {repository.issues}")
    outputs: dict[str, bytes] = {}
    if selected_project_ids is None:
        outputs = {
            "schemas/product-v1.schema.json": schema_json_bytes(ProductRecord),
            "schemas/product-index-v1.schema.json": schema_json_bytes(ProductIndex),
            "schemas/project-manifest-v1.schema.json": schema_json_bytes(ProjectManifest),
            "schemas/project-tests-v1.schema.json": schema_json_bytes(ProjectTestContract),
            "schemas/electrical-analysis-v1.schema.json": schema_json_bytes(ElectricalAnalysisContract),
            "schemas/release-manifest-v1.schema.json": schema_json_bytes(ReleaseManifest),
            "schemas/release-policies-v1.schema.json": schema_json_bytes(
                ReleasePoliciesCatalog
            ),
            "schemas/template-adoption-v1.schema.json": schema_json_bytes(
                TemplateAdoptionRecord
            ),
            "schemas/template-contract-v1.schema.json": schema_json_bytes(TemplateContract),
            "schemas/template-upgrades-v1.schema.json": schema_json_bytes(
                TemplateUpgradesCatalog
            ),
            "generated/library-sbom-v1.json": model_json_bytes(library_sbom(root)),
            "schemas/sourcing-snapshot-v1.schema.json": schema_json_bytes(
                SourcingSnapshot
            ),
        }
    index = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
    product_paths = {entry.id: Path(entry.path).parent.as_posix() for entry in index.products}
    for product in repository.products:
        for variant in product.variants:
            prefix = f"{product_paths[product.id]}/build/{variant.id}"
            outputs[prefix + ".bom.csv"] = csv_bytes(
                bom_rows(product, repository.parts, variant)
            )
            outputs[prefix + ".electrical.json"] = model_json_bytes(
                electrical_view(product, variant)
            )
            outputs[prefix + ".system.json"] = model_json_bytes(system_view(product, variant))
            schedule = harness_schedule(product, variant)
            outputs[prefix + ".harness-schedule.json"] = model_json_bytes(schedule)
            outputs[prefix + ".harness-schedule.csv"] = harness_schedule_csv_bytes(
                schedule
            )
    return outputs


def drift(
    root: Path, selected_project_ids: tuple[str, ...] | None = None,
    *, output: Path | None = None,
) -> tuple[str, ...]:
    """Detect full or selected-product output drift without writing files."""
    outputs = expected_outputs(root, selected_project_ids)
    destination = root if output is None else output
    issues = [
        f"GENERATION_DRIFT: {name}"
        for name, expected in sorted(outputs.items())
        if not (path := repo_path(destination, name)).is_file() or path.read_bytes() != expected
    ]
    index = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
    directories = ["generated", "schemas"] if selected_project_ids is None else []
    directories.extend(
        f"{Path(entry.path).parent.as_posix()}/build"
        for entry in index.products
        if selected_project_ids is None or set(selected_project_ids).intersection(entry.project_ids)
    )
    found = {
        path.relative_to(destination).as_posix()
        for directory in directories
        for path in (destination / directory).rglob("*")
        if path.is_file()
        and path.relative_to(destination).as_posix() not in {"generated/README.md", "schemas/README.md"}
    }
    issues.extend(f"STALE_OUTPUT: {name}" for name in sorted(found - set(outputs)))
    return tuple(issues)


def generate(
    root: Path, output: Path | None = None,
    selected_project_ids: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Write validated projections only; intentional stale files remain for review."""
    outputs = expected_outputs(root, selected_project_ids)
    destination = root if output is None else output
    destinations = {name: repo_path(destination, name) for name in outputs}
    for path in destinations.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        destinations[name].write_bytes(content)
    return tuple(sorted(outputs))


def check_generation(
    root: Path, selected_project_ids: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Regenerate in isolation and compare an independent pass, without cached outputs."""
    with tempfile.TemporaryDirectory(prefix="kicad-generation-") as temporary:
        output = Path(temporary).resolve()
        generate(root, output, selected_project_ids)
        return drift(root, selected_project_ids, output=output)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def snapshot(root: Path, output: Path) -> SnapshotManifest:
    """Write a retained integrity manifest; it explicitly is not release evidence."""
    outputs = expected_outputs(root)
    root, output = root.resolve(), output.resolve()
    if output == root or (root in output.parents and not output.is_relative_to(root / "build")):
        raise ValueError("In-repository review output must be under build/")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retained evidence: {output}")
    repository = load_repository(root)
    if repository.issues:
        raise ValueError(str(repository.issues))
    sources: set[Path] = set()
    for directory in (
        "catalog",
        "products",
        "projects",
        "examples",
        "libraries",
        "tools",
        "tests",
        ".github",
        "docs",
        "templates",
    ):
        sources.update(
            path
            for path in (root / directory).rglob("*")
            if path.is_file()
            and not ephemeral(path.relative_to(root).as_posix())
        )
    source_hashes = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(sources)
    }
    for name in (
        "README.md", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", ".gitattributes",
        ".gitignore", "pyproject.toml", "template-adoption.json",
    ):
        if (root / name).is_file():
            source_hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    manifest = SnapshotManifest(
        commit=_git(root, "rev-parse", "HEAD"),
        working_tree_clean=not bool(
            _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        ),
        git_status=_git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        python_version=platform.python_version(),
        policy_version=__version__,
        products=tuple(product.id for product in repository.products),
        checks={
            "product_policy": "PASS",
            "kicad": "NOT_RUN",
            "mechanical_fit": "NOT_RUN",
            "human_review": "NOT_RUN",
        },
        sources_sha256=source_hashes,
        artifacts_sha256={
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(outputs.items())
        },
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, content in outputs.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    write_model(output / "manifest.json", manifest)
    return manifest


def verify_snapshot(output: Path) -> SnapshotVerification:
    """Check retained bytes and inventory, not authenticity or source reproduction."""
    manifest = read_model(output / "manifest.json", SnapshotManifest)
    for name, expected in manifest.artifacts_sha256.items():
        if hashlib.sha256(repo_path(output, name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    actual = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    if actual != set(manifest.artifacts_sha256) | {"manifest.json"}:
        raise ValueError("Retained artifact inventory differs")
    return SnapshotVerification(
        status="PASS",
        artifacts=len(manifest.artifacts_sha256),
        scope="artifact_integrity_only_not_authenticity_or_source_reconstruction",
    )
