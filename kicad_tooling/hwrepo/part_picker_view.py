"""Local selection and diff pages; browser choices only download a draft map."""
from __future__ import annotations

import difflib
from html import escape
from pathlib import Path

from .contracts import write_model
from .models import PartPickerReport, PartSelectionReport
from .parts_view import STYLE

PICKER_STYLE = """
.journey{display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:#536174;margin:20px 0}
.journey span{background:#e8efed;padding:7px 12px;border-radius:6px}.component{margin:16px 0}
.component-head{display:flex;justify-content:space-between;gap:16px;align-items:baseline}
.component-head h2{margin-bottom:4px}.component label{display:block;margin:16px 0 7px;font-weight:650}
select{font:inherit;width:100%;padding:12px;border:1px solid #aabdb7;border-radius:8px;background:white;
color:#203047;white-space:normal}.choice{margin-top:18px;border-top:1px solid #e3e8ed;padding-top:14px}
dl{display:grid;grid-template-columns:130px 1fr;gap:7px 16px;font-size:14px;margin:12px 0}
dt{color:#657284}dd{margin:0;overflow-wrap:anywhere}.selection-bar{position:sticky;bottom:12px;
background:#183f38;color:white;border-radius:12px;padding:14px 20px;display:flex;justify-content:space-between;
align-items:center;gap:16px;box-shadow:0 6px 22px #102b3824}.selection-bar p{font-size:14px}
.selection-bar button{background:white;color:#205f51;border:0;white-space:nowrap;margin:0}
button:disabled{opacity:.55;cursor:not-allowed}pre{white-space:pre-wrap;overflow-wrap:anywhere;
font-size:12px;padding:14px;background:#f6f8fa;border-radius:8px;margin:12px 0}.diff-add{color:#215e3a;
background:#edf8ef}.diff-remove{color:#963b37;background:#fff0ed}.source-diff{max-height:480px;overflow:auto}
input:focus,select:focus,button:focus{outline:2px solid #3b8f7e;outline-offset:3px}
@media(max-width:700px){dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:10px}
.selection-bar{position:static;display:block}.selection-bar button{width:100%}.component-head{display:block}}
"""
PICKER_SCRIPT = """
const form = document.getElementById('picker');
const selects = Array.from(document.querySelectorAll('select[data-reference]'));
const counter = document.getElementById('selection-count');
const download = document.getElementById('download-selection');
function updateSelection() {
  let count = 0;
  selects.forEach(select => {
    if (select.value) count++;
    select.closest('.component').querySelectorAll('.choice').forEach(choice => {
      choice.hidden = choice.dataset.partId !== select.value;
    });
  });
  counter.textContent = count + ' component' + (count === 1 ? '' : 's') + ' selected';
  download.disabled = count === 0;
}
if (form) {
  selects.forEach(select => select.addEventListener('change', updateSelection));
  updateSelection();
  form.addEventListener('submit', event => {
    event.preventDefault();
    const selection = JSON.parse(document.getElementById('selection-template').textContent);
    selection.assignments = selects.filter(select => select.value).map(select => ({
      reference: select.dataset.reference, part_id: select.value
    }));
    if (!selection.assignments.length) return;
    const blob = new Blob([JSON.stringify(selection, null, 2) + '\\n'], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = selection.project_id + '-parts-selection.json';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    document.getElementById('download-note').hidden = false;
  });
  const search = document.getElementById('search');
  search.addEventListener('input', () => {
    const query = search.value.toLowerCase();
    document.querySelectorAll('.component').forEach(card => {
      card.hidden = !card.textContent.toLowerCase().includes(query);
    });
  });
}
"""


def _page(project_id: str, title: str, body: str, script: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)} · {escape(project_id)}</title><style>{STYLE}'
            f'{PICKER_STYLE}</style></head><body><main><header>'
            '<span class="eyebrow">KiCad / Parts to board</span>'
            f'<h1>{escape(title)}</h1><p class="subtitle">{escape(project_id)}</p></header>'
            + body + '<footer>Reviewed catalog bindings preserve the existing symbol and value. '
            'They do not establish electrical suitability, mechanical fit, live stock or build approval.'
            '</footer></main>' + (f'<script>{script}</script>' if script else '') + '</body></html>')


