"""Compare one explicitly authored ground domain with source-bound netlist pins."""

from __future__ import annotations

from html import escape
from pathlib import Path
from uuid import uuid4

from .contract_coach import receipt_directory
from .contracts import write_model
from .electrical_view_evidence import load_electrical_view_evidence
from .evidence import digest
from .grounding_models import GroundingAnalysis
from .grounding_view_models import GroundingPinView, GroundingViewReport
from .models import NetlistContract
from .netlist_membership import net_pin_membership


def _pins(
    net: str, declared: tuple[str, ...], observed: NetlistContract | None
) -> tuple[GroundingPinView, ...]:
    return tuple(
        GroundingPinView(
            pin=row.pin,
            expected_net=row.expected_net,
            observed_nets=row.observed_nets,
            status=row.status,
        )
        for row in net_pin_membership(net, declared, observed)
    )


def _html(report: GroundingViewReport) -> str:
    rows = "".join(
        f"<tr class='{escape(item.status.lower())}'><th>{escape(item.pin)}</th>"
        f"<td>{escape(item.expected_net or '—')}</td>"
        f"<td>{escape(', '.join(item.observed_nets) or '—')}</td>"
        f"<td>{escape(item.status)}</td></tr>"
        for item in report.pins
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Grounding view</title>
<style>body{{font:15px system-ui;color:#24344b;background:#f5f7fa;margin:0;padding:2rem}}
main{{max-width:1050px;margin:auto}}section{{background:white;padding:1.4rem;border-radius:12px;margin:1rem 0}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:.7rem;text-align:left;border-bottom:1px solid #dce3ec}}
.match{{background:#e8f6eb}}.unreviewed{{background:#f0f3f7}}
.different,.missing,.unconnected,.ambiguous,.undeclared{{background:#fff4df}}
.scroll{{overflow:auto}}code{{overflow-wrap:anywhere}}</style><main>
<h1>Grounding · {escape(report.net)}</h1>
<p>{escape(report.basis)}</p><p>Observed evidence: {report.observation_status}.
Recorded source against current checkout: {report.source_status}.</p>
<section><h2>Evidence</h2><p>Analysis receipt: <code>{escape(report.source_receipt)}</code></p>
<p>Report SHA-256: <code>{report.source_report_sha256}</code></p>
<p>Requirements SHA-256: <code>{report.requirements_sha256}</code></p>
<p>Netlist evidence report SHA-256: <code>{report.observed_sha256 or "not supplied"}</code></p></section>
<section><h2>Declared and observed pins</h2><div class="scroll"><table><thead><tr>
<th>Pin</th><th>Authored net</th><th>Observed net</th><th>Status</th>
</tr></thead><tbody>{rows}</tbody></table></div></section>
<p>This view compares saved intent and observations. It does not prove physical continuity.</p>
</main></html>"""


def build_grounding_view(
    root: Path, receipt: Path, net: str, output: Path | None = None
) -> GroundingViewReport:
    """Render one selected domain; keep absent native evidence explicit."""
    root = root.resolve()
    evidence = load_electrical_view_evidence(root, receipt)
    if not isinstance(evidence.contract.grounding, GroundingAnalysis):
        raise ValueError("Electrical receipt has no reviewed grounding contract for this project")  # noqa: TRY004
    domains = [domain for domain in evidence.contract.grounding.domains if domain.net == net]
    if len(domains) != 1:
        raise ValueError(f"Select one exact authored ground net; {net!r} is not unique or absent")
    pins = _pins(net, domains[0].pins, evidence.observed)
    directory = receipt_directory(
        root,
        evidence.analysis.project_id,
        output
        or Path("build/grounding-view") / f"{evidence.analysis.project_id}-{uuid4().hex[:12]}",
    )
    view = GroundingViewReport(
        project_id=evidence.analysis.project_id,
        net=net,
        basis=evidence.contract.grounding.basis,
        source_receipt=evidence.report_path.relative_to(root).as_posix(),
        source_report_sha256=evidence.report_sha256,
        requirements_sha256=evidence.requirements_sha256,
        observed_sha256=evidence.observed_sha256,
        observation_status="RETAINED" if evidence.observed is not None else "UNREVIEWED",
        source_status=evidence.source_status,
        pins=pins,
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(_html(view), encoding="utf-8")
    evidence.verify()
    view = view.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "grounding-view.json", view)
    return view
