"""Loopback browser adapter for automatic CAD, reviewed parts and order files."""
from __future__ import annotations

import hashlib
import re
import secrets
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl

from .contract_coach import AutoNetlistRunner, NetlistRunner, project_context
from .contracts import repo_path
from .evidence import digest
from .models import (
    CadImportReport,
    CadSourceReport,
    CadSourcingReview,
    CadStepReport,
    DigiKeyHandoffResult,
    PartPickerReport,
    PartSelectionAssignment,
    PartSelectionMap,
    PurchasingPreferences,
    PurchasingReport,
    StrictModel,
)
from .part_picker import create_picker, selection
from .part_picker_view import save_picker, save_selection
from .parts_workflow import (
    input_hashes,
    load_preferences,
    new_receipt,
    prepare,
    save_report,
    selected_project,
)

MAX_BODY = 64 * 1024


@dataclass(frozen=True)
class Form:
    """Validated HTTP form boundary; core services never receive raw payloads."""

    fields: tuple[tuple[str, str], ...]

    @classmethod
    def decode(cls, body: bytes) -> Form:
        if len(body) > MAX_BODY:
            raise ValueError("The request is too large")
        fields = tuple(parse_qsl(body.decode("utf-8"), keep_blank_values=True,
                                 strict_parsing=True, max_num_fields=1024,
                                 encoding="utf-8", errors="strict"))
        names = [name for name, _ in fields]
        if len(names) != len(set(names)):
            raise ValueError("A request field appears more than once")
        return cls(fields)

    def empty(self) -> None:
        if self.fields:
            raise ValueError("This action does not accept request fields")

    def review(self) -> str:
        if len(self.fields) != 1 or self.fields[0][0] != "review" or not self.fields[0][1].strip():
            raise ValueError("Provide the review shown on this page")
        return self.fields[0][1]

    def cad_source(self) -> tuple[str, str | None]:
        values = dict(self.fields)
        if set(values) != {"id", "expected_mpn"}:
            raise ValueError("Provide an LCSC part number and optional expected MPN")
        supplier_id, expected_mpn = values["id"], values["expected_mpn"]
        if re.fullmatch(r"C[1-9][0-9]*", supplier_id) is None or len(supplier_id) > 32:
            raise ValueError("Use an exact LCSC part number such as C2040")
        if (len(expected_mpn) > 200 or expected_mpn != expected_mpn.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in expected_mpn)):
            raise ValueError("Expected MPN must be exact text without padding or control characters")
        return supplier_id, expected_mpn or None

    def assignments(self) -> tuple[PartSelectionAssignment, ...]:
        if not self.fields or any(not name.startswith("part.") for name, _ in self.fields):
            raise ValueError("Select at least one listed part")
        return tuple(PartSelectionAssignment(reference=name.removeprefix("part."), part_id=value)
                     for name, value in self.fields)

    def quantities(self) -> PurchasingPreferences:
        values = dict(self.fields)
        if set(values) != {"boards", "spare_percent", "spare_minimum"}:
            raise ValueError("Provide board quantity, spare percentage and minimum spares")
        if any(not value.isascii() or not value.isdecimal() for value in values.values()):
            raise ValueError("Quantities must be whole numbers")
        return PurchasingPreferences(boards=int(values["boards"]),
            spare_percent=int(values["spare_percent"]), spare_minimum=int(values["spare_minimum"]))