def render_picker(report: PartPickerReport) -> str:
    """Render compatible catalog choices without making implicit selections."""
    parts = {part.id: part for part in report.choices}
    content = [('<p class="subtitle">Choose the physical part, footprint, 3D body and supplier number '
               'together. Download your choices, review the source changes, then apply.</p>'
               '<div class="journey"><span>1 · Choose parts</span><span>2 · Review changes</span>'
               '<span>3 · Update the board</span><span>4 · Build an order</span></div>')]
    if report.issues:
        content.append('<section class="notice"><h2>Before you choose</h2>' + ''.join(
            f'<p>{escape(issue)}</p>' for issue in report.issues) + '</section>')
    if report.evidence is not None and report.evidence.native_status == "FAIL":
        content.append('<section class="notice"><h2>Native validation needs attention</h2>'
                       '<p>Part choices can be reviewed here. Resolve the existing native findings '
                       'before treating this board as ready to build.</p></section>')
    if report.status == "NEEDS_CATALOG":
        content.append('<section><h2>Add reviewed parts to unlock the picker</h2><p>'
                       'No fitted component has a compatible reviewed catalog choice yet. '
                       'Add an approved manufacturer and part number with its exact symbol, value, '
                       'footprint and declared 3D source model. Then create a fresh picker.</p>'
                       '<p>Training placeholders stay visible for learning; they cannot be selected '
                       'for a production order.</p></section>')
    selectable = report.selection_template is not None and report.status != "BLOCKED"
    if selectable:
        content.append('<form id="picker"><div class="toolbar"><input id="search" type="search" '
                       'aria-label="Search components or catalog parts" '
                       'placeholder="Search reference, value or part number…"></div>')
    for index, item in enumerate(report.items):
        component = item.component
        content.append('<section class="component"><div class="component-head"><div>'
                       f'<h2>{escape(component.reference)} · {escape(component.value)}</h2>'
                       f'<p class="muted">{escape(component.symbol_id)}</p></div>'
                       f'<span class="badge">{len(item.choice_ids)} reviewed choice(s)</span></div>'
                       f'<p class="muted">Current part: {escape(component.part_id or "Unassigned")}<br>'
                       f'Current footprint: {escape(component.footprint or "Unassigned")}</p>')
        content.extend(f'<p class="notice">{escape(issue)}</p>' for issue in item.issues)
        if selectable and item.choice_ids:
            content.append(f'<label for="part-{index}">Choose a reviewed part for '
                           f'{escape(component.reference)}</label><select id="part-{index}" '
                           f'data-reference="{escape(component.reference, quote=True)}">'
                           '<option value="">Keep current / skip this component</option>')
            for part_id in item.choice_ids:
                part = parts[part_id]
                content.append(f'<option value="{escape(part.id, quote=True)}">'
                               f'{escape(part.manufacturer)} · {escape(part.mpn)} '
                               f'— {escape(part.description)}</option>')
            content.append('</select>')
            for part_id in item.choice_ids:
                part = parts[part_id]
                cad = part.cad
                if cad is None:
                    continue
                details = (("Catalog identity", part.id), ("Manufacturer", part.manufacturer),
                           ("Part number", part.mpn), ("Footprint", cad.footprint),
                           ("3D source model", cad.model),
                           ("DigiKey number", cad.digikey_sku or "Use manufacturer part number"))
                content.append(f'<div class="choice" data-part-id="{escape(part.id, quote=True)}" hidden>'
                               '<h3>This choice will use</h3><dl>' + ''.join(
                                   f'<dt>{escape(label)}</dt><dd>{escape(value)}</dd>'
                                   for label, value in details) + '</dl></div>')
        content.append('</section>')
    if selectable:
        template = report.selection_template
        assert template is not None
        # JSON is data, never executable markup, even if a catalog/path contains </script>.
        payload = (template.model_dump_json().replace('&', '\\u0026').replace('<', '\\u003c')
                   .replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))
        content.append('<div class="selection-bar"><p id="selection-count" aria-live="polite">'
                       '0 components selected</p><button class="button" id="download-selection" '
                       'type="submit" disabled>Download choices</button></div></form>'
                       f'<script type="application/json" id="selection-template">{payload}</script>')
        command = (f'python -B -m kicad_tooling.parts --project {report.project_id} '
                   f'--selection /path/to/{report.project_id}-parts-selection.json')
        content.append('<section><h2>Review before applying</h2><p id="download-note" hidden>'
                       'Your browser downloaded the choices. Use the downloaded file path below.</p>'
                       '<p>Run this from the repository, replacing the path with your downloaded file. '
                       'It creates a source diff and the exact apply command.</p>'
                       f'<pre>{escape(command)}</pre><p class="muted">'
                       'Selections are tied to the saved design. If you edit it, create a fresh picker.</p>'
                       '</section>')
    content.append('<section><h2>What happens to the 3D board?</h2><p>'
                   'A matching footprint already on the PCB gets the chosen 3D model. '
                   'For a new or changed footprint, use Update PCB from Schematic (F8) in KiCad, '
                   'place it on the board, save, then run the printed model sync command.</p>'
                   '<p>The 3D viewer shows those placed bodies. Component placement and routing '
                   'remain engineering steps.</p></section>')
    return _page(report.project_id, "Choose parts for your board", ''.join(content),
                 PICKER_SCRIPT if selectable else "")


