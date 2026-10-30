"""Assess selected engineering receipts without executing their source workflows."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .findings_view_models import FindingsViewReport
from .models import (
    ElectricalAnalysisReport,
    ElectricalChartsReport,
    ProjectVerificationReport,
    PurchasingReport,
    ThreeDReport,
    ValidationSummary,
)
from .native_summary_binding import validate_native_toolchain
from .parts_receipts import read_parts_output_manifest
from .project_models import ProjectKind
from .review_overview_evidence import (
    ReviewContext,
    artifact_issues,
    checked_link,
    dependency_issue,
    read_receipt,
    recorded_directory,
    selected_receipt,
    source_mismatch,
)
from .review_overview_models import OverviewItem, OverviewKind, OverviewLink


def _result(
    context: ReviewContext,
    kind: OverviewKind,
    path: Path,
    report_hash: str,
    status: str,
    *,
    source_hashes: dict[str, str] | None = None,
    source_commit: str | None = None,
    links: tuple[OverviewLink, ...] = (),
    stale: tuple[str, ...] = (),
    unknown: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> OverviewItem:
    report_link = checked_link(context, path, "Selected receipt", report_hash)
    if report_link is None:
        stale = (*stale, "Selected receipt changed during overview creation.")
    else:
        report_link = report_link.model_copy(update={"receipt_bound": False})
    return OverviewItem(
        kind=kind,
        selected_path=path.relative_to(context.root).as_posix(),
        status=status,
        freshness="STALE" if stale else "UNKNOWN" if unknown else "CURRENT",
        report_sha256=report_hash,
        source_commit=source_commit,
        source_hashes=source_hashes or {},
        links=((report_link,) if report_link is not None else ()) + links,
        issues=(*stale, *unknown, *notes),
    )


def _integrity(
    context: ReviewContext, path: Path, recorded: dict[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not recorded:
        return (), ("Receipt has no artifact hash inventory.",)
    if len(recorded) > 2000:
        return (), ("Artifact inventory exceeds the 2000-file review limit.",)
    return artifact_issues(context, path.parent, recorded), ()


def _native(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, ValidationSummary)
    if report.project_id != context.project_id or report.project_kind != context.config.kind:
        raise ValueError("Native receipt identifies a different project or design kind")
    stale: list[str] = []
    unknown: list[str] = []
    source = report.checks.get("source_scope")
    unchanged = report.checks.get("source_unchanged")
    source_hashes = dict(source.source_hashes) if source is not None else {}
    if source is None or unchanged is None or not source_hashes:
        unknown.append("Native receipt has no complete source-scope binding.")
    elif source.status != "PASS" or unchanged.status != "PASS":
        stale.append("Native source scope or unchanged check did not pass.")
    elif unchanged.source_hashes != source_hashes:
        stale.append("Native source-scope and source-unchanged inventories differ.")
    else:
        mismatch = source_mismatch(context, source_hashes, exact_scope=True)
        if mismatch:
            stale.append(mismatch)
    try:
        validate_native_toolchain(report, context.config)
    except ValueError:
        stale.append("Native toolchain no longer matches the selected project.")
    artifact_stale, artifact_unknown = _integrity(context, path, dict(report.artifacts_sha256))
    stale.extend(artifact_stale)
    unknown.extend(artifact_unknown)
    links: list[OverviewLink] = []
    notes: list[str] = []
    for check_name, label in (("schematic_svg", "Schematic"), ("pcb_svg", "PCB")):
        required = (
            context.config.kind is not ProjectKind.PCB_ONLY
            if check_name == "schematic_svg"
            else context.config.kind in {ProjectKind.PCB, ProjectKind.PCB_ONLY}
        )
        check = report.checks.get(check_name)
        if required and (check is None or check.status != "PASS" or not check.files):
            notes.append(f"{label} drawing is not available from a passing native export.")
        if check is None or check.status != "PASS":
            continue
        for name in check.files:
            expected = report.artifacts_sha256.get(name)
            if expected is None or not name.endswith(".svg"):
                stale.append(f"{label} drawing is not bound to a native SVG: {name}")
                continue
            link = checked_link(
                context, repo_path(path.parent, name), f"{label}: {Path(name).name}", expected
            )
            if link is not None:
                links.append(link)
    return _result(
        context,
        "native",
        path,
        checksum,
        report.status,
        source_hashes=source_hashes,
        source_commit=report.checked_commit,
        links=tuple(links),
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=tuple(notes),
    )


def _findings(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, FindingsViewReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.output_directory, path.parent
    ):
        raise ValueError("Findings receipt has a different project or output directory")
    stale: list[str] = []
    unknown: list[str] = []
    if report.source_hashes:
        mismatch = source_mismatch(context, report.source_hashes, exact_scope=True)
        if mismatch:
            stale.append(mismatch)
    else:
        unknown.append("Findings receipt has no source hashes.")
    for value, expected in (
        (report.native_summary, report.native_summary_sha256),
        (report.lint_report, report.lint_report_sha256),
    ):
        if value is not None and expected is not None:
            issue = dependency_issue(context, value, expected)
            if issue:
                stale.append(issue)
    if not any("Referenced receipt" in issue for issue in stale):
        try:
            native_path = selected_receipt(
                context.root, Path(report.native_summary), "summary.json"
            )
            native = _native(context, native_path)
            if native.freshness != "CURRENT":
                stale.append(
                    "Underlying native receipt is no longer current: " + "; ".join(native.issues)
                )
        except (OSError, ValueError):
            stale.append("Underlying native receipt could not be rechecked.")
    artifact_stale, artifact_unknown = _integrity(context, path, dict(report.artifacts_sha256))
    stale.extend(artifact_stale)
    unknown.extend(artifact_unknown)
    index = checked_link(
        context,
        path.parent / "index.html",
        "Open findings explorer",
        report.artifacts_sha256.get("index.html"),
    )
    if index is None:
        stale.append("Findings explorer page changed or is missing.")
    return _result(
        context,
        "findings",
        path,
        checksum,
        f"Native {report.native_status}; lint {report.lint_status}",
        source_hashes=dict(report.source_hashes),
        links=(index,) if index is not None else (),
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=report.issues,
    )


def _parts(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, PurchasingReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.receipt_dir, path.parent
    ):
        raise ValueError("Parts receipt has a different project or output directory")
    stale: list[str] = []
    unknown: list[str] = []
    if report.source_hashes:
        mismatch = source_mismatch(context, report.source_hashes, exact_scope=True)
        if mismatch:
            stale.append(mismatch)
    else:
        unknown.append("Parts receipt has no source hashes.")
    if report.input_hashes:
        mismatch = source_mismatch(context, report.input_hashes, exact_scope=False)
        if mismatch:
            stale.append(mismatch)
    else:
        unknown.append("Parts receipt has no input hashes.")
    if report.netlist_sha256:
        if (
            checked_link(
                context, path.parent / "netlist.xml", "Retained netlist", report.netlist_sha256
            )
            is None
        ):
            stale.append("Retained parts netlist changed or is missing.")
    else:
        unknown.append("Parts receipt has no retained netlist hash.")
    manifest_path = path.parent / "parts-artifacts.json"
    manifest_present = manifest_path.exists() or manifest_path.is_symlink()
    recorded: dict[str, str] = {}
    if manifest_present:
        try:
            manifest = read_parts_output_manifest(path.parent, checksum)
        except (OSError, ValueError):
            stale.append("Parts output manifest is invalid or no longer binds the report.")
        else:
            if manifest is not None:
                recorded = dict(manifest.artifacts_sha256)
                artifact_stale, artifact_unknown = _integrity(context, path, recorded)
                stale.extend(artifact_stale)
                unknown.extend(artifact_unknown)
                for name in ("index.html", "report.txt", *report.artifacts):
                    if name not in recorded:
                        stale.append(f"Parts output has no recorded hash: {name}")
    else:
        unknown.append(
            "Parts HTML and CSV outputs have no saved artifact hashes; links are snapshot-only."
        )
    links: list[OverviewLink] = []
    for name, label in (
        ("index.html", "Open parts checklist"),
        *((item, item) for item in report.artifacts),
    ):
        if manifest_present and name not in recorded:
            continue
        link = checked_link(context, path.parent / name, label, recorded.get(name))
        if link is None:
            if not manifest_present:
                stale.append(f"Parts output changed or is missing: {name}")
        else:
            links.append(link)
    return _result(
        context,
        "parts",
        path,
        checksum,
        report.status,
        source_hashes=dict(report.source_hashes),
        links=tuple(links),
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=report.issues,
    )


def _three_d(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, ThreeDReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.run_directory, path.parent
    ):
        raise ValueError("3D receipt has a different project or output directory")
    stale: list[str] = []
    unknown: list[str] = []
    expected_board = Path(context.config.project).with_suffix(".kicad_pcb").as_posix()
    if report.board is not None and report.board != expected_board:
        stale.append("3D receipt refers to a different board source.")
    elif report.mode == "generate" and report.board is None:
        unknown.append("3D export has no recorded board source path.")
    if report.source_sha256:
        mismatch = source_mismatch(context, report.source_sha256, exact_scope=False)
        if mismatch:
            stale.append(mismatch)
    else:
        unknown.append("3D receipt has no source hashes.")
    if report.toolchain_id is None or report.kicad_version is None:
        unknown.append("3D receipt has no exact toolchain identity.")
    elif (
        report.toolchain_id != context.config.toolchain_id
        or report.kicad_version != context.config.kicad_version
    ):
        stale.append("3D toolchain identity differs from the current project.")
    artifact_stale, artifact_unknown = _integrity(context, path, dict(report.artifacts_sha256))
    stale.extend(artifact_stale)
    unknown.extend(artifact_unknown)
    links = tuple(
        link
        for name, label in (
            ("index.html", "Open 3D gallery"),
            ("board.glb", "Board GLB"),
            ("board.step", "Board STEP"),
        )
        if (expected := report.artifacts_sha256.get(name)) is not None
        if (link := checked_link(context, path.parent / name, label, expected)) is not None
    )
    return _result(
        context,
        "three_d",
        path,
        checksum,
        report.status,
        source_hashes=dict(report.source_sha256),
        links=links,
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=(f"Model coverage: {report.models.status if report.models else 'NOT_RUN'}",),
    )


def _simulation(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, ElectricalChartsReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.run_directory, path.parent
    ):
        raise ValueError("Charts receipt has a different project or output directory")
    stale: list[str] = []
    unknown: list[str] = []
    source_hashes: dict[str, str] = {}
    commit: str | None = None
    try:
        selected = selected_receipt(context.root, Path(report.source_receipt), "electrical.json")
        if not recorded_directory(context.root, report.source_receipt, selected.parent):
            raise ValueError("Analysis directory is outside the checkout")
        analysis, analysis_hash = read_receipt(selected, ElectricalAnalysisReport)
        if analysis.project_id != context.project_id or not recorded_directory(
            context.root, analysis.run_directory, selected.parent
        ):
            raise ValueError("Analysis receipt identifies a different project or directory")
        if analysis_hash != report.source_report_sha256:
            stale.append("Source analysis receipt changed after chart export.")
        if analysis.source is not None:
            commit = analysis.source.commit
            source_hashes = dict(analysis.source.files_sha256)
        if source_hashes:
            mismatch = source_mismatch(context, source_hashes, exact_scope=False)
            if mismatch:
                stale.append(mismatch)
        else:
            unknown.append("Analysis has no source-file identity.")
        if analysis.input_sha256:
            mismatch = source_mismatch(context, analysis.input_sha256, exact_scope=False)
            if mismatch:
                stale.append(mismatch)
        else:
            unknown.append("Analysis has no input hash inventory.")
        analysis_stale, analysis_unknown = _integrity(
            context, selected, dict(analysis.artifacts_sha256)
        )
        stale.extend(analysis_stale)
        unknown.extend(analysis_unknown)
    except (OSError, ValueError):
        stale.append("Source analysis receipt is missing or unavailable.")
    chart_stale, chart_unknown = _integrity(context, path, dict(report.artifacts_sha256))
    stale.extend(chart_stale)
    unknown.extend(chart_unknown)
    links: list[OverviewLink] = []
    for case in report.cases:
        for name in (case.png, case.svg, case.csv):
            if name is None:
                continue
            expected = report.artifacts_sha256.get(name)
            if expected is None:
                stale.append(f"Chart output has no recorded hash: {name}")
                continue
            link = checked_link(
                context,
                repo_path(path.parent, name),
                f"{case.id}: {Path(name).suffix[1:]}",
                expected,
            )
            if link is not None:
                links.append(link)
    return _result(
        context,
        "simulation",
        path,
        checksum,
        report.status,
        source_hashes=source_hashes,
        source_commit=commit,
        links=tuple(links),
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=(f"Source analysis status: {report.source_analysis_status}",),
    )


def _verification(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, ProjectVerificationReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.run_directory, path.parent
    ):
        raise ValueError("Verification receipt has a different project or output directory")
    return _result(
        context,
        "verification",
        path,
        checksum,
        report.status,
        unknown=(
            "Verification summary has no standalone source hash inventory; inspect its stage receipts.",
        ),
        notes=(f"Depth: {report.depth}", *report.next_actions),
    )


def inspect_receipt(context: ReviewContext, kind: OverviewKind, path: Path) -> OverviewItem:
    """Contain malformed or obsolete receipts to their own overview card."""
    relative = path.relative_to(context.root).as_posix()
    if not path.is_file():
        return OverviewItem(
            kind=kind,
            selected_path=relative,
            status="MISSING",
            freshness="MISSING",
            issues=(f"Selected receipt is missing: {relative}",),
        )
    handlers = {
        "native": _native,
        "findings": _findings,
        "parts": _parts,
        "three_d": _three_d,
        "simulation": _simulation,
        "verification": _verification,
    }
    try:
        return handlers[kind](context, path)
    except (OSError, ValueError, TypeError) as exc:
        return OverviewItem(
            kind=kind,
            selected_path=relative,
            status="UNAVAILABLE",
            freshness="UNAVAILABLE",
            issues=(f"Selected receipt could not be inspected: {exc}",),
        )
