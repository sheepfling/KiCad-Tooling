"""Offline onboarding review of one selected native project import."""

from __future__ import annotations

from html import escape

from .import_review_models import ImportReviewReport


def render_import_review(report: ImportReviewReport) -> str:
    files = (
        "".join(
            f"<tr><th><code>{escape(item.path)}</code></th><td>{escape(item.role)}</td>"
            f"<td>{escape(item.disposition)}</td>"
            f"<td><code>{item.sha256 or '—'}</code></td><td>{escape(item.reason)}</td></tr>"
            for item in report.files
        )
        or '<tr><td colspan="5">No source files could be inventoried.</td></tr>'
    )
    dependencies = (
        "".join(
            f"<tr><th>{escape(item.kind)}</th><td><code>{escape(item.source_location)}</code></td>"
            f"<td><code>{escape(item.reference)}</code></td><td>{escape(item.status)}</td>"
            f"<td>{escape(item.issue)}</td></tr>"
            for item in report.dependencies
        )
        or '<tr><td colspan="5">No supported CAD references were observed in included boards, footprints, or library tables.</td></tr>'
    )
    actions = (
        "".join(
            f"<li><strong>{escape(item.severity)} · {escape(item.code)}</strong> — "
            f"{escape(item.observed)}<br>{escape(item.action)}</li>"
            for item in report.diagnosis.findings
        )
        or "<li>No import blockers were found. Review the source and authored expectations before applying.</li>"
    )
    issues = "".join(f"<li>{escape(item)}</li>" for item in report.issues)
    toolchain = (
        f"{escape(report.toolchain.kicad_version)} · <code>{escape(report.toolchain.image)}</code>"
        if report.toolchain is not None
        else "Unknown toolchain ID; choose one declared in the project catalog"
    )
    repository = "".join(
        f"<li><code>{escape(path)}</code> · SHA-256 <code>{sha}</code></li>"
        for path, sha in sorted(report.repository_inputs_sha256.items())
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Import review · {escape(report.project_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#263747;background:#f3f6f8}}*{{box-sizing:border-box}}
body{{margin:0}}main{{max-width:1250px;margin:auto;padding:36px 20px 64px}}h1{{font-size:2.1rem}}
section{{background:#fff;border:1px solid #d9e2e8;border-radius:12px;padding:20px;margin:18px 0}}
.notice{{background:#fff2d9;border-left:4px solid #af742d;padding:14px 17px;border-radius:6px}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;vertical-align:top;padding:10px;
border-bottom:1px solid #e2e8ed}}.scroll{{overflow:auto}}code{{font:12px ui-monospace,monospace;
overflow-wrap:anywhere}}p,li,td{{overflow-wrap:anywhere}}li{{margin:8px 0}}a{{color:#166076}}
a:focus-visible{{outline:3px solid #2e8492}}small{{color:#647685}}</style><main>
<header><h1>Import review · {escape(report.project_id)}</h1>
<p><strong>{escape(report.status)}</strong> · {escape(report.source_kind.value if report.source_kind else "unsupported or incomplete design")}
· {len(report.files)} source row(s) · {len(report.dependencies)} CAD reference(s)</p>
<p class="notice">This is a saved preview. No source was copied. A clear preview means the selected
files are importable under the current policy; it does not validate the design or authorize a build.
Reopen or regenerate this review if source or project configuration changes.</p></header>
<section><h2>Selection and toolchain</h2><p>Source: <code>{escape(report.source_project)}</code>
· SHA-256 <code>{report.source_project_sha256 or "unavailable"}</code></p>
<p>Project ID: <code>{escape(report.project_id)}</code> · Destination:
<code>{escape(report.preview.directory)}</code></p><p>Declared toolchain:
<code>{escape(report.toolchain_id)}</code> · {toolchain}</p>
<details><summary>Repository input hashes</summary><ul>{repository}</ul></details></section>
<section><h2>Source files</h2><p>Included files are copied only after a separate import action.
Excluded and missing files stay visible for review.</p><div class="scroll"><table><thead><tr>
<th>Path</th><th>Role</th><th>Disposition</th><th>SHA-256</th><th>Reason</th></tr></thead>
<tbody>{files}</tbody></table></div></section>
<section><h2>CAD libraries and models</h2><p>Versioned KiCad library paths are declared
against the pinned toolchain; their installed contents are checked by the native lane.</p>
<div class="scroll"><table><thead><tr><th>Kind</th><th>Source location</th><th>Reference</th>
<th>State</th><th>Issue</th></tr></thead><tbody>{dependencies}</tbody></table></div></section>
<section><h2>Review actions</h2><ul>{actions}</ul>
<p>Next step from the preview: {escape(report.preview.next_step)}</p>
<p>Apply only after review, with this saved receipt as the expected input. The import
will stop if included source bytes, selected files, exclusions, or configuration changed.</p>
<details><summary>Other issues</summary><ul>{issues}</ul></details></section>
<p><a href="review.json">Structured review and exact saved preview</a></p>
</main></html>"""
