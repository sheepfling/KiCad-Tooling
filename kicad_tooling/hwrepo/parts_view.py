"""Self-contained beginner review page for a source-bound purchasing receipt."""
from __future__ import annotations

from html import escape

from .models import PurchasingReport

STYLE = """
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#203047;
background:#f4f6f8;line-height:1.55}*{box-sizing:border-box}body{margin:0}main{max-width:1180px;
margin:auto;padding:44px 28px 70px}header{margin-bottom:30px}.eyebrow{letter-spacing:.16em;
text-transform:uppercase;font-size:12px;font-weight:750;color:#49716b}h1{font-size:38px;line-height:1.15;
letter-spacing:-.04em;margin:12px 0}h2{font-size:21px;margin:0 0 12px}h3{font-size:16px;margin:0 0 6px}
p{margin:8px 0}.subtitle{color:#5a687a;max-width:760px}.badge{display:inline-block;border-radius:99px;
padding:5px 12px;font-weight:650;font-size:13px;background:#fff0d8;color:#784609}.ready{background:#dceee7;
color:#205c48}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:26px 0}.card,section{
background:white;border:1px solid #dbe2e8;border-radius:14px;padding:23px}section{margin:20px 0}
.number{display:block;font-size:30px;font-weight:700;letter-spacing:-.03em}.label{color:#5a687a;font-size:13px}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}.step{border-top:3px solid #dce7e5;
padding-top:14px}.step small{color:#49716b;font-weight:750}.step p{font-size:14px;color:#536174}
a{color:#166758;text-underline-offset:3px}.button{display:inline-block;background:#205f51;color:white;
text-decoration:none;padding:10px 16px;border-radius:8px;font-weight:650;margin:8px 8px 0 0}
.secondary{background:#edf3f1;color:#205f51}.toolbar{display:flex;align-items:center;gap:16px;
flex-wrap:wrap;margin:18px 0}input[type=search]{font:inherit;padding:10px 13px;border:1px solid #b7c3ce;
border-radius:8px;flex:1;min-width:210px}input:focus{outline:2px solid #3b8f7e;outline-offset:2px}
label{font-size:14px}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;
font-size:11px;letter-spacing:.06em;text-transform:uppercase;background:#f6f8fa;color:#536174}
th,td{padding:14px 12px;border-bottom:1px solid #e3e8ed;vertical-align:top}td small{display:block;
color:#657284;margin-top:3px}.table-scroll{overflow-x:auto}code{font-family:ui-monospace,monospace;
font-size:12px;overflow-wrap:anywhere}.notice{border-left:3px solid #c88b35;padding:6px 16px;
margin:16px 0;background:#fffaf1}.muted{color:#657284;font-size:13px}.error{color:#8a4b1c}
.finding{padding:12px 0;border-bottom:1px solid #e3e8ed}.finding:last-child{border:0}
details{margin-top:18px}summary{cursor:pointer;font-weight:600}.empty{padding:16px;color:#657284}
footer{font-size:12px;color:#657284;margin-top:26px}button{cursor:pointer} [hidden]{display:none!important}
@media(max-width:700px){main{padding:24px 16px}h1{font-size:30px}.cards,.steps{grid-template-columns:1fr}
.card{padding:16px}.number{font-size:24px}section{padding:18px}th,td{padding:10px}}
"""
SCRIPT = """
const search = document.getElementById('search');
const issues = document.getElementById('issues-only');
function filterRows() {
  const query = search.value.toLowerCase();
  let shown = 0;
  document.querySelectorAll('#components tbody tr').forEach(row => {
    const visible = row.textContent.toLowerCase().includes(query)
      && (!issues.checked || row.dataset.issue === 'yes');
    row.hidden = !visible;
    shown += visible ? 1 : 0;
  });
  document.getElementById('row-count').textContent = shown + ' component(s) shown';
}
if (search) { search.addEventListener('input', filterRows);
  issues.addEventListener('change', filterRows); filterRows(); }
"""


