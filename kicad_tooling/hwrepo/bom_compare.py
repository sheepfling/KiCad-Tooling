"""Source-bound comparison of two saved parts planning receipts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from uuid import uuid4

from .bom_compare_models import (
    BomComparisonReport,
    BomQuantityDifference,
    BomQuantityState,
    BomReferenceDifference,
    BomReferenceState,
    Change,
)
from .contract_coach import receipt_directory
from .contracts import write_model
from .evidence import digest
from .models import PurchasingPlan
from .parts_receipts import read_parts_receipt
from .selection import resolve_project


def _references(plan: PurchasingPlan) -> dict[str, BomReferenceState]:
    line_by_reference: dict[str, str] = {}
    revision_by_reference: dict[str, str] = {}
    for line in plan.lines:
        for reference in line.references:
            if reference in line_by_reference:
                raise ValueError(f"Parts plan repeats fitted reference {reference}")
            line_by_reference[reference] = line.part_id
            revision_by_reference[reference] = line.revision
    result: dict[str, BomReferenceState] = {}
    for component in plan.components:
        reference = component.reference
        if reference in result:
            raise ValueError(f"Parts plan repeats component reference {reference}")
        issue_codes = tuple(
            sorted({finding.code for finding in plan.findings if reference in finding.references})
        )
        population = (
            "DNP"
            if component.dnp
            else "EXCLUDED"
            if component.exclude_from_bom
            else "FITTED"
            if reference in line_by_reference
            else "UNRESOLVED"
        )
        result[reference] = BomReferenceState(
            part_id=component.part_id,
            revision=revision_by_reference.get(reference),
            population=population,
            value=component.value,
            footprint=component.footprint,
            issue_codes=issue_codes,
        )
    if set(line_by_reference) - set(result):
        raise ValueError("Parts plan has a line for an unknown component reference")
    return result


def _quantities(plan: PurchasingPlan) -> dict[tuple[str, str], BomQuantityState]:
    result: dict[tuple[str, str], BomQuantityState] = {}
    for line in plan.lines:
        key = (line.part_id, line.revision)
        if key in result:
            raise ValueError(f"Parts plan repeats quantity line for {key}")
        result[key] = BomQuantityState(
            references=line.references,
            per_board=line.per_board,
            required=line.required,
            spares=line.spares,
            quantity=line.quantity,
        )
    return result


def _change(before: object | None, after: object | None) -> Change:
    return (
        "ADDED"
        if before is None
        else "REMOVED"
        if after is None
        else "UNCHANGED"
        if before == after
        else "CHANGED"
    )


def _compare(
    before: PurchasingPlan,
    after: PurchasingPlan,
) -> tuple[tuple[BomReferenceDifference, ...], tuple[BomQuantityDifference, ...]]:
    old_refs, new_refs = _references(before), _references(after)
    references = tuple(
        BomReferenceDifference(
            reference=name,
            change=_change(old_refs.get(name), new_refs.get(name)),
            before=old_refs.get(name),
            after=new_refs.get(name),
        )
        for name in sorted(old_refs.keys() | new_refs.keys())
    )
    old_lines, new_lines = _quantities(before), _quantities(after)
    quantities = tuple(
        BomQuantityDifference(
            part_id=key[0],
            revision=key[1],
            change=_change(old_lines.get(key), new_lines.get(key)),
            before=old_lines.get(key),
            after=new_lines.get(key),
        )
        for key in sorted(old_lines.keys() | new_lines.keys())
    )
    return references, quantities


def _state(value: BomReferenceState | None) -> str:
    if value is None:
        return "—"
    identity = f"{value.part_id or 'unresolved'} @ {value.revision or '?'}"
    detail = f"{value.population}; {identity}; {value.value}; {value.footprint}"
    return detail + (f"; issues: {', '.join(value.issue_codes)}" if value.issue_codes else "")


def _reference_table(title: str, items: tuple[BomReferenceDifference, ...]) -> str:
    rows = "".join(
        f"<tr class='{escape(item.change.lower())}'><th>{escape(item.reference)}</th>"
        f"<td>{escape(item.change)}</td><td>{escape(_state(item.before))}</td>"
        f"<td>{escape(_state(item.after))}</td></tr>"
        for item in items
    )
    return (
        f'<section><h2>{escape(title)} · {len(items)}</h2><div class="scroll"><table>'
        "<thead><tr><th>Reference</th><th>Change</th><th>Before</th><th>After</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div></section>"
    )


def _quantity(value: BomQuantityState | None) -> str:
    if value is None:
        return "—"
    return (
        f"{value.per_board} per board · {value.required} required · "
        f"{value.spares} spares · {value.quantity} total"
    )


def _html(report: BomComparisonReport) -> str:
    changed = sum(item.change != "UNCHANGED" for item in report.references)
    unresolved = tuple(
        item
        for item in report.references
        if any(
            state is not None and state.population == "UNRESOLVED"
            for state in (item.before, item.after)
        )
    )
    excluded = tuple(
        item
        for item in report.references
        if item not in unresolved
        and any(
            state is not None and state.population in {"DNP", "EXCLUDED"}
            for state in (item.before, item.after)
        )
    )
    fitted = tuple(
        item for item in report.references if item not in unresolved and item not in excluded
    )
    reference_tables = "".join(
        (
            _reference_table("Fitted references", fitted),
            _reference_table("Excluded or DNP references", excluded),
            _reference_table("Unresolved references", unresolved),
        )
    )
    quantity_rows = "".join(
        f"<tr><th>{escape(item.part_id)} @ {escape(item.revision)}</th>"
        f"<td>{escape(item.change)}</td>"
        f"<td>{escape(_quantity(item.before))}</td>"
        f"<td>{escape(_quantity(item.after))}</td>"
        f"<td>{escape(', '.join(item.before.references) if item.before else '—')}</td>"
        f"<td>{escape(', '.join(item.after.references) if item.after else '—')}</td></tr>"
        for item in report.quantities
    )
    source_rows = "".join(
        f"<tr><th>{escape(name)}</th>"
        f"<td>{report.before_source_hashes.get(name, '—')}</td>"
        f"<td>{report.after_source_hashes.get(name, '—')}</td></tr>"
        for name in sorted(report.before_source_hashes.keys() | report.after_source_hashes.keys())
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>BOM comparison</title>
<style>body{{font:15px system-ui;color:#24344b;background:#f5f7fa;margin:0;padding:2rem}}
main{{max-width:1200px;margin:auto}}section{{background:white;padding:1.3rem;margin:1rem 0;border-radius:12px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:.6rem;text-align:left;border-bottom:1px solid #dce3ec}}
td{{overflow-wrap:anywhere}}.changed{{background:#fff7e4}}.added{{background:#e7f6ec}}
.removed{{background:#fff0ee}}.muted{{color:#59697f}}.scroll{{overflow:auto}}</style><main>
<h1>BOM comparison · {escape(report.project_id)}</h1>
<p>{changed} changed references of {len(report.references)}. This comparison is for review only.</p>
<p><a href="comparison.json">Download structured comparison</a></p>
<section><h2>Selected receipts</h2><p>Before: {escape(report.before_receipt)}
({escape(report.before_status)}, SHA-256 {report.before_report_sha256})</p>
<p>After: {escape(report.after_receipt)} ({escape(report.after_status)},
SHA-256 {report.after_report_sha256})</p>
<p>Source paths: {report.source_scope}. Variant identity: not recorded in parts receipts.</p></section>
<section><h2>Source hashes</h2><div class="scroll"><table><thead><tr>
<th>Path</th><th>Before SHA-256</th><th>After SHA-256</th></tr></thead>
<tbody>{source_rows}</tbody></table></div></section>
{reference_tables}
<section><h2>Grouped quantities</h2><div class="scroll"><table><thead><tr>
<th>Part @ revision</th><th>Change</th><th>Before quantity</th><th>After quantity</th>
<th>Before refs</th><th>After refs</th></tr></thead><tbody>{quantity_rows}</tbody></table></div></section>
</main></html>"""


