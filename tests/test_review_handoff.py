"""Source-scoped handoffs expose outdated and conflicting reviewer notes."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport, ReviewDrawing
from kicad_tooling.hwrepo.findings_view_svg import prepare_drawing
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.review_handoff import export_review_handoff
from kicad_tooling.hwrepo.review_handoff_models import (
    ReviewerNote,
    ReviewerNotesFile,
    ReviewHandoffReport,
)
from kicad_tooling.hwrepo.review_overview_models import ReviewOverviewReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_verification_history import _fixtures

pytestmark = pytest.mark.template_checkout
OLD = "1" * 64
NEW = "2" * 64


def _notes(root: Path, island: Path, baseline: Path, candidate: Path) -> Path:
    notes = island / "docs/reviewer-notes.json"
    old = digest(baseline)
    new = digest(candidate)
    write_model(
        notes,
        ReviewerNotesFile(
            project_id="controller",
            notes=(
                ReviewerNote(
                    id="old-observation",
                    reviewer="Engineer A",
                    recorded_at="2026-10-29T10:00:00Z",
                    snapshot="baseline",
                    overview_sha256=old,
                    finding_fingerprint=OLD,
                    assessment="observation",
                    text="Check the return path.",
                ),
                ReviewerNote(
                    id="new-question",
                    reviewer="Engineer B",
                    recorded_at="2026-10-30T10:00:00Z",
                    snapshot="candidate",
                    overview_sha256=new,
                    finding_fingerprint=NEW,
                    assessment="needs_review",
                    text="Confirm this net assignment.",
                ),
                ReviewerNote(
                    id="new-resolved-claim",
                    reviewer="Engineer C",
                    recorded_at="2026-10-30T11:00:00Z",
                    snapshot="candidate",
                    overview_sha256=new,
                    finding_fingerprint=NEW,
                    assessment="resolved_claim",
                    text="I think this is resolved.",
                ),
                ReviewerNote(
                    id="old-receipt",
                    reviewer="Engineer D",
                    recorded_at="2026-10-30T12:00:00Z",
                    snapshot="candidate",
                    overview_sha256="0" * 64,
                    finding_fingerprint=NEW,
                    assessment="observation",
                    text="Old copy of the candidate.",
                ),
                ReviewerNote(
                    id="old-fingerprint",
                    reviewer="Engineer E",
                    recorded_at="2026-10-30T13:00:00Z",
                    snapshot="candidate",
                    overview_sha256=new,
                    finding_fingerprint=OLD,
                    assessment="observation",
                    text="Finding moved or changed.",
                ),
            ),
        ),
    )
    return notes


def test_two_revisions_conflicts_and_outdated_note_scope(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    notes = _notes(root, island, baseline, candidate)
    report = export_review_handoff(
        root,
        "controller",
        baseline,
        candidate,
        notes,
        (OLD, NEW),
        Path("build/review-handoff/control"),
    )
    assert report.baseline.identity.source_relation == "HISTORICAL"
    assert report.candidate.identity.source_relation == "CURRENT"
    assert {(item.snapshot, item.fingerprint) for item in report.findings} == {
        ("baseline", OLD),
        ("candidate", NEW),
    }
    states = {item.note.id: (item.state, item.conflict) for item in report.notes}
    assert states == {
        "old-observation": ("CURRENT", False),
        "new-question": ("CURRENT", True),
        "new-resolved-claim": ("CURRENT", True),
        "old-receipt": ("OUTDATED_RECEIPT", False),
        "old-fingerprint": ("OUTDATED_FINGERPRINT", False),
    }
    assert not report.build_authorized
    output = Path(report.output_directory)
    assert read_model(output / "handoff.json", ReviewHandoffReport) == report
    assert (output / "baseline/review.json").is_file()
    assert (output / "candidate/review.json").is_file()
    assert (output / "notes.json").read_bytes() == notes.read_bytes()
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "CONFLICT" in html and "OUTDATED_FINGERPRINT" in html
    for name, checksum in report.artifacts_sha256.items():
        assert digest(output / name) == checksum


def test_missing_findings_evidence_keeps_notes_unavailable(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    notes = _notes(root, island, baseline, candidate)
    old = read_model(baseline, ReviewOverviewReport)
    selected = next(item for item in old.items if item.kind == "findings")
    assert selected.selected_path is not None
    (root / selected.selected_path).unlink()
    report = export_review_handoff(
        root,
        "controller",
        baseline,
        candidate,
        notes,
        (OLD, NEW),
        Path("build/review-handoff/missing"),
    )
    assert report.baseline.findings_integrity == "MISSING"
    assert not any(item.snapshot == "baseline" for item in report.findings)
    assert (
        next(item for item in report.notes if item.note.id == "old-observation").state
        == "UNAVAILABLE"
    )
    assert not (Path(report.output_directory) / "baseline/review.json").exists()


def test_verified_drawing_link_and_missing_drawing(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate, _, _ = _fixtures(root)
    overview = read_model(candidate, ReviewOverviewReport)
    selected = next(item for item in overview.items if item.kind == "findings")
    assert selected.selected_path is not None
    review_path = root / selected.selected_path
    source = review_path.parent / "board.svg"
    raw_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        'viewBox="0 0 10 10"><desc>PCBNEW</desc><circle cx="5" cy="5" r="2"/></svg>'
    )
    source.write_bytes(prepare_drawing(raw_svg.encode("utf-8"), "pcb").content)
    findings = read_model(review_path, FindingsViewReport)
    write_model(
        review_path,
        findings.model_copy(
            update={
                "drawings": (
                    ReviewDrawing(
                        kind="pcb",
                        file="board.svg",
                        source_artifact="board-source.svg",
                        sha256=digest(source),
                        width_mm=10,
                        height_mm=10,
                        mapping_supported=True,
                    ),
                ),
                "artifacts_sha256": {"board.svg": digest(source)},
            }
        ),
    )
    write_model(
        candidate,
        overview.model_copy(
            update={
                "items": tuple(
                    item.model_copy(update={"report_sha256": digest(review_path)})
                    if item.kind == "findings"
                    else item
                    for item in overview.items
                )
            }
        ),
    )
    notes = _notes(root, island, baseline, candidate)
    valid = export_review_handoff(
        root,
        "controller",
        baseline,
        candidate,
        notes,
        (NEW,),
        Path("build/review-handoff/drawing"),
    )
    assert any(item.packet_file == "candidate/board.svg" for item in valid.evidence_links), (
        valid.issues
    )
    assert (
        Path(valid.output_directory) / "candidate/board.svg"
    ).read_bytes() == source.read_bytes()
    source.unlink()
    missing = export_review_handoff(
        root,
        "controller",
        baseline,
        candidate,
        notes,
        (NEW,),
        Path("build/review-handoff/drawing-missing"),
    )
    assert any("drawing is missing" in issue for issue in missing.issues)
    assert not any(item.packet_file == "candidate/board.svg" for item in missing.evidence_links)


class _HandoffParity(McpParityHarness):
    async def _case_test_cli_mcp_review_handoff_parity(self) -> None:
        baseline, candidate, _, _ = _fixtures(self.root)
        notes = _notes(self.root, self.island, baseline, candidate)
        cli = await self.cli(
            "kicad_tooling.review_handoff",
            ReviewHandoffReport,
            "--project",
            "controller",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--notes",
            str(notes),
            "--fingerprint",
            OLD,
            "--fingerprint",
            NEW,
            "--output",
            "build/review-handoff/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "baseline": baseline.relative_to(self.root).as_posix(),
            "candidate": candidate.relative_to(self.root).as_posix(),
            "notes": notes.relative_to(self.root).as_posix(),
            "fingerprints": [OLD, NEW],
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("export_review_handoff_packet", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_review_handoff_packet", ReviewHandoffReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_review_handoff_parity() -> None:
    run_mcp_parity(_HandoffParity, "_case_test_cli_mcp_review_handoff_parity")
