"""Offline, escaped tables for two selected verification snapshots."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .contracts import relative_path_from, repo_path
from .verification_history_models import (
    HistoryArtifact,
    HistoryEvidence,
    HistoryRelease,
    HistorySnapshot,
    VerificationHistoryReport,
)


def _href(root: Path, output: Path, path: str) -> str:
    target = repo_path(root, path)
    return escape(quote(relative_path_from(target, output).as_posix(), safe="/.-_"), quote=True)


def _snapshot(
    root: Path, output: Path, title: str, snapshot: HistorySnapshot, release: HistoryRelease
) -> str:
    issues = "".join(f"<li>{escape(item)}</li>" for item in (*snapshot.issues, *release.issues))
    release_text = (
        f"{escape(release.release_id or 'unknown')} · authored status {escape(release.status)} · "
        f"commit relation {escape(release.source_relation)}"
        if release.manifest is not None
        else "No release manifest selected"
    )
    return (
        '<article class="card">'
        f"<h2>{escape(title)}</h2>"
        f'<p><a href="{_href(root, output, snapshot.overview)}">Selected overview</a> · '
        f"SHA-256 <code>{snapshot.overview_sha256}</code></p>"
        f"<p>Source: <strong>{escape(snapshot.source_relation)}</strong> · "
        f"{len(snapshot.source_hashes)} files · inventory <code>{snapshot.source_fingerprint}</code></p>"
        f"<p>Recorded commit: <code>{escape(snapshot.source_commit or 'unknown')}</code></p>"
        f"<p>Project manifest SHA-256: <code>{snapshot.project_manifest_sha256}</code></p>"
        f"<p>Release: {release_text}</p>" + (f"<ul>{issues}</ul>" if issues else "") + "</article>"
    )


def _evidence(item: HistoryEvidence) -> str:
    return (
        f"{escape(item.status)} · captured {escape(item.captured_freshness)} · "
        f"now {escape(item.integrity)}"
        + (f" · <code>{escape(item.selected_path)}</code>" if item.selected_path else "")
        + (f"<small>{escape('; '.join(item.issues))}</small>" if item.issues else "")
    )


def _artifact(item: HistoryArtifact | None) -> str:
    if item is None:
        return "—"
    return (
        f"{escape(item.kind)} · {escape(item.integrity)} · "
        f"<code>{escape(item.path)}</code> · SHA-256 <code>{item.sha256}</code>"
    )


def _table(title: str, headings: tuple[str, ...], rows: str, empty: str) -> str:
    header = "".join(f"<th>{escape(item)}</th>" for item in headings)
    body = rows or f'<tr><td colspan="{len(headings)}" class="muted">{escape(empty)}</td></tr>'
    return (
        f"<section><h2>{escape(title)}</h2><div class='scroll'><table>"
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div></section>"
    )


def render_verification_history(root: Path, report: VerificationHistoryReport) -> str:
    """Render a static review page without implying a historical check is current."""
    output = Path(report.output_directory)
    evidence_rows = "".join(
        f"<tr><th>{escape(item.kind)}</th><td>{escape(item.change)}</td>"
        f"<td>{_evidence(item.before)}</td><td>{_evidence(item.after)}</td></tr>"
        for item in report.evidence_changes
    )
    source_rows = "".join(
        f"<tr><th><code>{escape(item.path)}</code></th><td>{escape(item.change)}</td>"
        f"<td><code>{item.before_sha256 or '—'}</code></td>"
        f"<td><code>{item.after_sha256 or '—'}</code></td></tr>"
        for item in report.source_changes
        if item.change != "UNCHANGED"
    )
    check_rows = "".join(
        f"<tr><th>{escape(item.name)}</th><td>{escape(item.before)}</td>"
        f"<td>{escape(item.after)}</td><td>{escape(item.detail)}</td></tr>"
        for item in report.check_changes
    )
    finding_rows = "".join(
        f"<tr><th>{escape(item.origin)} · {escape(item.rule)} · {escape(item.title)}</th>"
        f"<td>{escape(item.change)}</td>"
        f"<td><code>{item.before_fingerprint or '—'}</code></td>"
        f"<td><code>{item.after_fingerprint or '—'}</code></td>"
        f"<td>{escape(item.explanation)}</td></tr>"
        for item in report.finding_changes
    )
    artifact_rows = "".join(
        f"<tr><th>{escape(item.id)}</th><td>{escape(item.change)}</td>"
        f"<td>{_artifact(item.before)}</td><td>{_artifact(item.after)}</td></tr>"
        for item in report.artifact_changes
    )
    missing_findings = next(item for item in report.evidence_changes if item.kind == "findings")
    finding_empty = (
        "Finding comparison unavailable because one selected findings receipt is missing, stale, or not selected."
        if missing_findings.before.integrity != "CURRENT"
        or missing_findings.after.integrity != "CURRENT"
        else "No findings in either selected receipt."
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verification history · {escape(report.project_id)}</title>
<style>:root{{font:15px/1.5 system-ui;color:#203145;background:#f3f6f9}}*{{box-sizing:border-box}}
body{{margin:0}}main{{max-width:1250px;margin:auto;padding:36px 20px 65px}}h1{{font-size:2.2rem}}
section,.card{{background:white;padding:20px;margin:16px 0;border:1px solid #d8e1e8;border-radius:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}}
.grid .card{{margin:0}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;
padding:10px;border-bottom:1px solid #e2e8ee;min-width:120px}}th{{font-weight:650}}.scroll{{overflow:auto}}
code{{font:12px ui-monospace,monospace;overflow-wrap:anywhere}}td,li,p{{overflow-wrap:anywhere}}
small{{display:block;color:#667888}}.muted{{color:#657587}}a{{color:#126477}}a:focus-visible{{outline:3px solid #318e9c}}
</style><main><header><h1>Verification history · {escape(report.project_id)}</h1>
<p>Two explicitly selected saved overviews. CURRENT describes the live checkout at export time;
HISTORICAL does not apply to the live source. Saved check results are not rerun here.</p>
<p><a href="history.json">Structured comparison</a> · Review only; no engineering or release approval.</p>
</header><div class="grid">
{_snapshot(root, output, "Baseline", report.baseline, report.baseline_release)}
{_snapshot(root, output, "Candidate", report.candidate, report.candidate_release)}</div>
{_table("Selected evidence", ("Area", "Change", "Baseline", "Candidate"), evidence_rows, "No evidence selected.")}
{_table("Changed source bytes", ("Path", "Change", "Baseline SHA-256", "Candidate SHA-256"), source_rows, "Source inventories match.")}
{_table("Native checks", ("Check", "Baseline", "Candidate", "Detail"), check_rows, "No native checks are available in either selected snapshot.")}
{_table("Findings", ("Finding", "Change", "Baseline fingerprint", "Candidate fingerprint", "Explanation"), finding_rows, finding_empty)}
{_table("Declared release artifacts", ("Artifact ID", "Change", "Baseline", "Candidate"), artifact_rows, "No release artifacts were selected.")}
<p class="muted">A missing or changed findings report does not mean a finding was resolved.
Release manifests and their artifact availability are displayed separately from approval and packaging.</p>
</main></html>"""