def compare_bom(
    root: Path, project_id: str, before: Path, after: Path, output: Path | None = None
) -> BomComparisonReport:
    """Compare saved plans without rerunning capture or asserting current source."""
    root = root.resolve()
    resolve_project(root, project_id)
    old_path, old, old_hash = read_parts_receipt(root, before, project_id)
    new_path, new, new_hash = read_parts_receipt(root, after, project_id)
    if old_path == new_path:
        raise ValueError("Select two distinct parts receipts")
    if old.plan is None or new.plan is None:
        raise ValueError("Both parts receipts need a BOM plan")
    references, quantities = _compare(old.plan, new.plan)
    directory = receipt_directory(
        root,
        project_id,
        output or Path("build/bom-comparison") / f"{project_id}-{uuid4().hex[:12]}",
    )
    report = BomComparisonReport(
        project_id=project_id,
        before_receipt=old_path.relative_to(root).as_posix(),
        after_receipt=new_path.relative_to(root).as_posix(),
        before_report_sha256=old_hash,
        after_report_sha256=new_hash,
        before_source_hashes=old.source_hashes,
        after_source_hashes=new.source_hashes,
        source_scope="SAME_PATHS"
        if old.source_hashes.keys() == new.source_hashes.keys()
        else "DIFFERENT_PATHS",
        before_status=old.status,
        after_status=new.status,
        references=references,
        quantities=quantities,
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(_html(report), encoding="utf-8")
    if (
        digest(old_path) != old_hash
        or digest(new_path) != new_hash
        or digest(old_path.parent / "netlist.xml") != old.netlist_sha256
        or digest(new_path.parent / "netlist.xml") != new.netlist_sha256
    ):
        raise ValueError("Selected parts evidence changed during BOM comparison")
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "comparison.json", report)
    return report