def render_html(report: PurchasingReport) -> str:
    """Escape all design/catalog text; loading a receipt performs no network calls."""
    ready = report.status == "READY_FOR_ORDER_REVIEW"
    status = {"READY_FOR_ORDER_REVIEW": "Ready for supplier review",
              "NEEDS_PARTS": "Part details need attention", "BLOCKED": "Could not read the parts"}
    sections: list[str] = []
    title = escape(report.project_id)
    if report.native_status == "FAIL":
        sections.append(
            '<section class="notice"><strong>Existing native validation failed.</strong>'
            '<p>Inspect the native receipt and resolve its findings before using this parts plan. '
            'Part metadata can still be reviewed here.</p></section>'
        )
    if report.plan is None:
        sections.append('<section><h2>Start here</h2>' + ''.join(
            f'<p class="notice">{escape(message)}</p>' for message in report.issues
        ) + ''.join(f'<p>{escape(action)}</p>' for action in report.next_actions) + '</section>')
    else:
        plan = report.plan
        prefs = plan.preferences
        sections.append(f'''<div class="cards">
<div class="card"><span class="label">Boards to build</span><span class="number">{prefs.boards}</span></div>
<div class="card"><span class="label">Purchasing groups</span><span class="number">{len(plan.lines)}</span></div>
<div class="card"><span class="label">Details to resolve</span><span class="number">{len(plan.findings)}</span></div>
</div><section><h2>Your path to an order</h2><div class="steps">
<div class="step"><small>01 / SELECT</small><h3>Give every fitted part an identity</h3>
<p>Open the parts picker to choose a reviewed part, footprint, 3D model and supplier number together.</p>
<p><code>python -B -m kicad_tooling.parts --project {title} --picker</code></p></div>
<div class="step"><small>02 / COUNT</small><h3>Save build preferences</h3>
<p>This plan uses {prefs.boards} board(s), with {prefs.spare_percent}% extras or at least
{prefs.spare_minimum} spare(s) per part, whichever is larger. Percentage spares round up.</p></div>
<div class="step"><small>03 / REVIEW</small><h3>Match parts in DigiKey</h3>
<p>Upload the list, then check manufacturer, package, availability and price.
Use an assembly multiplier of 1 and no extra attrition; these quantities already include spares.</p></div>
</div></section>''')
        manifest = next((name for name in report.input_hashes
                         if name.endswith(f"/{report.project_id}/project.json")),
                        f"projects/{report.project_id}/project.json")
        prefs_path = manifest.removesuffix("project.json") + "docs/purchasing.json"
        rerun = (f"python -B -m kicad_tooling.parts --project {report.project_id} --boards {prefs.boards} "
                 f"--spare-percent {prefs.spare_percent} --spare-minimum {prefs.spare_minimum}")
        initialize = (f"python -B -m kicad_tooling.parts --project {report.project_id} "
                      f"--init-preferences {prefs_path} --boards {prefs.boards} "
                      f"--spare-percent {prefs.spare_percent} --spare-minimum {prefs.spare_minimum}")
        sections.append('<section><h2>Adjust the build</h2><p>Change the numbers below and run '
                        'the command from your repository. Each run makes a fresh review.</p><p><code>'
                        + escape(rerun) + '</code></p><details><summary>Save defaults for next time</summary>'
                        '<p>Create this file once, then edit its quantities or reviewed DigiKey SKUs. '
                        'Future runs load it automatically.</p><p><code>' + escape(initialize)
                        + '</code></p></details></section>')
        downloads = '<a class="button secondary" href="bom.csv" download>Download review BOM</a>'
        if ready:
            downloads = '<a class="button" href="digikey.csv" download>Download DigiKey list</a>' + downloads
            guidance = ('Map Part Number, Quantity and Customer Reference when uploading. '
                        'Confirm each matched product before adding it to your cart.')
        else:
            guidance = ('Resolve the items below and rerun the command to unlock the DigiKey list. '
                        'The review BOM helps you fill in the missing details.')
        sections.append(f'<section><h2>Order files</h2><p>{guidance}</p>{downloads}'
                        '<a class="button secondary" href="https://www.digikey.com/en/mylists/" '
                        'target="_blank" rel="noopener noreferrer">Open DigiKey myLists</a></section>')
        if plan.findings:
            findings = ''.join(
                f'<div class="finding"><strong>{escape(f.message)}</strong>'
                f'<p>{escape(f.action)}</p><small class="muted">'
                f'{escape(", ".join(f.references) or "Part catalog / preferences")}</small></div>'
                for f in plan.findings
            )
            sections.append('<section><h2>What needs attention</h2>' + findings + '</section>')
        rows: list[str] = []
        for component in plan.components:
            problems = tuple(f for f in plan.findings if component.reference in f.references)
            global_blockers = any(not f.references for f in plan.findings)
            excluded = component.reference in plan.excluded_references
            line = next((item for item in plan.lines if component.reference in item.references), None)
            detail = ('Excluded from purchasing' if excluded else ' / '.join(f.message for f in problems)
                      if problems else 'Resolve catalog / preferences above' if global_blockers
                      else 'Part details complete')
            part = escape(component.part_id or 'No PART_ID assigned')
            if line is not None:
                part += f'<small>{escape(line.manufacturer)} · {escape(line.mpn)}</small>'
                part += (f'<a href="{escape(line.search_url, quote=True)}" target="_blank" '
                         'rel="noopener noreferrer">Find in DigiKey</a>')
            rows.append(f'<tr data-issue="{"yes" if problems or (global_blockers and not excluded) else "no"}"><td><strong>'
                        f'{escape(component.reference)}</strong></td><td>{escape(component.value)}'
                        f'<small>{escape(component.footprint or "No footprint assigned")}</small></td>'
                        f'<td>{part}</td><td>{escape(detail)}</td></tr>')
        sections.append('''<section><h2>Component checklist</h2><div class="toolbar">
<input id="search" type="search" aria-label="Search component references, values or part numbers"
placeholder="Search reference, value or part number…"><label><input type="checkbox" id="issues-only">
Only items needing attention</label></div><p class="muted" id="row-count" aria-live="polite"></p>
<div class="table-scroll"><table id="components"><thead><tr><th>Reference</th><th>Value / footprint</th>
<th>Catalog part</th><th>Next step</th></tr></thead><tbody>''' + ''.join(rows) + '</tbody></table></div></section>')
        if plan.lines:
            quantities = ''.join(f'<tr><td>{escape(line.part_id)}<small>{escape(", ".join(line.references))}'
                                 f'</small></td><td>{line.per_board}</td><td>{line.required}</td>'
                                 f'<td>{line.spares}</td><td><strong>{line.quantity}</strong></td></tr>'
                                 for line in plan.lines)
            sections.append('<section><h2>Quantity worksheet</h2><p class="muted">'
                            'Counts for resolved purchasing groups. The complete list is released '
                            'for supplier review only after all details are resolved.</p>'
                            '<div class="table-scroll"><table><thead><tr><th>Part</th><th>Per board</th>'
                            '<th>Needed</th><th>Spares</th><th>Order</th></tr></thead><tbody>'
                            + quantities + '</tbody></table></div></section>')
    evidence = (f'<details><summary>Receipt details</summary><p>Saved design files: '
                f'{len(report.source_hashes)}. Runner: {escape(report.selected_runner or "native receipt")}.</p>'
                '<p><a href="report.json">Full report and source hashes</a> · '
                '<a href="report.txt">Plain text report</a></p></details>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Parts to order · {title}</title><style>{STYLE}</style></head><body><main>'
            f'<header><div class="eyebrow">KiCad / Parts to order</div><h1>{title}</h1>'
            '<p class="subtitle">Turn your saved design into a clear parts checklist and an order list.</p>'
            f'<p><span class="badge{" ready" if ready else ""}">{status[report.status]}</span></p>'
            '</header>' + ''.join(sections) + evidence
            + '<footer>This is a saved parts review. It does not check electrical correctness, '
            'physical fit, current stock or prices, and does not place an order. '
            'Regenerate after changing the design or part records.</footer>'
            f'</main><script>{SCRIPT}</script></body></html>')
