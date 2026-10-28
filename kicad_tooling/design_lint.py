"""Run source-bound schematic and mapped PCB design lint with project-owned decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.contracts import repo_path
from .hwrepo.design_lint import inspect_summary, reconcile_design_lint_reports, rule_catalog
from .hwrepo.design_lint_reconciliation_text import reconciliation_text
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.design_lint_rule_models import DesignLintRuleCatalog
from .hwrepo.design_lint_text_report import text_report
from .hwrepo.layout import default_project_root


def catalog_text(catalog: DesignLintRuleCatalog) -> str:
    """Render the packaged rule catalog without requiring project evidence."""
    active_count = sum(item.status == "active" for item in catalog.rules)
    lines = [
        f"Design-lint catalog: schema {catalog.schema_version}, {active_count} active rules",
        f"Catalog SHA-256: {catalog.sha256}",
    ]
    for item in catalog.rules:
        lines.extend(
            (
                "",
                (
                    f"{item.rule_id} — {item.title} [{item.status}; theme {item.theme}; "
                    f"default {item.default_mode}]"
                ),
                f"  Owner: {item.implementation_owner}",
                f"  Predicate: {item.predicate}",
                f"  Evidence: {item.evidence_adapter}",
                f"  KiCad: {'; '.join(item.supported_kicad_versions)}",
                f"  Limits: {' '.join(item.limitations)}",
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", help="Registered pcb or schematic project ID")
    parser.add_argument(
        "--native-summary",
        type=Path,
        help="Source-bound native project summary.json with hashed sibling netlist.xml",
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        help="Project-relative JSON design-lint report to compare with the current result",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="List the packaged design-lint rules without reading project evidence",
    )
    args = parser.parse_args()
    if args.catalog:
        if any(
            value is not None for value in (args.project, args.native_summary, args.baseline_report)
        ):
            parser.error("--catalog cannot be combined with project evidence or --baseline-report")
        catalog = rule_catalog()
        print(catalog.model_dump_json(indent=2) if args.format == "json" else catalog_text(catalog))
        return 0
    if args.project is None or args.native_summary is None:
        parser.error("--project and --native-summary are required unless --catalog is selected")
    root = args.root.resolve()
    summary = (
        args.native_summary if args.native_summary.is_absolute() else root / args.native_summary
    )
    report = inspect_summary(root, args.project, summary)
    if args.baseline_report is not None:
        if args.baseline_report.is_absolute():
            parser.error("--baseline-report must be relative to --root")
        try:
            baseline_path = repo_path(root, args.baseline_report.as_posix())
            baseline = DesignLintReport.model_validate_json(baseline_path.read_bytes())
        except (OSError, ValueError) as exc:
            parser.error(f"Could not read source-bound baseline report: {exc}")
        result = reconcile_design_lint_reports(baseline, report)
        print(
            result.model_dump_json(indent=2)
            if args.format == "json"
            else reconciliation_text(result)
        )
        return 0 if result.status == "UNCHANGED" else 1
    print(report.model_dump_json(indent=2) if args.format == "json" else text_report(report))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