@dataclass
class Assistant:
    """One browser session; only server-created source-bound plans can be applied."""

    root: Path
    project_id: str
    runner: NetlistRunner
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    lock: threading.Lock = field(default_factory=threading.Lock)
    cad_plan: Path | None = None
    sourced_plan: Path | None = None
    sourcing_review_id: str | None = None
    sourced_source: CadSourceReport | None = None
    step_assets: dict[str, tuple[Path, str]] = field(default_factory=dict[str, tuple[Path, str]])
    picker: PartPickerReport | None = None
    selection_plan: Path | None = None
    selection_diff: Path | None = None
    order: PurchasingReport | None = None
    downloads: dict[str, str] = field(default_factory=dict[str, str])
    handoff_result: DigiKeyHandoffResult | None = None

    def invalidate(self) -> None:
        self.cad_plan = None
        self.sourced_plan = None
        self.sourcing_review_id = None
        self.sourced_source = None
        self.step_assets.clear()
        self.picker = None
        self.selection_plan = None
        self.selection_diff = None
        self.reset_order()

    def reset_order(self) -> None:
        self.order = None
        self.downloads.clear()
        self.handoff_result = None

    def source_cad(self, supplier_id: str, expected_mpn: str | None) -> CadSourcingReview:
        from .cad_library import plan
        from .cad_source import fetch

        self.sourced_plan = None
        self.sourcing_review_id = None
        self.sourced_source = None
        self.step_assets.clear()
        source = fetch(self.root, supplier_id, new_receipt(self.root, self.project_id, None),
                       expected_mpn=expected_mpn)
        import_plan = None
        review_id = secrets.token_urlsafe(24)
        if source.status == "READY":
            if source.bundle is None or source.bundle_directory is None:
                raise ValueError("The CAD provider returned an incomplete bundle; find the part again")
            import_plan = plan(self.root, self.project_id, Path(source.bundle_directory),
                               new_receipt(self.root, self.project_id, None))
            if import_plan.status == "PLAN" and import_plan.plan_path is not None:
                self.sourced_plan = Path(import_plan.plan_path)
                self.sourcing_review_id = review_id
                self.sourced_source = source
        return CadSourcingReview(source=source, import_plan=import_plan, review_id=review_id)

    def check_step(self, review: str) -> CadStepReport:
        from .cad_step import review as compare

        if (self.sourcing_review_id is None or self.sourced_source is None
                or review != self.sourcing_review_id):
            raise ValueError("Find the exact part again before checking its STEP model")
        self.step_assets.clear()
        report = compare(self.root, self.project_id, self.sourced_source,
                         new_receipt(self.root, self.project_id, None))
        if report.status == "REVIEW":
            output = Path(report.receipt_directory)
            self.step_assets = {
                name: (output / name, sha) for name, sha in report.artifacts_sha256.items()
                if name in {"index.html", "index.css", "assembly.step"} or name.endswith(".png")
            }
        return report

    def step_asset(self, name: str) -> bytes:
        if name not in self.step_assets:
            raise ValueError("Prepare a current STEP comparison before opening its views")
        path, expected = self.step_assets[name]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            self.step_assets.clear()
            raise ValueError("STEP review files changed; prepare a fresh comparison")
        return content

    def import_cad(self, review: str) -> CadImportReport:
        from .cad_library import apply

        if self.sourced_plan is None or self.sourcing_review_id is None:
            raise ValueError("Find a part and review its CAD before adding it to the project")
        if review != self.sourcing_review_id:
            raise ValueError("A newer CAD review replaced this page; find the part again before adding it")
        # The form only identifies the server-held plan; it never supplies a path.
        path = self.sourced_plan
        self.invalidate()
        return apply(self.root, self.project_id, path,
                     new_receipt(self.root, self.project_id, None))

    def scan(self) -> StrictModel:
        from .auto_cad import plan

        self.cad_plan = None
        report = plan(self.root, self.project_id, new_receipt(self.root, self.project_id, None))
        self.cad_plan = Path(report.plan_path) if report.plan_path is not None else None
        return report

    def apply_cad(self) -> StrictModel:
        from .auto_cad import apply

        if self.cad_plan is None:
            raise ValueError("Scan the board and review the proposed models before applying")
        path = self.cad_plan
        self.invalidate()
        return apply(self.root, self.project_id, path,
                     new_receipt(self.root, self.project_id, None))

    def parts(self) -> PartPickerReport:
        self.picker = None
        self.selection_plan = None
        self.selection_diff = None
        output = new_receipt(self.root, self.project_id, None)
        report = create_picker(self.root, self.project_id, output, self.runner)
        save_picker(output, report)
        self.picker = report
        return report

    def choose(self, assignments: tuple[PartSelectionAssignment, ...]) -> StrictModel:
        self.selection_plan = None
        self.selection_diff = None
        if self.picker is None or self.picker.selection_template is None:
            raise ValueError("Load the current part choices before selecting")
        allowed = {item.component.reference: item.choice_ids for item in self.picker.items}
        if any(item.part_id not in allowed.get(item.reference, ()) for item in assignments):
            raise ValueError("Selection contains a part that was not offered for that reference")
        spec = PartSelectionMap(project_id=self.project_id,
            preconditions=self.picker.selection_template.preconditions, assignments=assignments)
        # The submitted form never supplies a filesystem path or source precondition.
        draft_output = new_receipt(self.root, self.project_id, None)
        path = draft_output / "selection.json"
        path.write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
        output = new_receipt(self.root, self.project_id, None)
        report = selection(self.root, self.project_id, path, output)
        save_selection(output, report)
        if report.status == "PLAN" and report.locked_map is not None:
            self.selection_plan = Path(report.locked_map)
            self.selection_diff = output / "selection.diff"
        return report

    def apply_selection(self) -> StrictModel:
        if self.selection_plan is None:
            raise ValueError("Preview the selected parts before applying")
        path = self.selection_plan
        self.invalidate()
        output = new_receipt(self.root, self.project_id, None)
        report = selection(self.root, self.project_id, path, output, apply=True)
        save_selection(output, report)
        return report

    def prepare_order(self, preferences: PurchasingPreferences) -> PurchasingReport:
        self.reset_order()
        output = new_receipt(self.root, self.project_id, None)
        report = prepare(self.root, self.project_id, output, self.runner,
            boards=preferences.boards, spare_percent=preferences.spare_percent,
            spare_minimum=preferences.spare_minimum)
        save_report(output, report)
        self.order = report
        allowed = ("bom.csv", "digikey.csv") if report.status == "READY_FOR_ORDER_REVIEW" else ("bom.csv",)
        for name in allowed:
            path = output / name
            if name in report.artifacts and path.is_file() and not path.is_symlink():
                self.downloads[name] = digest(path)
        return report

    def current_order(self) -> PurchasingReport:
        if self.order is None:
            raise ValueError("Prepare a current order review first")
        _, _, current = project_context(self.root, self.project_id)
        if (current != self.order.source_hashes
                or input_hashes(self.root, self.project_id, None) != self.order.input_hashes):
            self.reset_order()
            raise ValueError("The board or part information changed; prepare a fresh order review")
        return self.order

    def send_digikey(self, review: str) -> DigiKeyHandoffResult:
        from .digikey_handoff import build_payload, send

        try:
            order = self.current_order()
            # Compare only; browser-provided review identity is never a filesystem path.
            if review != order.receipt_dir:
                raise ValueError("A newer order review replaced this page; prepare a fresh review before sending")
            if order.status != "READY_FOR_ORDER_REVIEW" or order.plan is None:
                raise ValueError("Complete the parts review before sending a DigiKey list")
            if self.handoff_result is not None:
                return self.handoff_result
            payload = build_payload(order.plan)
        except (OSError, ValueError) as error:
            return DigiKeyHandoffResult(status="BLOCKED", issues=(str(error),))
        # Mark the attempt before the external write; retries require a fresh review.
        self.handoff_result = DigiKeyHandoffResult(status="ERROR", issues=(
            "The DigiKey request was not confirmed. Check DigiKey before preparing another order review.",))
        try:
            reply = send(payload, list_name=self.project_id)
            result = DigiKeyHandoffResult(status="READY", single_use_url=reply.single_use_url)
        except (OSError, ValueError) as error:
            result = DigiKeyHandoffResult(status="ERROR", issues=(str(error),
                "Your CSV files remain available. Check DigiKey before preparing a fresh order review to try again."))
        try:
            self.current_order()
        except (OSError, ValueError) as error:
            result = DigiKeyHandoffResult(status="BLOCKED", issues=(str(error),
                "DigiKey may already have received the earlier list; it no longer represents the current board."))
        self.handoff_result = result
        return result

    def download(self, name: str) -> bytes:
        if name not in self.downloads:
            raise ValueError("Prepare a current order review before downloading this file")
        order = self.current_order()
        output = Path(order.receipt_dir)
        path = repo_path(self.root, (output / name).relative_to(self.root).as_posix())
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != self.downloads[name]:
            raise ValueError("The order file changed; prepare a fresh order review")
        return content

    def execute(self, action: str, form: Form) -> StrictModel:
        if action == "source-cad":
            supplier_id, expected_mpn = form.cad_source()
            return self.source_cad(supplier_id, expected_mpn)
        if action == "import-cad":
            return self.import_cad(form.review())
        if action == "check-step":
            return self.check_step(form.review())
        if action == "select":
            return self.choose(form.assignments())
        if action == "order":
            return self.prepare_order(form.quantities())
        if action == "digikey":
            return self.send_digikey(form.review())
        form.empty()
        if action == "scan":
            return self.scan()
        if action == "apply":
            return self.apply_cad()
        if action == "parts":
            return self.parts()
        if action == "apply-selection":
            return self.apply_selection()
        raise ValueError("Unknown assistant action")


