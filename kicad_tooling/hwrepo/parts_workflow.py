"""Source-bound parts planning and fresh, local purchasing review receipts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .contract_coach import NetlistRunner, capture, inspect_summary, project_context
from .contracts import read_model, repo_path, write_model
from .discovery import load_registry
from .evidence import digest
from .layout import CONFIG_NAME, layout
from .models import (
    PartsCatalog,
    ProjectManifest,
    ProjectRecord,
    PurchasingPreferences,
    PurchasingReport,
)
from .purchasing import plan, read_components, write_csvs


def selected_project(root: Path, project_id: str) -> ProjectRecord:
    project = next((p for p in load_registry(root).projects if p.id == project_id), None)
    if project is None:
        raise ValueError(
            f"Unknown project {project_id!r}; run kicad_tooling.template list --format text"
        )
    return project


def local_path(root: Path, path: Path) -> Path:
    relative = path.relative_to(root) if path.is_absolute() else path
    return repo_path(root, relative.as_posix())


def preferences_path(root: Path, project_id: str, requested: Path | None) -> Path:
    project = selected_project(root, project_id)
    default = Path(project.config).parent / "docs/purchasing.json"
    return local_path(root, default if requested is None else requested)


def load_preferences(
    root: Path,
    project_id: str,
    requested: Path | None,
    boards: int | None,
    spare_percent: int | None,
    spare_minimum: int | None,
) -> PurchasingPreferences:
    path = preferences_path(root, project_id, requested)
    saved = (
        read_model(path, PurchasingPreferences)
        if requested is not None or path.exists()
        else PurchasingPreferences()
    )
    return PurchasingPreferences(
        boards=saved.boards if boards is None else boards,
        spare_percent=saved.spare_percent if spare_percent is None else spare_percent,
        spare_minimum=saved.spare_minimum if spare_minimum is None else spare_minimum,
        digikey_skus=saved.digikey_skus,
    )


def init_preferences(
    root: Path,
    project_id: str,
    requested: Path,
    preferences: PurchasingPreferences,
) -> Path:
    """Create editable defaults only within the selected island's authored docs."""
    root = root.resolve()
    project = selected_project(root, project_id)
    path = local_path(root, requested)
    docs = repo_path(root, (Path(project.config).parent / "docs").as_posix())
    if not path.is_relative_to(docs) or path.suffix != ".json":
        raise ValueError("Save preferences as a new .json file under the selected project's docs/")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(preferences.model_dump_json(indent=2) + "\n")
    return path


def new_receipt(root: Path, project_id: str, requested: Path | None) -> Path:
    """Keep reports separate from authored source; never reuse an old directory."""
    if requested is not None:
        output = local_path(root, requested)
        if not output.is_relative_to(root / "build") or output == root / "build":
            raise ValueError("Parts receipts must use a fresh directory below ignored build/")
        output.mkdir(parents=True, exist_ok=False)
        return output
    # Validate identity before using it as a temporary-directory prefix.
    selected_project(root, project_id)
    parent = repo_path(root, "build/parts")
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{project_id}-", dir=parent))


def input_hashes(root: Path, project_id: str, requested: Path | None) -> dict[str, str]:
    registry = load_registry(root)
    project = selected_project(root, project_id)
    # Config includes independent contract and toolchain/catalog references; bind them
    # in addition to the native design hashes supplied by the capture adapter.
    manifest = read_model(repo_path(root, project.config), ProjectManifest)
    checks = repo_path(root, project.config).parent / manifest.checks
    paths = {
        layout(root).discovery,
        registry.catalogs.parts,
        registry.catalogs.toolchains,
        project.config,
        checks.relative_to(root).as_posix(),
    }
    if repo_path(root, CONFIG_NAME).exists():
        paths.add(CONFIG_NAME)
    path = preferences_path(root, project_id, requested)
    if path.exists():
        paths.add(path.relative_to(root).as_posix())
    return {name: digest(repo_path(root, name)) for name in sorted(paths)}