def render_selection(report: PartSelectionReport) -> str:
    applied = report.status in {"APPLIED", "APPLIED_NEEDS_PCB_UPDATE"}
    title = "Parts applied to your design" if applied else "Review your part changes"
    body = [f'<span class="badge">{escape(report.status)}</span>']
    body.extend(f'<p class="notice">{escape(issue)}</p>' for issue in report.issues)
    if report.pending_references:
        body.append('<section><h2>Continue in KiCad</h2><p>Use Update PCB from Schematic (F8), '
                    'review the proposed footprint changes, place the components and save. '
                    'Then sync the models using the command below.</p><p><strong>'
                    + escape(', '.join(report.pending_references)) + '</strong></p></section>')
    if report.status == "PLAN":
        body.append('<p class="subtitle">These are the proposed source changes. '
                    'Review them before running the apply command below.</p>')
    for edit in report.edits:
        diff = difflib.unified_diff((edit.before or '').splitlines(), edit.after.splitlines(),
                                   fromfile=edit.path, tofile=edit.path, lineterm='')
        lines: list[str] = []
        for line in diff:
            style = 'diff-add' if line.startswith('+') else 'diff-remove' if line.startswith('-') else ''
            lines.append(f'<span class="{style}">{escape(line)}</span>')
        body.append('<section><h2>' + escape(edit.path) + '</h2><pre class="source-diff">'
                    + '\n'.join(lines) + '</pre></section>')
    if report.next_commands:
        body.append('<section><h2>Next steps</h2>' + ''.join(
            f'<pre>{escape(command)}</pre>' for command in report.next_commands) + '</section>')
    return _page(report.project_id, title, ''.join(body))


def picker_text(report: PartPickerReport) -> str:
    lines = [f'Parts picker: {report.status}', f'Project: {report.project_id}',
             f'Components: {len(report.items)}; reviewed choices: {len(report.choices)}']
    lines.extend(f'Attention: {issue}' for issue in report.issues)
    lines.extend((f'Open: {report.receipt_dir}/index.html',
                  'Choose parts in the page and download the selection to preview source changes.'))
    return '\n'.join(lines)


def selection_text(report: PartSelectionReport) -> str:
    lines = [f'Part selection: {report.status}', f'Project: {report.project_id}']
    label = 'Changed source' if report.status.startswith('APPLIED') else 'Proposed source'
    lines.extend(f'{label}: {edit.path}' for edit in report.edits)
    if report.pending_references:
        lines.append('KiCad F8 update / placement needed: ' + ', '.join(report.pending_references))
    lines.extend(f'Attention: {issue}' for issue in report.issues)
    lines.extend(f'Next: {command}' for command in report.next_commands)
    lines.append(f'Review: {report.receipt_dir}/index.html')
    return '\n'.join(lines)


def save_picker(output: Path, report: PartPickerReport) -> None:
    write_model(output / 'report.json', report)
    (output / 'report.txt').write_text(picker_text(report) + '\n', encoding='utf-8')
    (output / 'index.html').write_text(render_picker(report), encoding='utf-8')


def save_selection(output: Path, report: PartSelectionReport) -> None:
    # New files need an explicit null before-state for the strict edit contract.
    (output / 'report.json').write_text(report.model_dump_json(indent=2) + '\n', encoding='utf-8')
    (output / 'report.txt').write_text(selection_text(report) + '\n', encoding='utf-8')
    (output / 'index.html').write_text(render_selection(report), encoding='utf-8')
