"""Run source-bound schematic and mapped PCB design lint with project-owned decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.design_lint import inspect_summary, rule_catalog
from .hwrepo.design_lint_rule_models import DesignLintRuleCatalog
from .hwrepo.design_lint_text_report import text_report


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
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", help="Registered pcb or schematic project ID")
    parser.add_argument(
        "--native-summary",
        type=Path,
        help="Source-bound native project summary.json with hashed sibling netlist.xml",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="List the packaged design-lint rules without reading project evidence",
    )
    args = parser.parse_args()
    if args.catalog:
        if args.project is not None or args.native_summary is not None:
            parser.error("--catalog cannot be combined with --project or --native-summary")
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
    print(report.model_dump_json(indent=2) if args.format == "json" else text_report(report))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
