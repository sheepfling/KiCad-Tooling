"""Cross-record product rules over validated Pydantic records.

This module never accepts raw JSON values.  File deserialization occurs once in
the repository loader and engineering policy uses typed immutable records only.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .models import (
    AssemblyKind,
    Assurance,
    Connection,
    ConnectionKind,
    EvidenceKind,
    Harness,
    HarnessInterfaceValidationContract,
    InterfaceRecord,
    InterfacesCatalog,
    MechanicalHandoff,
    NetlistIdentityReport,
    Occurrence,
    PartRecord,
    PartsCatalog,
    PartStatus,
    PcbValidationContract,
    PolicyIssue,
    ProductIndex,
    ProductPolicyReport,
    ProductRecord,
    ProductTraceabilityValidationContract,
    ProjectConfig,
    ProjectKind,
    ProjectRecord,
    SystemWiringValidationContract,
    Terminal,
    TerminalKind,
    Variant,
)


class HasIdentifier(Protocol):
    id: str


Record = TypeVar("Record", bound=HasIdentifier)


@dataclass(frozen=True)
class ProductRepository:
    """Validated repository records indexed once for policy services."""

    products: tuple[ProductRecord, ...]
    product_project_ids: Mapping[str, tuple[str, ...]]
    parts: Mapping[str, PartRecord]
    interfaces: Mapping[str, InterfaceRecord]
    projects: Mapping[str, ProjectRecord]
    issues: tuple[PolicyIssue, ...]


def index_by_id(
    records: Iterable[Record], label: str, issues: list[PolicyIssue]
) -> dict[str, Record]:
    result: dict[str, Record] = {}
    casefolded: set[str] = set()
    for record in records:
        if record.id.casefold() in casefolded:
            issues.append(
                PolicyIssue(code="DUPLICATE_ID", location=label, message=record.id)
            )
        casefolded.add(record.id.casefold())
        result[record.id] = record
    return result


def occurrences(product: ProductRecord) -> dict[str, Occurrence]:
    """Expand a product tree without silently treating built and purchased alike."""
    assemblies = {assembly.id: assembly for assembly in product.assemblies}
    result: dict[str, Occurrence] = {}

    def visit(item: str, path: str, quantity: int, ancestry: tuple[str, ...]) -> None:
        if item in ancestry or len(ancestry) > 64:
            raise ValueError("Assembly cycle or excessive nesting")
        if len(result) >= 10_000:
            raise ValueError("Assembly exceeds the v1 limit of 10000 expanded instances")
        result[path] = Occurrence(item=item, quantity=quantity)
        assembly = assemblies.get(item)
        if assembly is not None and assembly.kind is not AssemblyKind.PURCHASED:
            for member in assembly.members:
                child = f"{path}.{member.ref}" if path else member.ref
                if child in result:
                    raise ValueError(f"Duplicate instance: {child}")
                visit(
                    member.item,
                    child,
                    quantity * member.quantity,
                    (*ancestry, item),
                )

    visit(product.root_assembly, "", 1, ())
    return result


def excluded(path: str, variant: Variant) -> bool:
    return any(path == item or path.startswith(item + ".") for item in variant.exclude)


def validate_product(
    root: Path,
    product: ProductRecord,
    parts: Mapping[str, PartRecord],
    interfaces: Mapping[str, InterfaceRecord],
    projects: Mapping[str, ProjectRecord],
) -> tuple[PolicyIssue, ...]:
    """Apply cross-record rules that cannot be expressed in one Pydantic model."""
    issues: list[PolicyIssue] = []

    def fail(code: str, location: str, message: str) -> None:
        issues.append(PolicyIssue(code=code, location=location, message=message))

    assemblies = index_by_id(product.assemblies, "assemblies", issues)
    terminals = index_by_id(product.terminals, "terminals", issues)
    connections = index_by_id(product.connections, "connections", issues)
    variants = index_by_id(product.variants, "variants", issues)
    evidence = index_by_id(product.evidence, "evidence", issues)
    harnesses = index_by_id(product.harnesses, "harnesses", issues)
    mechanical = index_by_id(product.mechanical, "mechanical", issues)

    for identifier in set(assemblies) & set(parts):
        fail("DUPLICATE_ID", identifier, "Part and assembly identities must not collide")
    if product.root_assembly not in assemblies:
        fail("ASSEMBLY_REF", "root_assembly", "Missing root assembly")

    configurations: dict[str, PcbValidationContract] = {}
    project_bindings: dict[str, ProjectRecord] = {}
    for assembly in assemblies.values():
        member_refs: set[str] = set()
        for member in assembly.members:
            if member.ref.casefold() in member_refs:
                fail("DUPLICATE_INSTANCE", assembly.id, member.ref)
            member_refs.add(member.ref.casefold())
            if member.item not in parts and member.item not in assemblies:
                fail("PART_REF", assembly.id, member.item)

        if assembly.kind is AssemblyKind.PURCHASED:
            if (
                assembly.purchase_part not in parts
                or assembly.members
                or assembly.project_id is not None
            ):
                fail(
                    "PURCHASED_ASSEMBLY",
                    assembly.id,
                    "Needs one catalog purchase_part, no expanded members or project",
                )
        elif not assembly.members or assembly.purchase_part is not None:
            fail(
                "ASSEMBLY_KIND",
                assembly.id,
                "Built/phantom assemblies need members and no purchase_part",
            )

        if assembly.project_id is not None:
            project = projects.get(assembly.project_id)
            if project is None:
                fail("PROJECT_REF", assembly.id, assembly.project_id)
                continue
            try:
                config = load_config(root, project.config)
                project_bindings[assembly.id] = project
                if (
                    assembly.kind is not AssemblyKind.BUILT
                    or config.kind is not ProjectKind.PCB
                    or not isinstance(config.validation, PcbValidationContract)
                ):
                    fail("KICAD_MEMBERS", assembly.id, "Only a built assembly may map to KiCad")
                else:
                    configurations[assembly.id] = config.validation
                    if set(config.validation.components) != {
                        member.ref for member in assembly.members
                    }:
                        fail(
                            "KICAD_MEMBERS",
                            assembly.id,
                            "Assembly members must match every KiCad component reference",
                        )
                if any(
                    member.quantity != 1 or member.item not in parts
                    for member in assembly.members
                ):
                    fail(
                        "KICAD_MEMBERS",
                        assembly.id,
                        "Each mapped symbol must identify one catalog part",
                    )
            except (OSError, ValueError) as exc:
                fail("PROJECT_REF", assembly.id, str(exc))

    # Check every assembly, including a definition accidentally disconnected from root.
    for assembly in assemblies.values():
        try:
            occurrences(product.model_copy(update={"root_assembly": assembly.id}))
        except ValueError as exc:
            fail("ASSEMBLY_GRAPH", assembly.id, str(exc))
    if issues:
        return tuple(issues)

    instances = occurrences(product)
    used_parts = {
        occurrence.item for occurrence in instances.values() if occurrence.item in parts
    }
    used_parts.update(
        assembly.purchase_part
        for assembly in assemblies.values()
        if assembly.kind is AssemblyKind.PURCHASED and assembly.purchase_part is not None
    )
    for identifier in sorted(used_parts):
        part = parts[identifier]
        if not part.revision or part.unit != "each":
            fail(
                "PART_METADATA",
                identifier,
                "Needs a revision and unit=each; fractional consumables are not supported in v1",
            )

    for variant in variants.values():
        if len(set(variant.exclude)) != len(variant.exclude):
            fail("VARIANT_REF", variant.id, "Duplicate exclusion")
        for path in variant.exclude:
            if path not in instances:
                fail("VARIANT_REF", variant.id, f"Unknown excluded instance {path}")
        for project_id in variant.board_variants:
            matching = (
                path for path, occurrence in instances.items()
                if (assembly := assemblies.get(occurrence.item)) is not None
                and assembly.project_id == project_id and not excluded(path, variant)
            )
            if not any(matching):
                fail("VARIANT_BOARD", variant.id,
                     f"Board variant maps {project_id} without an included board occurrence")

    terminal_pairs: set[tuple[str, str]] = set()
    for terminal in terminals.values():
        occurrence = instances.get(terminal.instance)
        if occurrence is None or occurrence.quantity != 1:
            fail(
                "TERMINAL_REF",
                terminal.id,
                "Endpoint needs one uniquely addressed instance",
            )
            continue
        pair = (terminal.instance, terminal.pin)
        if pair in terminal_pairs:
            fail("DUPLICATE_TERMINAL", terminal.id, str(pair))
        terminal_pairs.add(pair)
        parent, _, reference = terminal.instance.rpartition(".")
        parent_item = instances.get(parent)
        config = configurations.get(parent_item.item) if parent_item is not None else None
        project = project_bindings.get(parent_item.item) if parent_item is not None else None
        if config is not None:
            nodes = {
                node
                for values in config.nets.values()
                for node in values
            }
            if (
                terminal.kind is not TerminalKind.ELECTRICAL
                or f"{reference}.{terminal.pin}" not in nodes
            ):
                fail(
                    "KICAD_TERMINAL",
                    terminal.id,
                    "Terminal absent from the declared KiCad netlist contract",
                )
        if (terminal.interface_id is None) != (terminal.interface_pin is None):
            fail(
                "INTERFACE_BINDING",
                terminal.id,
                "Interface ID and interface pin must be present together",
            )
        elif terminal.interface_id is not None and terminal.interface_pin is not None:
            interface = interfaces.get(terminal.interface_id)
            if terminal.kind is not TerminalKind.ELECTRICAL:
                fail("INTERFACE_BINDING", terminal.id, "Bound interface terminal must be electrical")
            if project is None or terminal.interface_id not in project.interfaces:
                fail(
                    "INTERFACE_BINDING",
                    terminal.id,
                    "Terminal interface is not declared by its KiCad project",
                )
            elif interface is None:
                fail("INTERFACE_REF", terminal.id, terminal.interface_id)
            elif terminal.interface_pin not in {pin.number for pin in interface.pins}:
                fail("INTERFACE_PIN", terminal.id, terminal.interface_pin)

    claims: dict[str, Connection | Harness | MechanicalHandoff] = {
        **connections,
        **harnesses,
        **mechanical,
    }
    if len(claims) != len(connections) + len(harnesses) + len(mechanical):
        fail(
            "DUPLICATE_ID",
            product.id,
            "Claim identities must be unique across relation, harness and mechanical records",
        )

    for record in evidence.values():
        try:
            path = repo_path(root, record.path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
                fail("EVIDENCE_HASH", record.id, "Evidence content changed")
        except (OSError, ValueError) as exc:
            fail("EVIDENCE_PATH", record.id, str(exc))
        for claim in record.claims:
            if claim not in claims:
                fail("EVIDENCE_CLAIM", record.id, claim)

    required_kind = {
        Assurance.VERIFIED: EvidenceKind.TEST_REPORT,
        Assurance.MANUFACTURER_DOCUMENTED: EvidenceKind.DATASHEET,
        Assurance.OBSERVED: EvidenceKind.OBSERVATION,
    }
    all_claims: tuple[Connection | Harness | MechanicalHandoff, ...] = (
        *connections.values(),
        *harnesses.values(),
        *mechanical.values(),
    )
    for claim in all_claims:
        evidence_kinds: set[EvidenceKind] = set()
        for evidence_id in claim.evidence:
            record = evidence.get(evidence_id)
            if record is None or claim.id not in record.claims:
                fail("EVIDENCE_REF", claim.id, evidence_id)
            else:
                evidence_kinds.add(record.kind)
        required = required_kind.get(claim.assurance)
        if required is not None and required not in evidence_kinds:
            fail(
                "ASSURANCE_EVIDENCE",
                claim.id,
                f"{claim.assurance.value} requires scoped {required.value}",
            )

    allocated: set[tuple[str, str]] = set()
    used_harnesses: set[str] = set()
    endpoint_types = {
        ConnectionKind.ELECTRICAL: TerminalKind.ELECTRICAL,
        ConnectionKind.MECHANICAL: TerminalKind.MECHANICAL,
        ConnectionKind.PROTOCOL: TerminalKind.LOGICAL,
    }
    for connection in connections.values():
        from_endpoint = terminals.get(connection.from_terminal)
        to_endpoint = terminals.get(connection.to_terminal)
        if from_endpoint is None or to_endpoint is None:
            fail("ENDPOINT_REF", connection.id, "Missing terminal")
            continue
        endpoints: tuple[Terminal, Terminal] = (from_endpoint, to_endpoint)
        if connection.from_terminal == connection.to_terminal:
            fail("ENDPOINT_REF", connection.id, "Self-connection")
        expected_kind = endpoint_types.get(connection.kind)
        if expected_kind is not None and any(
            endpoint.kind is not expected_kind for endpoint in endpoints
        ):
            fail(
                "RELATION_KIND",
                connection.id,
                "Relation and endpoint semantics disagree",
            )

        harness = harnesses.get(connection.harness) if connection.harness is not None else None
        if connection.harness is not None:
            if connection.kind is not ConnectionKind.ELECTRICAL or harness is None:
                fail(
                    "HARNESS_REF",
                    connection.id,
                    "Only electrical relations may reference an existing harness",
                )
            else:
                used_harnesses.add(harness.id)
                if not any(endpoint.interface_id is not None for endpoint in endpoints):
                    fail(
                        "HARNESS_INTERFACE",
                        connection.id,
                        "Harness conductor needs at least one controlled interface endpoint",
                    )

        if len(set(connection.variants)) != len(connection.variants):
            fail("VARIANT_REF", connection.id, "Duplicate variant")
        for variant_id in connection.variants:
            variant = variants.get(variant_id)
            if variant is None:
                fail("VARIANT_REF", connection.id, variant_id)
                continue
            for endpoint in endpoints:
                if excluded(endpoint.instance, variant):
                    fail(
                        "VARIANT_ENDPOINT",
                        connection.id,
                        f"{variant_id} excludes {endpoint.instance}",
                    )
                allocation = (variant_id, endpoint.id)
                if connection.kind is ConnectionKind.ELECTRICAL and endpoint.exclusive:
                    if allocation in allocated:
                        fail(
                            "TERMINAL_ALLOCATION",
                            connection.id,
                            f"{variant_id}: {endpoint.id} already allocated",
                        )
                    allocated.add(allocation)
            if harness is not None and excluded(harness.instance, variant):
                fail("VARIANT_HARNESS", connection.id, variant_id)

    for harness in harnesses.values():
        occurrence = instances.get(harness.instance)
        if occurrence is None or occurrence.quantity != 1:
            fail(
                "HARNESS_INSTANCE",
                harness.id,
                "Missing or non-unique harness instance",
            )
        if harness.id not in used_harnesses:
            fail("HARNESS_UNUSED", harness.id, "No electrical conductor references this harness")

    for handoff in mechanical.values():
        for instance in handoff.instances:
            if instance not in instances:
                fail("MECHANICAL_INSTANCE", handoff.id, instance)
        try:
            if not repo_path(root, handoff.drawing).is_file():
                fail("MECHANICAL_DRAWING", handoff.id, "Missing drawing/reference")
        except ValueError as exc:
            fail("MECHANICAL_DRAWING", handoff.id, str(exc))
    return tuple(issues)


def load_repository(
    root: Path, selected_project_ids: tuple[str, ...] | None = None
) -> ProductRepository:
    """Load global catalogs and only products relevant to an optional project scope."""
    root = root.resolve()
    selected = None if selected_project_ids is None else frozenset(selected_project_ids)
    issues: list[PolicyIssue] = []
    products: list[ProductRecord] = []
    product_project_ids: dict[str, tuple[str, ...]] = {}
    parts: Mapping[str, PartRecord] = {}
    interfaces: Mapping[str, InterfaceRecord] = {}
    projects: Mapping[str, ProjectRecord] = {}
    try:
        index = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
        registry = load_registry(root)
        parts_catalog = read_model(repo_path(root, registry.catalogs.parts), PartsCatalog)
        interfaces_catalog = read_model(
            repo_path(root, registry.catalogs.interfaces), InterfacesCatalog
        )
        parts = index_by_id(parts_catalog.parts, "parts", issues)
        interfaces = index_by_id(interfaces_catalog.interfaces, "interfaces", issues)
        projects = index_by_id(registry.projects, "projects", issues)
        if selected is not None and (unknown := selected - projects.keys()):
            issues.append(
                PolicyIssue(
                    code="PROJECT_SELECTION",
                    location="catalog/projects.json",
                    message=f"Unknown selected project IDs: {sorted(unknown)}",
                )
            )
        relevant_entries = (
            index.products if selected is None else tuple(
                entry for entry in index.products
                if not selected.isdisjoint(entry.project_ids)
            )
        )
        relevant_project_ids = (
            None if selected is None else selected | {
                project_id
                for entry in relevant_entries
                for project_id in entry.project_ids
            }
        )
        product_view_projects_by_product: dict[
            str, list[tuple[str, ProductTraceabilityValidationContract]]
        ] = {}
        for project in registry.projects:
            # A selected lane needs view contracts from its dependent products,
            # but must not load contracts belonging to unrelated project islands.
            # Its own board contract is checked by the selected registry lane.
            if relevant_project_ids is not None and (
                project.id not in relevant_project_ids
                or project.kind not in {ProjectKind.SYSTEM_WIRING, ProjectKind.HARNESS_INTERFACE}
            ):
                continue
            config = load_config(root, project.config)
            if isinstance(
                config.validation,
                (SystemWiringValidationContract, HarnessInterfaceValidationContract),
            ):
                product_view_projects_by_product.setdefault(
                    config.validation.product_id, []
                ).append((project.id, config.validation))

        declared: set[str] = set()
        for entry in index.products:
            product_project_ids[entry.id] = entry.project_ids
            path = repo_path(root, entry.path)
            if (
                not (
                    entry.path.startswith("products/")
                    or entry.path.startswith("examples/products/")
                )
                or path.suffix != ".json"
                or entry.path in declared
            ):
                raise ValueError(
                    "Products need unique products/*.json paths "
                    "(or examples/products/*.json in the template)"
                )
            declared.add(entry.path)
            if len(set(entry.project_ids)) != len(entry.project_ids):
                issues.append(
                    PolicyIssue(
                        code="PRODUCT_PROJECTS",
                        location=entry.path,
                        message="Product index has duplicate project IDs",
                    )
                )
            if selected is not None and selected.isdisjoint(entry.project_ids):
                continue
            product = read_model(path, ProductRecord)
            if product.id != entry.id:
                issues.append(
                    PolicyIssue(
                        code="PRODUCT_ID",
                        location=entry.path,
                        message="Index and product identity differ",
                    )
                )
            mapped_projects = {
                assembly.project_id
                for assembly in product.assemblies
                if assembly.project_id is not None
            }
            wiring_projects = product_view_projects_by_product.get(product.id, [])
            associated_projects = mapped_projects | {
                project_id for project_id, _ in wiring_projects
            }
            if associated_projects != set(entry.project_ids):
                issues.append(
                    PolicyIssue(
                        code="PRODUCT_PROJECTS",
                        location=entry.path,
                        message=(
                            "Product index project_ids must exactly match its "
                            "KiCad board-assembly, system-wiring, and harness-interface project IDs"
                        ),
                    )
                )
            product_issues = validate_product(root, product, parts, interfaces, projects)
            for project_id, validation in wiring_projects:
                issue_code = (
                    "SYSTEM_WIRING_CONTRACT"
                    if isinstance(validation, SystemWiringValidationContract)
                    else "HARNESS_INTERFACE_CONTRACT"
                )
                try:
                    if isinstance(validation, SystemWiringValidationContract):
                        validate_system_wiring_contract(product, validation)
                    elif isinstance(validation, HarnessInterfaceValidationContract):
                        validate_harness_interface_contract(product, validation)
                    else:
                        raise TypeError("Unsupported product traceability contract")
                except ValueError as exc:
                    product_issues = (
                        *product_issues,
                        PolicyIssue(
                            code=issue_code,
                            location=project_id,
                            message=str(exc),
                        ),
                    )
            issues.extend(product_issues)
            if not product_issues:
                products.append(product)

        indexed_product_ids = {entry.id for entry in index.products}
        for product_id, project_items in product_view_projects_by_product.items():
            if product_id not in indexed_product_ids:
                issues.append(
                    PolicyIssue(
                        code="PRODUCT_VIEW_PRODUCT",
                        location=",".join(sorted(project_id for project_id, _ in project_items)),
                        message=f"Product-view project references missing product {product_id}",
                    )
                )

        if selected is None:
            found = {
                path.relative_to(root).as_posix()
                for product_root in ("products", "examples/products")
                if product_root == "products" or any(name.startswith("examples/") for name in declared)
                for path in (root / product_root).glob("*/product.json")
                if (root / product_root).is_dir()
            }
            if declared != found:
                issues.append(
                    PolicyIssue(
                        code="PRODUCT_DISCOVERY",
                        location="products",
                        message=f"Unregistered or missing products: {sorted(declared ^ found)}",
                    )
                )
    except (OSError, ValueError) as exc:
        issues.append(
            PolicyIssue(code="PRODUCT_LOAD", location="repository", message=str(exc))
        )
    return ProductRepository(
        products=tuple(products),
        product_project_ids=product_project_ids,
        parts=parts,
        interfaces=interfaces,
        projects=projects,
        issues=tuple(issues),
    )


def check(
    root: Path,
    release: bool = False,
    selected_project_ids: tuple[str, ...] | None = None,
) -> ProductPolicyReport:
    repository = load_repository(root, selected_project_ids)
    issues = list(repository.issues)
    if release:
        issues.append(
            PolicyIssue(
                code="RELEASE_NOT_IMPLEMENTED",
                location="repository",
                message=(
                    "This lane produces engineering review evidence only; it cannot "
                    "authorize a build or release"
                ),
            )
        )
    open_items = {
        product.id: (
            *product.blocking_issues,
            *(item for handoff in product.mechanical for item in handoff.open_items),
        )
        for product in repository.products
    }
    return ProductPolicyReport(
        status="FAIL" if issues else "PASS",
        products=tuple(product.id for product in repository.products),
        open_items=open_items,
        issues=tuple(issues),
    )


def validate_system_wiring_contract(
    product: ProductRecord, validation: SystemWiringValidationContract
) -> None:
    """Fail unless a system diagram declares complete typed product traceability.

    The drawing is a review view. Product records remain authoritative for relation
    kinds, terminals, harnesses, and mechanical handoffs, so a visual line cannot
    silently turn a functional or mechanical relationship into electrical truth.
    """
    connections = {connection.id: connection for connection in product.connections}
    terminals = {terminal.id for terminal in product.terminals}
    harnesses = {harness.id for harness in product.harnesses}
    handoffs = {handoff.id for handoff in product.mechanical}
    declared_connections = set(validation.connection_ids)
    if declared_connections != set(connections):
        raise ValueError(
            "System wiring connection coverage differs; "
            f"missing={sorted(set(connections) - declared_connections)}, "
            f"extra={sorted(declared_connections - set(connections))}"
        )
    endpoints = {
        terminal_id
        for connection in connections.values()
        for terminal_id in (connection.from_terminal, connection.to_terminal)
    }
    if set(validation.terminal_ids) != endpoints or not endpoints <= terminals:
        raise ValueError("System wiring terminal coverage differs from connection endpoints")
    if set(validation.harness_ids) != harnesses:
        raise ValueError("System wiring harness coverage differs from the product contract")
    if set(validation.mechanical_handoff_ids) != handoffs:
        raise ValueError(
            "System wiring mechanical-handoff coverage differs from the product contract"
        )


def validate_harness_interface_contract(
    product: ProductRecord, validation: HarnessInterfaceValidationContract
) -> None:
    """Fail unless a harness view owns exactly its declared electrical conductors."""
    connections = {connection.id: connection for connection in product.connections}
    terminals = {terminal.id for terminal in product.terminals}
    harnesses = {harness.id for harness in product.harnesses}
    declared_harnesses = set(validation.harness_ids)
    if not declared_harnesses <= set(harnesses):
        raise ValueError("Harness interface references an unknown product harness")
    expected_connections = {
        connection.id
        for connection in connections.values()
        if connection.kind is ConnectionKind.ELECTRICAL
        and connection.harness in declared_harnesses
    }
    declared_connections = set(validation.connection_ids)
    if declared_connections != expected_connections:
        raise ValueError(
            "Harness interface conductor coverage differs; "
            f"missing={sorted(expected_connections - declared_connections)}, "
            f"extra={sorted(declared_connections - expected_connections)}"
        )
    endpoints = {
        terminal_id
        for connection_id in declared_connections
        for terminal_id in (
            connections[connection_id].from_terminal,
            connections[connection_id].to_terminal,
        )
    }
    if set(validation.terminal_ids) != endpoints or not endpoints <= terminals:
        raise ValueError("Harness interface terminal coverage differs from conductor endpoints")


def check_system_wiring_contract(root: Path, config: ProjectConfig) -> None:
    """Resolve a system-wiring project to its one typed product contract."""
    validation = config.validation
    if not isinstance(validation, SystemWiringValidationContract):
        raise TypeError("System wiring check requires a system_wiring configuration")
    repository = load_repository(root, (config.project_id,))
    if repository.issues:
        raise ValueError(f"Product policy failed: {repository.issues}")
    products = tuple(
        product for product in repository.products if product.id == validation.product_id
    )
    if len(products) != 1:
        raise ValueError(
            f"System wiring view must reference exactly one indexed product: {validation.product_id}"
        )
    validate_system_wiring_contract(products[0], validation)


def check_harness_interface_contract(root: Path, config: ProjectConfig) -> None:
    """Resolve a harness-interface project to its one typed product contract."""
    validation = config.validation
    if not isinstance(validation, HarnessInterfaceValidationContract):
        raise TypeError("Harness interface check requires a harness_interface configuration")
    repository = load_repository(root, (config.project_id,))
    if repository.issues:
        raise ValueError(f"Product policy failed: {repository.issues}")
    products = tuple(
        product for product in repository.products if product.id == validation.product_id
    )
    if len(products) != 1:
        raise ValueError(
            f"Harness interface must reference exactly one indexed product: {validation.product_id}"
        )
    validate_harness_interface_contract(products[0], validation)


def check_project_netlist(
    root: Path, project_id: str, path: Path
) -> NetlistIdentityReport:
    """Verify actual exported KiCad PART_ID fields against typed product records."""
    repository = load_repository(root, (project_id,))
    if repository.issues:
        raise ValueError(f"Product policy failed: {repository.issues}")
    bindings = tuple(
        assembly
        for product in repository.products
        for assembly in product.assemblies
        if assembly.project_id == project_id
    )
    project = repository.projects[project_id]
    if not bindings and not project.component_identity.required:
        return NetlistIdentityReport(status="NOT_APPLICABLE", reason="Project does not require component identity")
    tree = ET.parse(path).getroot()
    components: dict[str, Mapping[str, str]] = {}
    for component in tree.findall("./components/comp"):
        reference = component.attrib["ref"]
        if reference in components:
            raise ValueError(f"Duplicate KiCad reference {reference}")
        fields = tuple(component.findall("./fields/field"))
        names = tuple(field.attrib["name"] for field in fields)
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate KiCad fields at {reference}")
        components[reference] = {
            field.attrib["name"]: field.text or ""
            for field in fields
        }
    if project.component_identity.required:
        from .discovery import load_config
        from .models import PcbValidationContract, SchematicValidationContract

        config = load_config(root, project.config)
        if isinstance(config.validation, (PcbValidationContract, SchematicValidationContract)):
            expected_parts = {ref: component.part_id for ref, component in config.validation.components.items()}
            if set(components) != set(expected_parts):
                raise ValueError("KiCad and project component inventories differ")
            for reference, identifier in expected_parts.items():
                if identifier is None or components[reference].get("PART_ID") != identifier:
                    raise ValueError(f"KiCad PART_ID mismatch: {reference}, expected {identifier}")
        actual_ids = {fields.get("PART_ID") for fields in components.values()}
        if not components or actual_ids != set(project.component_identity.part_ids):
            raise ValueError("KiCad PART_ID inventory differs from the standalone project")
        for reference, fields in components.items():
            part = repository.parts.get(fields.get("PART_ID", ""))
            if part is None:
                raise ValueError(f"Unknown KiCad PART_ID at {reference}")
            if part.status is PartStatus.APPROVED and (
                fields.get("Manufacturer") != part.manufacturer or fields.get("MPN") != part.mpn
            ):
                raise ValueError(f"KiCad Manufacturer/MPN mismatch: {reference}")
    for assembly in bindings:
        expected = {member.ref: member.item for member in assembly.members}
        if set(components) != set(expected):
            raise ValueError("KiCad and product instance inventories differ")
        for reference, identifier in expected.items():
            if components[reference].get("PART_ID") != identifier:
                raise ValueError(
                    f"KiCad PART_ID mismatch: {reference}, expected {identifier}"
                )
            part = repository.parts[identifier]
            if part.status is PartStatus.APPROVED:
                for field_name, expected_value in (
                    ("Manufacturer", part.manufacturer),
                    ("MPN", part.mpn),
                ):
                    if components[reference].get(field_name) != expected_value:
                        raise ValueError(f"KiCad {field_name} mismatch: {reference}")
    return NetlistIdentityReport(
        status="PASS",
        assemblies=tuple(sorted(assembly.id for assembly in bindings)),
        components=len(components),
    )
