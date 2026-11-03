"""Compare two named native schematic and PCB populations from saved evidence."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from .artifact_access import artifact_file, read_regular_bytes
from .board_variant_compare_html import render_board_variant_comparison
from .board_variant_compare_models import (
    BoardVariantComparisonReport,
    BoardVariantQuantityChange,
    BoardVariantReferenceChange,
    BoardVariantSide,
    BoardVariantState,
)
from .bom_change import change_state
from .contract_coach import receipt_directory
from .contracts import parse_model_text, write_model
from .cross_probe_variant import VariantObservation, read_variant_observation
from .discovery import load_config
from .evidence import digest
from .findings_view_models import FindingsViewReport
from .models import ValidationSummary
from .native_summary_binding import validate_native_summary_binding
from .project_source_hashes import hash_project_sources as hashes
from .review_overview_evidence import read_receipt, recorded_directory, selected_receipt
from .selection import resolve_project


def _states(observed: VariantObservation) -> dict[str, tuple[str, BoardVariantState]]:
    result: dict[str, tuple[str, BoardVariantState]] = {}
    footprint_assigned = {
        key for key, component in observed.schematic.items() if component.footprint.strip()
    }
    for key in sorted(footprint_assigned | observed.board_all.keys()):
        component = observed.schematic.get(key)
        result[key] = (
            observed.board_all.get(key, observed.schematic_references.get(key, key)),
            BoardVariantState(
                schematic=(
                    "ABSENT"
                    if component is None
                    else "DNP"
                    if key in observed.schematic_dnp
                    else "FITTED"
                ),
                board=(
                    "FITTED"
                    if key in observed.board_fitted
                    else "DNP"
                    if key in observed.board_all
                    else "ABSENT"
                ),
                part_id=component.part_id if component is not None else None,
                value=component.value if component is not None else None,
                footprint=component.footprint if component is not None else None,
            ),
        )
    return result


def _quantities(
    states: dict[str, tuple[str, BoardVariantState]],
) -> tuple[dict[tuple[str, str, str], tuple[str, ...]], tuple[str, ...]]:
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    unresolved: list[str] = []
    for reference, state in states.values():
        if state.board != "FITTED":
            continue
        if (
            state.schematic != "FITTED"
            or state.part_id is None
            or state.value is None
            or state.footprint is None
        ):
            unresolved.append(reference)
            continue
        groups[(state.part_id, state.value, state.footprint)].append(reference)
    return (
        {key: tuple(sorted(refs)) for key, refs in groups.items()},
        tuple(sorted(unresolved)),
    )


def compare_board_variants(
    root: Path,
    project_id: str,
    findings_view: Path,
    before_variant: str,
    after_variant: str,
    output: Path | None = None,
) -> BoardVariantComparisonReport:
    """Compare saved native variant outputs without claiming a purchasing BOM."""
    if before_variant.casefold() == after_variant.casefold():
        raise ValueError("Select two distinct named KiCad variants")
    root = root.resolve()
    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    findings_path = selected_receipt(root, findings_view, "review.json")
    findings, findings_sha = read_receipt(findings_path, FindingsViewReport)
    if (
        findings.project_id != project_id
        or dict(findings.source_hashes) != current
        or not recorded_directory(root, findings.output_directory, findings_path.parent)
    ):
        raise ValueError("Select a current findings view for the same project source")
    summary_path = artifact_file(root, findings.native_summary)
    summary_bytes, _ = read_regular_bytes(summary_path, maximum=8 * 1024 * 1024)
    if digest(summary_path) != findings.native_summary_sha256:
        raise ValueError("Findings native summary changed")
    summary = parse_model_text(summary_bytes.decode("utf-8"), ValidationSummary)
    validate_native_summary_binding(summary, config, current)
    netlist_sha = summary.artifacts_sha256.get("netlist.xml")
    before = read_variant_observation(root, config, current, findings, before_variant, netlist_sha)
    after = read_variant_observation(root, config, current, findings, after_variant, netlist_sha)
    old, new = _states(before), _states(after)
    references = tuple(
        BoardVariantReferenceChange(
            reference=(new.get(key) or old[key])[0],
            change=change_state(
                old[key][1] if key in old else None,
                new[key][1] if key in new else None,
            ),
            before=old[key][1] if key in old else None,
            after=new[key][1] if key in new else None,
        )
        for key in sorted(old.keys() | new.keys())
    )
    old_groups, old_unresolved = _quantities(old)
    new_groups, new_unresolved = _quantities(new)
    quantities = tuple(
        BoardVariantQuantityChange(
            part_id=key[0],
            value=key[1],
            footprint=key[2],
            change=change_state(
                len(old_groups[key]) if key in old_groups else None,
                len(new_groups[key]) if key in new_groups else None,
            ),
            before=len(old_groups.get(key, ())),
            after=len(new_groups.get(key, ())),
            before_references=old_groups.get(key, ()),
            after_references=new_groups.get(key, ()),
        )
        for key in sorted(old_groups.keys() | new_groups.keys())
    )
    issues: list[str] = []
    if old_unresolved or new_unresolved:
        issues.append("Some fitted PCB references lack a matching fitted schematic part identity.")

    def verify_inputs() -> None:
        if (
            hashes(root, config.source_roots) != current
            or load_config(root, project.config) != config
        ):
            raise ValueError("Project source changed during board variant comparison")
        if (
            digest(findings_path) != findings_sha
            or digest(summary_path) != findings.native_summary_sha256
        ):
            raise ValueError("Selected findings evidence changed during board variant comparison")
        if (
            read_variant_observation(root, config, current, findings, before.name, netlist_sha)
            != before
            or read_variant_observation(root, config, current, findings, after.name, netlist_sha)
            != after
        ):
            raise ValueError("Named variant evidence changed during comparison")

    verify_inputs()
    target = output or Path("build/board-variant-comparison") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    report = BoardVariantComparisonReport(
        project_id=project_id,
        findings_view=findings_path.relative_to(root).as_posix(),
        findings_view_sha256=findings_sha,
        lint_report=before.lint_path.relative_to(root).as_posix(),
        lint_report_sha256=before.lint_sha256,
        source_hashes=current,
        before=BoardVariantSide(
            name=before.name,
            evidence_sha256=before.evidence_sha256,
            unresolved_fitted=old_unresolved,
        ),
        after=BoardVariantSide(
            name=after.name,
            evidence_sha256=after.evidence_sha256,
            unresolved_fitted=new_unresolved,
        ),
        references=references,
        quantities=quantities,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_board_variant_comparison(report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "comparison.json", report)
    return report
