"""Export charts and CSV tables from a saved electrical receipt without simulation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.electrical_charts import build_charts, build_suite
from .hwrepo.models import ElectricalChartsReport, ElectricalChartsSuiteReport


def format_text(report: ElectricalChartsReport | ElectricalChartsSuiteReport) -> str:
    if isinstance(report, ElectricalChartsSuiteReport):
        lines = [f"Electrical charts suite: {report.status}", f"Receipt: {report.run_directory}"]
        lines.extend(f"  {item.project_id}: {item.status} ({item.run_directory})"
                     for item in report.reports)
        return "\n".join(lines)
    lines = [f"Electrical charts: {report.status}", f"Project: {report.project_id}",
             f"Source: {report.source_receipt}", f"Receipt: {report.run_directory}"]
    for item in report.cases:
        suffix = f" — {item.samples} samples, {item.csv}, {item.png}, {item.svg}" if item.csv else f" — {item.detail}"
        lines.append(f"  {item.id}: {item.status}{suffix}")
    if report.grounding_csv:
        lines.append(f"Grounding: {report.grounding_csv}")
    if report.power_csv:
        lines.append(f"Power: {report.power_csv}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--receipt", type=Path, help="Saved build/.../electrical.json or its receipt directory")
    source.add_argument("--suite", type=Path, help="Saved build/... suite JSON from kicad_tooling.ci --electrical")
    parser.add_argument("--output", type=Path, help="New output directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        result = (build_charts(args.root, args.receipt, args.output) if args.receipt is not None
                  else build_suite(args.root, args.suite, args.output))
    except (OSError, ValueError) as exc:
        print(f"Electrical chart export could not finish: {exc}", file=sys.stderr)
        return 2
    print(result.model_dump_json(indent=2) if args.format == "json" else format_text(result))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