STYLE = """
:root{font-family:system-ui,-apple-system,sans-serif;color:#1b332f;background:#f3f6f4;line-height:1.5}
*{box-sizing:border-box}body{margin:0}main{max-width:1060px;margin:auto;padding:40px 24px 72px}
header{margin-bottom:28px}.eyebrow{color:#54756d;font-size:12px;font-weight:750;letter-spacing:.16em;
text-transform:uppercase}h1{font-size:38px;letter-spacing:-.04em;line-height:1.12;margin:10px 0}
h2{font-size:22px;margin:0 0 8px}p{margin:8px 0}.subtle{color:#5d716b}.small{font-size:13px}
section{background:#fff;border:1px solid #d7e2dc;border-radius:16px;padding:24px;margin:18px 0}
.heading{display:flex;align-items:start;gap:14px}.step{display:grid;place-items:center;flex-shrink:0;
width:32px;height:32px;border-radius:50%;background:#e7f0eb;color:#285f4e;font-size:14px;font-weight:750}
button,.button{border:0;border-radius:8px;background:#245d49;color:#fff;font:inherit;font-size:14px;
font-weight:650;padding:11px 16px;cursor:pointer;display:inline-block;text-decoration:none}
button:disabled{opacity:.45;cursor:default}.secondary{color:#245d49;background:#e8f0eb}
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:18px 0 0}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #73a793;
outline-offset:3px}input,select{font:inherit;color:inherit;border:1px solid #b6c8bf;border-radius:7px;
padding:9px;background:white;max-width:100%}input[type=number]{width:112px}.quantities{display:flex;
gap:18px;flex-wrap:wrap;margin:20px 0}label{font-size:13px;font-weight:600;display:grid;gap:6px}
.status{border-radius:8px;background:#edf3ef;padding:12px 15px;margin:18px 0;overflow-wrap:anywhere}
.error{background:#fff1e7;color:#85451c}.good{background:#e4f1e9;color:#22533c}.rows{margin:18px 0;overflow-wrap:anywhere}
.row{display:grid;grid-template-columns:56px minmax(0,1fr);gap:12px;border-top:1px solid #e0e7e3;
padding:15px 0}.ref{font-weight:750}.row p{font-size:13px;color:#5d716b;overflow-wrap:anywhere}
.row select{width:100%;margin-top:8px}.pill{font-size:11px;font-weight:750;letter-spacing:.04em;
display:inline-block;border-radius:20px;background:#edf3ef;padding:3px 8px;margin-left:7px}
ul{padding-left:21px}li{margin:5px 0;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;
font-size:12px;background:#f3f6f4;padding:14px;border-radius:8px;max-height:360px;overflow:auto}
summary{cursor:pointer;font-size:13px;font-weight:650}details{margin:16px 0}a{color:#245d49}
.step-views{display:grid;gap:12px;margin:16px 0}.step-pair{border:1px solid #d7e2dc;border-radius:10px;padding:12px}
.step-pair h3{margin:0 0 8px;font-size:16px}.step-images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.step-images figure{margin:0;min-width:0}.step-images figcaption{font-size:12px;font-weight:650;margin-bottom:5px}
.step-images img{display:block;width:100%;height:auto;border-radius:4px}
[hidden]{display:none!important}footer{color:#647970;font-size:12px;margin-top:26px}
@media(max-width:620px){main{padding:24px 16px 50px}h1{font-size:31px}section{padding:19px}
.actions>*{flex:1;text-align:center}.row{grid-template-columns:40px minmax(0,1fr)}}
"""

