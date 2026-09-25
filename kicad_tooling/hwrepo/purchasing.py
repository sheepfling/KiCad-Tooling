"""Read native components and prepare an explicit, reviewable purchasing plan."""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from .models import (
    PartRecord,
    PartsCatalog,
    PartStatus,
    PurchasingComponent,
    PurchasingFinding,
    PurchasingLine,
    PurchasingPlan,
    PurchasingPreferences,
)

_PLACEHOLDER = re.compile(
    r"(?:^|[^a-z0-9])(unspecified|unknown|training|placeholder|synthetic|example|generic|tbd|todo|none|n/a)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)


def _single_text(component: ET.Element, tag: str) -> str:
    elements = component.findall(tag)
    if len(elements) > 1:
        raise ValueError(f"Repeated {tag} for component {component.get('ref')}")
    if elements and len(elements[0]):
        raise ValueError(f"Nested text in {tag} for component {component.get('ref')}")
    return (elements[0].text or "") if elements else ""


def _named_entries(elements: list[ET.Element], reference: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for element in elements:
        name = element.get("name")
        if name is None or not name.strip() or name in entries:
            raise ValueError(f"Missing or repeated {element.tag} name at {reference}")
        if len(element):
            raise ValueError(f"Nested {element.tag} data at {reference}")
        if "value" in element.attrib and element.text and element.text.strip():
            raise ValueError(f"Ambiguous {element.tag} value at {reference}")
        entries[name] = element.get("value", element.text or "")
    return entries


def _excluded(properties: dict[str, str], name: str, reference: str) -> bool:
    # KiCad emits these direct properties only when true; variants are separate.
    if name not in properties:
        return False
    if properties[name].strip().casefold() not in {"", "true", "yes", "1"}:
        raise ValueError(f"Ambiguous native {name} property at {reference}")
    return True


def read_components(netlist_path: Path) -> tuple[PurchasingComponent, ...]:
    """Adapt an unfiltered KiCad XML netlist, rejecting ambiguous component data."""
    try:
        root = ET.parse(netlist_path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"Malformed native netlist: {error}") from error
    sections = root.findall("components")
    if root.tag != "export" or len(sections) != 1 or not len(sections[0]):
        raise ValueError("Native netlist requires exactly one nonempty components section")
    components: list[PurchasingComponent] = []
    references: set[str] = set()
    for element in sections[0]:
        reference = element.get("ref")
        if element.tag != "comp" or reference is None or reference in references:
            raise ValueError("Native netlist has an invalid or repeated component reference")
        references.add(reference)
        if len(element.findall("fields")) > 1:
            raise ValueError(f"Repeated fields section at {reference}")
        fields = _named_entries(element.findall("./fields/field"), reference)
        properties = _named_entries(element.findall("property"), reference)
        components.append(PurchasingComponent(
            reference=reference, value=_single_text(element, "value"),
            footprint=_single_text(element, "footprint"), part_id=fields.get("PART_ID"),
            dnp=_excluded(properties, "dnp", reference),
            exclude_from_bom=_excluded(properties, "exclude_from_bom", reference),
        ))
    return tuple(sorted(components, key=lambda component: component.reference))


def _finding(code: str, references: tuple[str, ...], message: str,
             action: str) -> PurchasingFinding:
    return PurchasingFinding(code=code, references=references, message=message, action=action)


def _catalog_findings(parts: PartsCatalog, selected: set[str]) -> tuple[PurchasingFinding, ...]:
    findings: list[PurchasingFinding] = []
    ids = Counter(part.id for part in parts.parts)
    identities: dict[tuple[str, str], list[str]] = defaultdict(list)
    for part in parts.parts:
        if part.id in selected:
            identities[(part.manufacturer.casefold(), part.mpn)].append(part.id)
    for identifier, count in sorted(ids.items()):
        if count > 1:
            findings.append(_finding("DUPLICATE_PART_ID", (),
                f"Catalog repeats PART_ID {identifier}.",
                "Give each catalog part one unambiguous identity and revision."))
    for _, identifiers in sorted(identities.items()):
        if len(set(identifiers)) > 1:
            findings.append(_finding("DUPLICATE_PART_IDENTITY", (),
                f"Catalog IDs {', '.join(sorted(identifiers))} share a manufacturer and MPN.",
                "Review the duplicate catalog records before choosing an ordering identity."))
    return tuple(findings)


def _preference_findings(preferences: PurchasingPreferences, parts: dict[str, PartRecord],
                         allowed: set[str]) -> tuple[PurchasingFinding, ...]:
    findings: list[PurchasingFinding] = []
    skus: dict[str, list[str]] = defaultdict(list)
    for identifier, sku in sorted(preferences.digikey_skus.items()):
        if identifier not in parts or identifier not in allowed:
            findings.append(_finding("UNKNOWN_SKU_OVERRIDE", (),
                f"DigiKey override {identifier} is unknown or outside this project's part scope.",
                "Remove the override or review and declare its catalog part for this project."))
        if _PLACEHOLDER.search(sku):
            findings.append(_finding("PLACEHOLDER_SKU", (),
                f"DigiKey override {identifier} contains a placeholder supplier number.",
                "Record the reviewed exact DigiKey part number or remove the override."))
        skus[sku].append(identifier)
    for sku, identifiers in sorted(skus.items()):
        if len(identifiers) > 1:
            findings.append(_finding("CONFLICTING_SKU", (),
                f"DigiKey number {sku!r} is assigned to several PART_IDs: {', '.join(identifiers)}.",
                "Check supplier identity and keep an unambiguous mapping for each ordered part."))
    return tuple(findings)


def _component_findings(component: PurchasingComponent, parts: dict[str, PartRecord],
                        allowed: set[str]) -> tuple[PurchasingFinding, ...]:
    findings: list[PurchasingFinding] = []
    references = (component.reference,)
    if not component.footprint.strip():
        findings.append(_finding("MISSING_FOOTPRINT", references,
            "Fitted component has no footprint.", "Assign and review its physical footprint in KiCad."))
    if not component.value.strip():
        findings.append(_finding("MISSING_VALUE", references,
            "Fitted component has no value.", "Enter its reviewed value in the schematic."))
    identifier = component.part_id
    if identifier is None or not identifier.strip():
        findings.append(_finding("MISSING_PART_ID", references,
            "Fitted component has no PART_ID.",
            "Choose a reviewed catalog part and assign its PART_ID in the schematic."))
    elif identifier not in parts:
        findings.append(_finding("UNKNOWN_PART_ID", references,
            f"PART_ID {identifier!r} is not in the parts catalog.",
            "Add the reviewed manufacturer part to the catalog or correct the schematic field."))
    elif identifier not in allowed:
        findings.append(_finding("UNDECLARED_PART_ID", references,
            f"PART_ID {identifier} is outside this project's declared part scope.",
            "Review the part and declare it in project.json component_identity.part_ids."))
    else:
        part = parts[identifier]
        if part.status != PartStatus.APPROVED:
            findings.append(_finding("UNAPPROVED_PART", references,
                f"PART_ID {identifier} is a training or unapproved catalog part.",
                "Select an independently reviewed real part; do not approve a training placeholder."))
        if _PLACEHOLDER.search(part.manufacturer) or _PLACEHOLDER.search(part.mpn):
            findings.append(_finding("PLACEHOLDER_PART", references,
                f"PART_ID {identifier} has a placeholder manufacturer or MPN.",
                "Record the exact manufacturer and manufacturer part number from reviewed evidence."))
    return tuple(findings)


def plan(components: tuple[PurchasingComponent, ...], parts: PartsCatalog,
         preferences: PurchasingPreferences, allowed_part_ids: tuple[str, ...]) -> PurchasingPlan:
    """Resolve declared parts and quantities without choosing parts or alternates."""
    components = tuple(sorted(components, key=lambda component: component.reference))
    selected = {component.part_id for component in components
                if component.part_id is not None and not component.dnp and not component.exclude_from_bom}
    findings = list(_catalog_findings(parts, selected))
    catalog = {part.id: part for part in parts.parts}
    allowed = set(allowed_part_ids)
    findings.extend(_preference_findings(preferences, catalog, allowed))
    counts = Counter(component.reference for component in components)
    for reference, count in sorted(counts.items()):
        if count > 1:
            findings.append(_finding("DUPLICATE_REFERENCE", (reference,),
                "Component reference appears more than once.", "Repair duplicate schematic references."))
    excluded = tuple(component.reference for component in components
                     if component.dnp or component.exclude_from_bom)
    fitted = tuple(component for component in components
                   if not component.dnp and not component.exclude_from_bom)
    if not fitted:
        findings.append(_finding("NO_FITTED_COMPONENTS", (), "No fitted components are available.",
            "Review schematic BOM exclusions and choose the intended assembly variant."))
    groups: dict[str, list[PurchasingComponent]] = defaultdict(list)
    for component in fitted:
        component_findings = _component_findings(component, catalog, allowed)
        findings.extend(component_findings)
        if not component_findings and component.part_id is not None:
            groups[component.part_id].append(component)
    lines: list[PurchasingLine] = []
    for identifier, group in sorted(groups.items()):
        references = tuple(component.reference for component in group)
        if len({(component.footprint, component.value) for component in group}) > 1:
            findings.append(_finding("INCONSISTENT_PART_USE", references,
                f"PART_ID {identifier} is used with different values or footprints.",
                "Review each use of this part; reconcile values and physical footprints explicitly."))
            continue
        part = catalog[identifier]
        required = len(group) * preferences.boards
        spares = max((required * preferences.spare_percent + 99) // 100, preferences.spare_minimum)
        sku = preferences.digikey_skus.get(identifier)
        order_number = sku if sku is not None else part.mpn
        lines.append(PurchasingLine(
            part_id=identifier, revision=part.revision, manufacturer=part.manufacturer,
            mpn=part.mpn, footprint=group[0].footprint, references=references,
            per_board=len(group), required=required, spares=spares, quantity=required + spares,
            order_number=order_number, order_number_kind="DigiKey" if sku is not None else "MPN",
            search_url="https://www.digikey.com/en/products?keywords=" + quote(order_number if sku is not None else f"{part.manufacturer} {part.mpn}", safe=""),
        ))
    order_numbers: dict[str, list[PurchasingLine]] = defaultdict(list)
    for line in lines:
        order_numbers[line.order_number].append(line)
    for number, matches in sorted(order_numbers.items()):
        if len(matches) > 1:
            findings.append(_finding("ORDER_NUMBER_COLLISION",
                tuple(reference for line in matches for reference in line.references),
                f"Order number {number!r} identifies more than one part group.",
                "Review manufacturer identity and assign distinct exact DigiKey numbers before export."))
    return PurchasingPlan(
        status="NEEDS_PARTS" if findings else "READY_FOR_ORDER_REVIEW", preferences=preferences,
        components=components, lines=tuple(lines), findings=tuple(findings), excluded_references=excluded,
    )


def _safe_cell(value: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("CSV text contains a control character; correct the source metadata")
    if value.lstrip().startswith(("=", "+", "-", "@")):
        raise ValueError("CSV text could be a spreadsheet formula; correct the source metadata")
    return value


def _csv_text(rows: tuple[tuple[str, ...], ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for row in rows:
        writer.writerow(tuple(_safe_cell(value) for value in row))
    return stream.getvalue()


def write_csvs(output_dir: Path, purchase_plan: PurchasingPlan) -> tuple[str, ...]:
    """Write fresh CSVs after all cells validate; never create a partial order file."""
    components = {component.reference: component for component in purchase_plan.components}
    covered: set[str] = set()
    review_rows: list[tuple[str, ...]] = [(
        "Reference", "Value", "Footprint", "PART_ID", "Manufacturer", "MPN", "DNP",
        "Exclude from BOM", "Per Board", "Required", "Spares", "Order Quantity", "Issue Codes",
    )]
    for line in purchase_plan.lines:
        covered.update(line.references)
        issue_codes = "; ".join(finding.code for finding in purchase_plan.findings
                               if not finding.references or set(line.references) & set(finding.references))
        review_rows.append((
            "; ".join(line.references), components[line.references[0]].value,
            line.footprint, line.part_id, line.manufacturer, line.mpn, "no", "no",
            str(line.per_board), str(line.required), str(line.spares), str(line.quantity), issue_codes,
        ))
    for component in purchase_plan.components:
        if component.reference in covered:
            continue
        issue_codes = "; ".join(finding.code for finding in purchase_plan.findings
                               if not finding.references or component.reference in finding.references)
        review_rows.append((
            component.reference, component.value, component.footprint, component.part_id or "", "", "",
            "yes" if component.dnp else "no", "yes" if component.exclude_from_bom else "no",
            "", "", "", "", issue_codes,
        ))
    contents = {"bom.csv": _csv_text(tuple(review_rows))}
    if purchase_plan.status == "READY_FOR_ORDER_REVIEW":
        if purchase_plan.findings or not purchase_plan.lines:
            raise ValueError("Ready purchasing plan cannot have findings or no order lines")
        order_rows = (("Part Number", "Quantity", "Customer Reference"),) + tuple(
            (line.order_number, str(line.quantity), line.part_id) for line in purchase_plan.lines
        )
        contents["digikey.csv"] = _csv_text(order_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in contents:
        if (output_dir / name).exists() or (output_dir / name).is_symlink():
            raise ValueError(f"Refusing to replace existing purchasing output: {name}")
    written: list[Path] = []
    try:
        for name, content in contents.items():
            path = output_dir / name
            with path.open("x", newline="", encoding="utf-8") as stream:
                written.append(path)
                stream.write(content)
    except OSError:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return tuple(contents)
