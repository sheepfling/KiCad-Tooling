"""Offline handoff page with escaped source, finding, and note labels."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from .review_handoff_models import ReviewHandoffReport


def render_review_handoff(report: ReviewHandoffReport) -> str:
    snapshots = "".join(
        "<tr>"
        f"<th>{escape(item.snapshot)}</th>"
        f"<td>{escape(item.identity.source_relation)}</td>"
        f"<td><code>{escape(item.identity.source_fingerprint)}</code></td>"
        f"<td>{escape(item.findings_integrity)}</td>"
        f"<td>{'<br>'.join(escape(issue) for issue in item.issues) or 'None'}</td>"
        "</tr>"
        for item in (report.baseline, report.candidate)
    )
    findings = (
        "".join(
            "<tr>"
            f"<td>{escape(item.snapshot)}</td>"
            f"<td><code>{item.fingerprint}</code></td>"
            f"<td>{escape(item.finding.origin)} · {escape(item.finding.rule)}</td>"
            f"<td>{escape(item.finding.title)}</td>"
            f"<td>{escape(item.finding.severity)}</td>"
            "</tr>"
            for item in report.findings
        )
        or '<tr><td colspan="5">No selected findings are available in these receipts.</td></tr>'
    )
    notes = (
        "".join(
            "<tr>"
            f"<td>{escape(item.note.snapshot)}</td>"
            f"<td>{escape(item.note.reviewer)}<br><small>{escape(item.note.recorded_at)}</small></td>"
            f"<td>{escape(item.note.assessment)}</td>"
            f"<td>{escape(item.note.text)}</td>"
            f"<td>{escape(item.state)}{' · CONFLICT' if item.conflict else ''}</td>"
            "</tr>"
            for item in report.notes
        )
        or '<tr><td colspan="5">No authored notes target the selected fingerprints.</td></tr>'
    )
    links = "".join(
        f'<li><a href="{escape(quote(item.packet_file, safe="/.-_"), quote=True)}">'
        f"{escape(item.snapshot)} · {escape(item.packet_file)}</a> · "
        f"SHA-256 <code>{item.sha256}</code> · from <code>{escape(item.source_path)}</code></li>"
        for item in report.evidence_links
    )
    issues = "".join(f"<li>{escape(issue)}</li>" for issue in report.issues) or "<li>None.</li>"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review handoff · {escape(report.project_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203446;background:#f3f6f8}}*{{box-sizing:border-box}}
body{{margin:0}}main{{max-width:1180px;margin:auto;padding:36px 20px 65px}}section{{background:white;
border:1px solid #d9e2e8;border-radius:12px;padding:20px;margin:18px 0}}h1{{font-size:2.1rem}}
.notice{{background:#fff2d9;border-left:4px solid #a56c27;padding:14px 17px;border-radius:6px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;
vertical-align:top;border-bottom:1px solid #e2e8ed}}code{{font:12px ui-monospace,monospace;overflow-wrap:anywhere}}
p,li,td{{overflow-wrap:anywhere}}a{{color:#116078}}a:focus-visible{{outline:3px solid #218fa5}}</style><main>
<header><h1>Review handoff · {escape(report.project_id)}</h1>
<p class="notice">Notes are attributed project-authored observations. A resolved claim,
an evidence link, and this packet do not approve an electrical design or release.</p></header>
<section><h2>Selected revisions</h2><div class="scroll"><table><thead><tr><th>Snapshot</th>
<th>Source vs current</th><th>Source fingerprint</th><th>Findings evidence</th><th>Issues</th>
</tr></thead><tbody>{snapshots}</tbody></table></div></section>
<section><h2>Selected findings</h2><div class="scroll"><table><thead><tr><th>Revision</th>
<th>Fingerprint</th><th>Origin and rule</th><th>Finding</th><th>Severity</th></tr></thead>
<tbody>{findings}</tbody></table></div></section>
<section><h2>Reviewer notes</h2><p>Source: <code>{escape(report.notes_path)}</code> ·
SHA-256 <code>{report.notes_sha256}</code> · <a href="notes.json">Exact selected notes</a>.</p>
<div class="scroll"><table><thead><tr><th>Scope</th><th>Reviewer</th><th>Assessment</th>
<th>Note</th><th>State</th></tr></thead><tbody>{notes}</tbody></table></div></section>
<section><h2>Retained evidence</h2><ul>{links}</ul><h3>Missing or changed evidence</h3>
<ul>{issues}</ul></section>
<p><a href="handoff.json">Structured handoff receipt</a></p></main></html>"""