SCRIPT = """
'use strict';
const $ = id => document.getElementById(id);
const names = {READY:'Matched pair',ALREADY_PRESENT:'Already assigned',NEEDS_REVIEW:'Needs attention'};
let busy = false;
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function message(id, text, kind='') {
  const node = $(id); node.textContent = text; node.className = 'status ' + kind; node.hidden = false;
}
function notes(parent, values) {
  if (!values || !values.length) return;
  const list = element('ul'); values.forEach(value => list.append(element('li', value))); parent.append(list);
}
function setBusy(value) {
  busy=value;
  document.querySelectorAll('button,input,select').forEach(button => {
    if (value) { button.dataset.disabled=button.disabled ? 'yes' : 'no'; button.disabled=true; }
    else button.disabled=button.dataset.disabled === 'yes';
  });
  $('working').hidden=!value;
}
async function action(path, statusId, working, form=new URLSearchParams()) {
  if (busy) return null;
  setBusy(true); message(statusId, working);
  try {
    const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:form,credentials:'same-origin',cache:'no-store'});
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
  } catch(error) { message(statusId, error.message, 'error'); return null; }
  finally { setBusy(false); }
}
function receipt(parent, report) {
  const path=report.receipt_directory || report.receipt_dir;
  if(path) { const details=element('details'); details.append(element('summary','Saved review details'),element('p',path,'subtle small')); parent.append(details); }
}
let sourcingReview = null;
let sourcingSource = null;
function clearSourcingReview() {
  sourcingReview=null; sourcingSource=null; $('import-cad').disabled=true; $('check-step').disabled=true;
  $('source-results').replaceChildren(); $('step-results').replaceChildren(); $('step-status').hidden=true;
}
function renderSourceIdentity(source) {
  const bundle=source && source.bundle;
  if(bundle) $('source-results').append(element('strong',bundle.manufacturer+' · '+bundle.mpn),
    element('p',source.supplier_id+' · '+bundle.package));
}
function renderSourceLimits(source, report, ready) {
  const parent=$('source-results'), bundle=source && source.bundle, check=report && report.check;
  const issues=[...new Set([...(bundle && bundle.issues || []),...(source && source.issues || []),
    ...(check && check.issues || []),...(report && report.issues || [])])];
  const details=element('details'); details.append(element('summary','Source and review limits'));
  if(bundle) {
    details.append(element('p','Converted with easyeda2kicad '+bundle.converter_version+
      (source.cache_hit ? ' · reused downloaded files' : ''),'subtle small'));
    if(bundle.source_url) details.append(element('p','Source: '+bundle.source_url,'subtle small'));
    if(bundle.retrieved_at) details.append(element('p','Retrieved: '+bundle.retrieved_at,'subtle small'));
  }
  notes(ready ? details : parent,issues);
  if(bundle || ready && issues.length) parent.append(details);
}
function renderCadImport(report, applied=false) {
  const parent=$('source-results');
  if(report.symbol_id) parent.append(element('p','KiCad symbol: '+report.symbol_id));
  if(report.footprint_id) parent.append(element('p','Paired footprint: '+report.footprint_id,'subtle small'));
  const check=report.check;
  if(check) {
    const models=check.model_references || [];
    const modelLabel=models.some(reference=>reference.toLowerCase().endsWith('.wrl')) ? 'WRL model included' : models.length+' model references';
    parent.append(element('p',(check.symbol_pins || []).length+' symbol pins · '+
      (check.footprint_pads || []).length+' numbered pads · '+modelLabel));
    parent.append(element('p','Checks compare files and pin numbers. STEP export is not verified; review actual fit, dimensions and polarity.','subtle small'));
  }
  if(report.files && report.files.length) {
    const details=element('details'); details.append(element('summary',applied ? 'Added project files' : 'Project files to add or update'));
    notes(details,report.files); parent.append(details);
  }
  if(report.diff) { const details=element('details'); details.append(element('summary','Exact source changes'),element('pre',report.diff)); parent.append(details); }
  if(applied && report.symbol_id) {
    parent.append(element('p','In KiCad, press A in the schematic and choose '+report.symbol_id+
      '. Wire the symbol, then use Update PCB from Schematic (F8) to add its assigned footprint.'));
  }
  receipt(parent,report);
}
['source-id','source-mpn'].forEach(id=>$(id).addEventListener('input',()=> {
  clearSourcingReview(); message('source-status','Find the part again to review the updated choice.');
}));
$('find-cad').addEventListener('click',async()=> {
  if(busy) return;
  clearSourcingReview();
  const form=new URLSearchParams({id:$('source-id').value.trim(),expected_mpn:$('source-mpn').value.trim()});
  const review=await action('source-cad','source-status','Finding the exact part and preparing its CAD library…',form);
  if(!review) return;
  const source=review.source, plan=review.import_plan;
  const ready=source.status==='READY' && plan && plan.status==='PLAN' && plan.plan_path;
  message('source-status',ready ? 'CAD is ready to review. Check the identity and file changes, then add it to this project.' :
    'This part needs attention before its CAD can be added.',ready ? 'good' : 'error');
  renderSourceIdentity(source);
  if(plan) renderCadImport(plan);
  else receipt($('source-results'),source);
  renderSourceLimits(source,plan,ready);
  if(ready) {sourcingReview=review.review_id; sourcingSource=source; $('import-cad').disabled=false; $('check-step').disabled=false;}
});
function renderStepViews(parent) {
  const gallery=element('div',undefined,'step-views');
  for(const pose of ['top','turned','bottom','angled']) {
    const pair=element('div',undefined,'step-pair'), images=element('div',undefined,'step-images');
    pair.append(element('h3',pose[0].toUpperCase()+pose.slice(1)));
    for(const kind of ['wrl','step']) {
      const figure=element('figure'), image=element('img');
      image.src='step/'+kind+'-'+pose+'.png';
      image.alt=kind.toUpperCase()+' '+pose+' placement on the same test footprint';
      figure.append(element('figcaption',kind==='wrl' ? 'Paired WRL' : 'Raw STEP'),image);
      images.append(figure);
    }
    pair.append(images); gallery.append(pair);
  }
  parent.append(gallery);
}
$('check-step').addEventListener('click',async()=> {
  if(!sourcingReview || busy) return;
  $('step-results').replaceChildren();
  const report=await action('check-step','step-status',
    'Comparing STEP and WRL in the pinned KiCad version. This may take a minute…',
    new URLSearchParams({review:sourcingReview}));
  if(!report) return;
  const ready=report.status==='REVIEW';
  message('step-status',ready ? 'STEP views and a test assembly are ready to inspect.' :
    'STEP review could not finish; see the finding below.',ready ? 'good' : 'error');
  const parent=$('step-results');
  if(ready) {
    parent.append(element('p','Compare the same pads in each view. Select the full-page gallery for larger images and the disposable STEP assembly.','subtle small'));
    renderStepViews(parent);
    const link=element('a','Open full-page comparison and STEP assembly','button secondary');
    link.href='step/index.html'; parent.append(link);
  }
  notes(parent,report.issues); receipt(parent,report);
});
$('import-cad').addEventListener('click',async()=> {
  if(!sourcingReview) return;
  const review=sourcingReview, source=sourcingSource; sourcingReview=null; sourcingSource=null; $('import-cad').disabled=true;
  clearOrderView();
  const report=await action('import-cad','source-status','Adding the reviewed CAD library to this project…',new URLSearchParams({review}));
  invalidateOtherViews(); $('apply-cad').disabled=true; $('check-step').disabled=true;
  $('step-results').replaceChildren(); $('step-status').hidden=true;
  $('cad-results').replaceChildren(); message('cad-status','Scan again after updating and saving the board.');
  if(!report) return;
  $('source-results').replaceChildren();
  const applied=report.status==='APPLIED';
  renderSourceIdentity(source); renderCadImport(report,applied); renderSourceLimits(source,report,applied);
  message('source-status',applied ? 'The CAD library is available in this project. Choose the symbol in KiCad to use it.' :
    'The CAD library was not added. Find the part again after resolving the issues below.',applied ? 'good' : 'error');
});
function renderCad(report) {
  $('cad-results').replaceChildren();
  const applied=report.status === 'APPLIED';
  message('cad-status', applied ? 'Matched models were added. Reopen or refresh the board in KiCad to see them.' :
    report.status === 'BLOCKED' ? 'The board needs attention before models can be added.' :
    report.plan_path ? 'Matching models are ready. Review the components below, then add them to the board.' :
    'The scan is complete. See each component below.', report.status==='BLOCKED' ? 'error' : applied ? 'good' : '');
  (report.items || []).forEach(item => {
    const row=element('div',undefined,'row'), body=element('div');
    body.append(element('strong',item.footprint),element('span',names[item.status] || item.status,'pill'),element('p',item.detail));
    row.append(element('div',item.reference || item.ref,'ref'),body); $('cad-results').append(row);
  });
  const shownIssues=new Set((report.items || []).map(item=>(item.reference || item.ref)+': '+item.detail));
  notes($('cad-results'),(report.issues || []).filter(issue=>!shownIssues.has(issue)));
  if(report.files && report.files.length) { const details=element('details'); details.append(element('summary','Files to add or update')); notes(details,report.files); $('cad-results').append(details); }
  if(report.diff) { const details=element('details'); details.append(element('summary','Exact source changes'),element('pre',report.diff)); $('cad-results').append(details); }
  receipt($('cad-results'),report);
  $('apply-cad').disabled=!report.plan_path || applied || report.status==='BLOCKED';
}
$('scan').addEventListener('click',async()=> { const report=await action('scan','cad-status','Finding paired footprints and 3D models…'); if(report) renderCad(report); });
function clearOrderView() {
  ['order-results','order-downloads','handoff-results'].forEach(id=>$(id).replaceChildren());
  $('handoff-status').hidden=true;
}
function invalidateOtherViews() {
  clearOrderView(); $('apply-selection').disabled=true; $('preview-selection').disabled=true;
  $('parts-results').replaceChildren(); $('selection-results').replaceChildren();
  message('parts-status','Reload choices after changing the board.');
  message('order-status','Prepare a fresh order list after changing the board.');
}
$('apply-cad').addEventListener('click',async()=> {
  clearSourcingReview(); clearOrderView();
  const report=await action('apply','cad-status','Adding the reviewed model pairs…');
  if(report) { renderCad(report); invalidateOtherViews(); }
});
$('load-parts').addEventListener('click',async()=> {
  const report=await action('parts','parts-status','Reading the saved schematic and matching reviewed parts. KiCad capture may take a moment…');
  if(!report) return;
  $('parts-results').replaceChildren(); $('selection-results').replaceChildren(); $('apply-selection').disabled=true;
  const choices=new Map((report.choices || []).map(part=>[part.id,part]));
  let count=0;
  (report.items || []).forEach(item=> {
    const component=item.component, row=element('div',undefined,'row'), body=element('div');
    body.append(element('strong',component.value),element('p',component.footprint || 'No footprint assigned'));
    if(item.choice_ids.length) {
      const label=element('label','Choose a reviewed part'), select=element('select');
      select.addEventListener('change',()=> {clearOrderView(); message('order-status','Save selected parts, then prepare a fresh order list.');});
      select.name='part.'+component.reference; select.append(new Option('Keep current part',''));
      item.choice_ids.forEach(id=> {const part=choices.get(id); select.append(new Option(part.manufacturer+' · '+part.mpn+' — '+part.description,id));});
      label.append(select); body.append(label); count++;
    }
    notes(body,item.issues); row.append(element('div',component.reference,'ref'),body); $('parts-results').append(row);
  });
  notes($('parts-results'),report.issues); receipt($('parts-results'),report);
  message('parts-status',count ? 'Choose parts below, then review their source changes.' :
    'No reviewed choices are available for these components. The details below explain what is missing.',count ? '' : 'error');
  $('preview-selection').disabled=count===0;
});
async function renderSelection(report) {
  $('selection-results').replaceChildren(); notes($('selection-results'),report.issues);
  const applied=report.status.startsWith('APPLIED');
  message('parts-status',report.status==='PLAN' ? 'Review the exact changes below before saving the selected parts.' :
    report.status==='APPLIED' ? 'Selected parts have been saved.' : report.status==='APPLIED_NEEDS_PCB_UPDATE' ?
    'Selected parts are saved. Update PCB from Schematic (F8) in KiCad for the listed footprints.' :
    'The selection needs attention.',report.status==='BLOCKED' ? 'error' : applied ? 'good' : '');
  if(report.status==='PLAN') {
    const response=await fetch('selection-diff',{cache:'no-store'});
    if(response.ok) { const details=element('details'); details.open=true; details.append(element('summary','Exact source changes'),element('pre',await response.text())); $('selection-results').append(details); }
  }
  receipt($('selection-results'),report); $('apply-selection').disabled=report.status!=='PLAN' || !report.locked_map;
}
$('preview-selection').addEventListener('click',async()=> {
  const form=new URLSearchParams(); $('parts-results').querySelectorAll('select').forEach(select=> {if(select.value) form.append(select.name,select.value);});
  const report=await action('select','parts-status','Checking selections and preparing exact source changes…',form);
  if(report) await renderSelection(report);
});
$('apply-selection').addEventListener('click',async()=> {
  clearSourcingReview(); clearOrderView();
  const report=await action('apply-selection','parts-status','Saving the reviewed selections…');
  if(report) { await renderSelection(report); $('apply-cad').disabled=true; $('order-downloads').replaceChildren(); message('order-status','Prepare a fresh order list from the saved parts.'); }
});
['boards','spare_percent','spare_minimum'].forEach(id=>$(id).addEventListener('input',()=> {
  clearOrderView(); message('order-status','Prepare a fresh order list with the updated quantities.');
}));
$('prepare-order').addEventListener('click',async()=> {
  clearOrderView();
  const form=new URLSearchParams(); ['boards','spare_percent','spare_minimum'].forEach(id=>form.append(id,$(id).value));
  const report=await action('order','order-status','Reading the saved parts and calculating the order quantities…',form);
  if(!report) return;
  $('order-results').replaceChildren(); $('order-downloads').replaceChildren();
  const ready=report.status==='READY_FOR_ORDER_REVIEW';
  message('order-status',ready ? 'Your order files are ready. Check the matched supplier products before ordering.' :
    'Some part details need attention before a DigiKey list can be prepared.',ready ? 'good' : 'error');
  notes($('order-results'),report.issues);
  if(report.plan) {
    report.plan.findings.forEach(finding=> {const block=element('div',undefined,'status'); block.append(element('strong',finding.references.join(', ') || 'Part details'),element('p',finding.message),element('p',finding.action)); $('order-results').append(block);});
    if(report.plan.lines.length) { const list=element('ul'); report.plan.lines.forEach(line=>list.append(element('li',line.quantity+' × '+line.manufacturer+' '+line.mpn+' ('+line.references.join(', ')+')'))); $('order-results').append(list); }
  }
  const files=report.artifacts || [];
  [['bom.csv','Download review BOM'],['digikey.csv','Download DigiKey list']].forEach(([file,label])=> {
    if(files.includes(file) && (file!=='digikey.csv' || ready)) { const link=element('a',label,'button'+(file==='bom.csv' ? ' secondary' : '')); link.href='download/'+file; link.download=file; $('order-downloads').append(link); }
  });
  if(ready) {
    const button=element('button','Send BOM to DigiKey'); button.id='send-digikey';
    $('order-downloads').prepend(button);
    $('handoff-results').append(element('p','Sends the listed part numbers, quantities, references and manufacturer notes to DigiKey. No API key is needed. Review matched products, packaging and prices there before ordering.','subtle small'));
    button.addEventListener('click',async()=> {
      button.disabled=true;
      const result=await action('digikey','handoff-status','Sending the prepared BOM to DigiKey…',
        new URLSearchParams({review:report.receipt_dir}));
      if(!result) { $('handoff-results').append(element('p','The request was not confirmed. CSV downloads remain available. Check DigiKey before preparing another order review.','subtle small')); return; }
      $('handoff-results').replaceChildren(); notes($('handoff-results'),result.issues);
      message('handoff-status',result.status==='READY' ? 'Your DigiKey review link is ready. No purchase has been made.' :
        'The DigiKey handoff needs attention. No automatic retry was made.',result.status==='READY' ? 'good' : 'error');
      if(result.status==='READY' && result.single_use_url) {
        const link=element('a','Review BOM in DigiKey','button'); link.href=result.single_use_url;
        link.target='_blank'; link.rel='noopener noreferrer'; $('handoff-results').append(link);
      }
    });
  }
  receipt($('order-results'),report);
});
$('scan').click();
"""


