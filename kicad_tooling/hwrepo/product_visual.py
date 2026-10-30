"""Project one selected product variant into an offline authored-relationship view."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from uuid import uuid4

from ..validate import hashes
from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import model_json_bytes, parse_model_text, repo_path, write_model
from .discovery import load_config, load_registry
from .evidence import digest
from .generation import harness_schedule, system_view
from .layout import CONFIG_NAME, layout, within_roots
from .product import excluded, load_repository, occurrences, validate_product
from .product_models import AssemblyKind, ProductIndex, ProductRecord, Terminal, Variant
from .product_visual_html import render_product_visual
from .product_visual_models import (
    ProductProjectIdentity,
    ProductVisualEndpoint,
    ProductVisualInstance,
    ProductVisualRelation,
    ProductVisualReport,
)


def _endpoint(
    terminal_id: str,
    terminals: dict[str, Terminal],
    known_paths: set[str],
    variant: Variant,
) -> ProductVisualEndpoint:
    terminal = terminals.get(terminal_id)
    if terminal is None:
        return ProductVisualEndpoint(terminal_id=terminal_id, status="MISSING")
    status = (
        "MISSING"
        if terminal.instance not in known_paths
        else "OMITTED"
        if excluded(terminal.instance, variant)
        else "RESOLVED"
    )
    return ProductVisualEndpoint(
        terminal_id=terminal.id,
        instance=terminal.instance,
        pin=terminal.pin,
        interface_id=terminal.interface_id,
        interface_pin=terminal.interface_pin,
        status=status,
    )


def _relationships(
    product: ProductRecord, variant: Variant, known_paths: set[str]
) -> tuple[ProductVisualRelation, ...]:
    terminals = {terminal.id: terminal for terminal in product.terminals}
    harnesses = {harness.id: harness for harness in product.harnesses}
    result: list[ProductVisualRelation] = []
    for connection in sorted(product.connections, key=lambda item: item.id):
        start = _endpoint(connection.from_terminal, terminals, known_paths, variant)
        end = _endpoint(connection.to_terminal, terminals, known_paths, variant)
        harness = harnesses.get(connection.harness) if connection.harness else None
        unresolved = (
            start.status == "MISSING"
            or end.status == "MISSING"
            or (connection.harness is not None and harness is None)
            or (harness is not None and harness.instance not in known_paths)
            or (harness is not None and excluded(harness.instance, variant))
            or (variant.id in connection.variants and "OMITTED" in (start.status, end.status))
        )
        population = (
            "UNRESOLVED"
            if unresolved
            else "INCLUDED"
            if variant.id in connection.variants
            else "OMITTED"
        )
        result.append(
            ProductVisualRelation(
                id=connection.id,
                kind=connection.kind.value,
                from_endpoint=start,
                to_endpoint=end,
                harness=connection.harness,
                assurance=connection.assurance.value,
                evidence=connection.evidence,
                population=population,
            )
        )
    return tuple(result)


def _instances(
    product: ProductRecord, variant: Variant, parts: set[str]
) -> tuple[ProductVisualInstance, ...]:
    expanded = occurrences(product)
    assemblies = {assembly.id: assembly for assembly in product.assemblies}
    result: list[ProductVisualInstance] = []
    for path, occurrence in expanded.items():
        assembly = assemblies.get(occurrence.item)
        kind: Literal["BUILT", "PHANTOM", "PURCHASED", "PART", "UNRESOLVED"]
        if assembly is None:
            kind = "PART" if occurrence.item in parts else "UNRESOLVED"
        elif assembly.kind is AssemblyKind.BUILT:
            kind = "BUILT"
        elif assembly.kind is AssemblyKind.PHANTOM:
            kind = "PHANTOM"
        else:
            kind = "PURCHASED"
        result.append(
            ProductVisualInstance(
                path=path,
                parent=path.rpartition(".")[0] if path else None,
                item=occurrence.item,
                quantity=occurrence.quantity,
                kind=kind,
                population="OMITTED" if excluded(path, variant) else "INCLUDED",
                project_id=assembly.project_id if assembly is not None else None,
            )
        )
    return tuple(result)


def _project_identities(
    root: Path,
    ids: set[str],
    source_hashes: dict[str, str],
) -> tuple[ProductProjectIdentity, ...]:
    projects = {item.id: item for item in load_registry(root).projects}
    result: list[ProductProjectIdentity] = []
    for project_id in sorted(ids):
        project = projects.get(project_id)
        if project is None:
            result.append(
                ProductProjectIdentity(
                    project_id=project_id,
                    status="MISSING",
                    issue="Project ID is absent from the configured discovery catalog.",
                )
            )
            continue
        config_path = repo_path(root, project.config)
        try:
            config = load_config(root, project.config)
            current = hashes(root, config.source_roots)
            source_hashes[project.config] = digest(config_path)
            source_hashes.update(current)
            result.append(
                ProductProjectIdentity(
                    project_id=project_id,
                    config_path=project.config,
                    config_sha256=source_hashes[project.config],
                    source_hashes=current,
                    status="CURRENT",
                )
            )
        except (OSError, ValueError) as exc:
            result.append(
                ProductProjectIdentity(
                    project_id=project_id,
                    config_path=project.config,
                    status="UNAVAILABLE",
                    issue=str(exc),
                )
            )
    return tuple(result)


def build_product_visual(
    root: Path,
    product_id: str,
    variant_id: str,
    output: Path | None = None,
) -> ProductVisualReport:
    """Render the authored variant without treating semantic relations as observed wires."""
    root = root.resolve()
    configuration = layout(root)
    index_path = repo_path(root, configuration.products)
    index_bytes, _ = read_regular_bytes(index_path, maximum=2 * 1024 * 1024)
    index = parse_model_text(index_bytes.decode("utf-8"), ProductIndex)
    matches = [entry for entry in index.products if entry.id == product_id]
    if len(matches) != 1:
        raise ValueError(f"Select one indexed product ID: {product_id}")
    entry = matches[0]
    if (
        not any(
            within_roots(entry.path, (directory,))
            and len(Path(entry.path).relative_to(directory).parts) == 2
            for directory in configuration.product_roots
        )
        or Path(entry.path).name != "product.json"
    ):
        raise ValueError("Indexed product must live in a configured product island")
    product_path = repo_path(root, entry.path)
    product_bytes, _ = read_regular_bytes(product_path, maximum=4 * 1024 * 1024)
    product = parse_model_text(product_bytes.decode("utf-8"), ProductRecord)
    if product.id != product_id:
        raise ValueError("Indexed product identity differs from its record")
    selected_variants = [item for item in product.variants if item.id == variant_id]
    if len(selected_variants) != 1:
        raise ValueError(f"Select one declared product variant: {variant_id}")
    variant = selected_variants[0]
    registry = load_registry(root)
    baseline = (
        configuration.discovery,
        configuration.products,
        registry.catalogs.parts,
        registry.catalogs.interfaces,
        entry.path,
    )
    source_hashes = {name: digest(repo_path(root, name)) for name in baseline}
    adapter = repo_path(root, CONFIG_NAME)
    if adapter.is_file():
        source_hashes[CONFIG_NAME] = digest(adapter)
    # Load shared typed catalogs without validating unrelated product islands.
    repository = load_repository(root, ())
    policy_issues = validate_product(
        root, product, repository.parts, repository.interfaces, repository.projects
    )
    issues = [f"{issue.code} at {issue.location}: {issue.message}" for issue in policy_issues]
    try:
        instances = _instances(product, variant, set(repository.parts))
    except ValueError as exc:
        instances = ()
        issues.append(f"Assembly hierarchy cannot be expanded: {exc}")
    known_paths = {item.path for item in instances}
    relations = _relationships(product, variant, known_paths)
    project_ids = set(entry.project_ids) | {
        assembly.project_id for assembly in product.assemblies if assembly.project_id is not None
    }
    projects = _project_identities(root, project_ids, source_hashes)
    for project in projects:
        if project.issue:
            issues.append(f"Project {project.project_id}: {project.issue}")
    unresolved = sum(item.population == "UNRESOLVED" for item in relations)
    if unresolved:
        issues.append(f"{unresolved} authored relation(s) have unresolved references.")
    if not instances:
        issues.append("Assembly hierarchy is unavailable; inspect the product record.")
    projection_available = not issues
    system = system_view(product, variant) if projection_available else None
    schedule = harness_schedule(product, variant) if projection_available else None
    system_bytes = model_json_bytes(system) if system is not None else None
    schedule_bytes = model_json_bytes(schedule) if schedule is not None else None

    def verify_inputs() -> None:
        observed = {name: digest(repo_path(root, name)) for name in baseline}
        if adapter.is_file():
            observed[CONFIG_NAME] = digest(adapter)
        refreshed_projects = _project_identities(root, project_ids, observed)
        if observed != source_hashes or refreshed_projects != projects:
            raise ValueError("Product or project source changed during visual export")

    verify_inputs()
    target = output or Path("build/product-visual") / f"{product_id}-{variant_id}-{uuid4().hex[:8]}"
    directory = receipt_directory(root, product_id, target)
    (directory / "product.json").write_bytes(product_bytes)
    (directory / "product-index.json").write_bytes(index_bytes)
    if system_bytes is not None:
        (directory / "system.json").write_bytes(system_bytes)
    if schedule_bytes is not None:
        (directory / "harness-schedule.json").write_bytes(schedule_bytes)
    report = ProductVisualReport(
        product_id=product_id,
        product_revision=product.revision,
        variant_id=variant.id,
        variant_revision=variant.revision,
        status="CURRENT" if projection_available else "REVIEW",
        product_path=entry.path,
        product_sha256=hashlib.sha256(product_bytes).hexdigest(),
        source_hashes=source_hashes,
        projects=projects,
        instances=instances,
        relations=relations,
        harnesses=schedule.rows if schedule is not None else (),
        system_projection=system_bytes is not None,
        harness_projection=schedule_bytes is not None,
        open_items=product.blocking_issues,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_product_visual(report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {path.name: digest(path) for path in directory.iterdir()}}
    )
    write_model(directory / "product-visual.json", report)
    return report