def prepare(
    root: Path,
    project_id: str,
    output: Path,
    runner: NetlistRunner,
    native_summary: Path | None = None,
    requested_preferences: Path | None = None,
    boards: int | None = None,
    spare_percent: int | None = None,
    spare_minimum: int | None = None,
) -> PurchasingReport:
    """Inspect a saved design and explicit identities without selecting substitutes."""
    root = root.resolve()
    evidence = None
    before: dict[str, str] = {}
    try:
        output = local_path(root, output)
        if (
            not output.is_relative_to(root / "build")
            or output == root / "build"
            or not output.is_dir()
            or any(output.iterdir())
        ):
            raise ValueError("Parts planning requires a new empty receipt directory under build/")
        project = selected_project(root, project_id)
        before = input_hashes(root, project_id, requested_preferences)
        preferences = load_preferences(
            root,
            project_id,
            requested_preferences,
            boards,
            spare_percent,
            spare_minimum,
        )
        if native_summary is None:
            evidence = capture(root, project_id, output, runner)
            netlist = output / "netlist.xml"
        else:
            summary = native_summary if native_summary.is_absolute() else root / native_summary
            evidence = inspect_summary(root, project_id, summary)
            netlist = (summary if summary.is_dir() else summary.parent) / "netlist.xml"
        if evidence.status != "READY_FOR_REVIEW":
            raise ValueError("; ".join(evidence.issues))
        if digest(netlist) != evidence.netlist_sha256:
            raise ValueError("Netlist changed after evidence verification; capture again")
        components = read_components(netlist)
        registry = load_registry(root)
        catalog = read_model(repo_path(root, registry.catalogs.parts), PartsCatalog)
        purchase_plan = plan(components, catalog, preferences, project.component_identity.part_ids)
        _, _, current = project_context(root, project_id)
        if (
            current != evidence.source_hashes
            or before
            != input_hashes(
                root,
                project_id,
                requested_preferences,
            )
            or digest(netlist) != evidence.netlist_sha256
        ):
            raise ValueError("Design, catalog or preferences changed during planning; rerun")
        # Preserve the inspected bytes when using an external native receipt.
        if native_summary is not None:
            (output / "netlist.xml").write_bytes(netlist.read_bytes())
            if digest(output / "netlist.xml") != evidence.netlist_sha256:
                raise ValueError("Netlist changed while saving the receipt; rerun")
        artifacts = write_csvs(output, purchase_plan)
        actions = (
            "Open index.html for component details and the next repair steps.",
            (
                f"Choose reviewed part/footprint/model bindings with: python -B -m kicad_tooling.parts "
                f"--project {project_id} --picker. Keep approved identities in the part catalog."
            ),
            (
                "Rerun this command after saving changes. Review supplier matches, packaging, "
                "stock and price in DigiKey myLists before ordering."
            ),
        )
        return PurchasingReport(
            project_id=project_id,
            status=purchase_plan.status,
            plan=purchase_plan,
            input_hashes=before,
            source_hashes=evidence.source_hashes,
            netlist_sha256=evidence.netlist_sha256,
            native_status=evidence.native_status,
            selected_runner=evidence.selected_runner,
            evidence=evidence,
            receipt_dir=str(output),
            artifacts=artifacts,
            next_actions=actions,
        )
    except (OSError, ValueError, TypeError) as exc:
        return PurchasingReport(
            project_id=project_id,
            status="BLOCKED",
            receipt_dir=str(output),
            input_hashes=before,
            evidence=evidence,
            issues=(str(exc),),
            next_actions=(
                "Fix the input or runner problem above and rerun kicad_tooling.parts.",
                (
                    f"Check the runner with: python -B -m kicad_tooling.template doctor --native "
                    f"--project-id {project_id} --format text"
                ),
            ),
        )


def text_report(report: PurchasingReport) -> str:
    lines = [f"Parts to order: {report.status}", f"Project: {report.project_id}"]
    if report.plan is not None:
        p = report.plan.preferences
        lines.append(
            f"Build: {p.boards} board(s); spares: {p.spare_percent}% or at least "
            f"{p.spare_minimum} per part (whichever is larger)"
        )
        lines.append(
            f"Purchasing groups: {len(report.plan.lines)}; excluded references: "
            f"{len(report.plan.excluded_references)}; issues: {len(report.plan.findings)}"
        )
        for finding in report.plan.findings[:8]:
            refs = ", ".join(finding.references)
            lines.append(
                f"- {finding.code}{' (' + refs + ')' if refs else ''}: "
                f"{finding.message} {finding.action}"
            )
        if len(report.plan.findings) > 8:
            lines.append("See index.html or report.json for all component findings.")
    lines.extend(f"Blocked: {issue}" for issue in report.issues)
    lines.extend(f"Next: {action}" for action in report.next_actions)
    lines.extend(
        (
            f"Review page: {report.receipt_dir}/index.html",
            f"Receipt: {report.receipt_dir}",
            (
                "Metadata review only; electrical validation, live sourcing and purchasing "
                "approval remain separate."
            ),
        )
    )
    return "\n".join(lines)


def save_report(output: Path, report: PurchasingReport) -> None:
    from .parts_view import render_html

    write_model(output / "report.json", report)
    (output / "report.txt").write_text(text_report(report) + "\n", encoding="utf-8")
    (output / "index.html").write_text(render_html(report), encoding="utf-8")