def render_html(project_id: str, preferences: PurchasingPreferences, nonce: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Finish your board · {escape(project_id)}</title><style nonce="{escape(nonce, quote=True)}">{STYLE}</style>
</head><body><main><header><div class="eyebrow">Parts assistant · {escape(project_id)}</div>
<h1>Finish your board</h1><p class="subtle">Find component CAD, add matching 3D models, and prepare an order.</p>
<p id="working" class="subtle small" role="status" hidden>Working locally. Keep this page open.</p></header>
<section aria-labelledby="source-heading"><div class="heading"><span class="step">1</span><div>
<h2 id="source-heading">Find CAD for a part</h2><p class="subtle">Enter an exact LCSC part number to get its symbol, footprint and available 3D model. No supplier login is needed.</p></div></div>
<div class="quantities"><label>LCSC part number<input id="source-id" type="text" placeholder="C2040" maxlength="32" autocomplete="off" spellcheck="false"></label>
<label>Expected manufacturer part number (optional)<input id="source-mpn" type="text" maxlength="200" autocomplete="off" spellcheck="false"></label></div>
<div class="actions"><button id="find-cad">Find CAD</button><button id="check-step" class="secondary" disabled>Check STEP alignment</button><button id="import-cad" disabled>Add CAD to this project</button></div>
<div id="source-status" class="status" role="status" hidden></div><div id="source-results" class="rows"></div>
<div id="step-status" class="status" role="status" hidden></div><div id="step-results" class="rows"></div>
<p class="subtle small">Adds a project library for you to choose in KiCad. Existing placed components and connections stay as saved; catalog approval is separate.</p></section>
<section aria-labelledby="cad-heading"><div class="heading"><span class="step">2</span><div>
<h2 id="cad-heading">Populate the 3D board</h2><p class="subtle">Find models paired with your existing footprints.
Their original alignment settings stay with them.</p></div></div>
<div id="cad-status" class="status" role="status">Checking the board…</div><div id="cad-results" class="rows"></div>
<div class="actions"><button id="scan" class="secondary">Scan again</button><button id="apply-cad" disabled>Add matched models</button></div></section>
<section aria-labelledby="parts-heading"><div class="heading"><span class="step">3</span><div>
<h2 id="parts-heading">Choose orderable parts</h2><p class="subtle">Pick from the reviewed choices available for each component.</p></div></div>
<div id="parts-status" class="status" role="status" hidden></div><div id="parts-results" class="rows"></div>
<div id="selection-results"></div><div class="actions"><button id="load-parts" class="secondary">Load part choices</button>
<button id="preview-selection" class="secondary" disabled>Review selected parts</button>
<button id="apply-selection" disabled>Save selected parts</button></div></section>
<section aria-labelledby="order-heading"><div class="heading"><span class="step">4</span><div>
<h2 id="order-heading">Prepare the order</h2><p class="subtle">Set your build quantity. The list includes the larger of percentage spares or minimum extras.</p></div></div>
<div class="quantities"><label>Boards<input id="boards" type="number" min="1" step="1" value="{preferences.boards}"></label>
<label>Extra parts (%)<input id="spare_percent" type="number" min="0" max="100" step="1" value="{preferences.spare_percent}"></label>
<label>Minimum extras per part<input id="spare_minimum" type="number" min="0" step="1" value="{preferences.spare_minimum}"></label></div>
<button id="prepare-order">Prepare order files</button><div id="order-status" class="status" role="status" hidden></div>
<div id="order-results"></div><div id="order-downloads" class="actions"></div>
<div id="handoff-status" class="status" role="status" hidden></div><div id="handoff-results"></div></section>
<footer>Uses your saved KiCad files. CAD matching checks pads and preserves library model settings; review actual geometry
and pin numbering before manufacturing. Supplier stock, price and packaging are confirmed in DigiKey.</footer>
</main><script nonce="{escape(nonce, quote=True)}">{SCRIPT}</script></body></html>'''


class AssistantServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, assistant: Assistant, port: int) -> None:
        self.assistant = assistant
        super().__init__(("127.0.0.1", port), AssistantHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.url = f"{self.origin}/{assistant.token}/"


class AssistantHandler(BaseHTTPRequestHandler):
    """Exact routes only; the server does not expose repository or receipt trees."""

    def log_message(self, format: str, *args: str) -> None:
        # Default access logs expose the session's secret path.
        return

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(15)

    @property
    def app_server(self) -> AssistantServer:
        return cast(AssistantServer, self.server)

    def route(self) -> str | None:
        server = self.app_server
        if self.headers.get_all("Host") != [server.origin.removeprefix("http://")]:
            self.respond(403, b"This assistant accepts its loopback address only")
            return None
        prefix = f"/{server.assistant.token}/"
        if not self.path.startswith(prefix) or "?" in self.path or "#" in self.path:
            self.respond(404, b"Assistant page not found")
            return None
        return self.path[len(prefix):]

    def respond(self, status: int, content: bytes, content_type: str = "text/plain; charset=utf-8",
                *, nonce: str | None = None, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; connect-src 'self'; "
            + (f"script-src 'nonce-{nonce}'; style-src 'self' 'nonce-{nonce}'; " if nonce else "style-src 'self'; ")
            + "img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        if filename is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        route = self.route()
        if route is None:
            return
        state = self.app_server.assistant
        try:
            if route == "":
                nonce = secrets.token_urlsafe(24)
                prefs = load_preferences(state.root, state.project_id, None, None, None, None)
                self.respond(200, render_html(state.project_id, prefs, nonce).encode("utf-8"),
                             "text/html; charset=utf-8", nonce=nonce)
            elif route in {"download/bom.csv", "download/digikey.csv"}:
                if not state.lock.acquire(blocking=False):
                    self.respond(409, b"Wait for the current action to finish")
                    return
                try:
                    name = route.removeprefix("download/")
                    self.respond(200, state.download(name), "text/csv; charset=utf-8", filename=name)
                finally:
                    state.lock.release()
            elif route.startswith("step/"):
                with state.lock:
                    name = route.removeprefix("step/")
                    content = state.step_asset(name)
                    content_type = ("text/html; charset=utf-8" if name == "index.html" else
                                    "image/png" if name.endswith(".png") else
                                    "text/css; charset=utf-8" if name == "index.css" else
                                    "application/step" if name == "assembly.step" else "application/octet-stream")
                    self.respond(200, content, content_type,
                                 filename=name if name == "assembly.step" else None)
            elif route == "selection-diff" and state.selection_diff is not None:
                self.respond(200, state.selection_diff.read_bytes())
            else:
                self.respond(404, b"Assistant page not found")
        except (OSError, ValueError) as error:
            self.respond(409, str(error).encode("utf-8"))

    def do_POST(self) -> None:
        route = self.route()
        if route is None:
            return
        if self.headers.get_all("Origin") != [self.app_server.origin]:
            self.respond(403, b"Open the assistant page to make changes")
            return
        if self.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin":
            self.respond(403, b"Cross-site assistant requests are not accepted")
            return
        if (self.headers.get_all("Content-Type") != ["application/x-www-form-urlencoded"]
                or self.headers.get("Transfer-Encoding") is not None):
            self.respond(415, b"Use the assistant's form controls")
            return
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
            self.respond(400, b"A request length is required")
            return
        length = int(lengths[0])
        if length > MAX_BODY:
            self.respond(413, b"The request is too large")
            return
        state = self.app_server.assistant
        if not state.lock.acquire(blocking=False):
            self.respond(409, b"Wait for the current action to finish")
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("The request was incomplete")
            report = state.execute(route, Form.decode(body))
            self.respond(200, report.model_dump_json().encode("utf-8"), "application/json")
        except (OSError, ValueError) as error:
            self.respond(400, str(error).encode("utf-8"))
        finally:
            state.lock.release()


def create_server(root: Path, project_id: str, *, port: int = 0,
                  runner: NetlistRunner | None = None) -> AssistantServer:
    root = root.resolve()
    selected_project(root, project_id)
    if not 0 <= port <= 65535:
        raise ValueError("Assistant port must be between 0 and 65535")
    return AssistantServer(Assistant(root, project_id, runner or AutoNetlistRunner("kicad-cli")), port)


def serve(root: Path, project_id: str, *, port: int = 0, open_browser: bool = True) -> None:
    """Serve a private loopback session until Ctrl-C; never start a remote listener."""
    with create_server(root, project_id, port=port) as server:
        print(f"Parts assistant: {server.url}\nKeep this terminal open; Ctrl-C stops the assistant.",
              flush=True)
        if open_browser:
            try:
                webbrowser.open(server.url)
            except webbrowser.Error as error:
                print(f"Open the assistant URL in your browser: {error}", file=sys.stderr)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
