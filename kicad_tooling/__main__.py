"""Run the KiCad project CLI from any project checkout."""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import PackageNotFoundError

from kicad_tooling import package_version

COMMANDS = (
    "assembly_review",
    "bom_compare",
    "check_all",
    "check_toolchain",
    "ci",
    "ci_hosted",
    "ci_matrix",
    "contract_coach",
    "cross_probe",
    "design_lint",
    "docs_policy",
    "electrical",
    "electrical_charts",
    "fault_probe",
    "findings_view",
    "governance_audit",
    "grounding_view",
    "hardware",
    "impact",
    "import_review",
    "lint_registry",
    "mcp",
    "metrics",
    "measured_series",
    "measured_comparison",
    "native_deps",
    "parts",
    "physical_voltage",
    "power_tree_view",
    "product_visual",
    "product_variant_bom",
    "release",
    "review_handoff",
    "review_overview",
    "sourcing",
    "surface",
    "supplier_analysis",
    "template",
    "validate",
    "verify",
    "verification_history",
    "visualize",
)


def main() -> int:
    if sys.argv[1:] == ["--version"]:
        try:
            print(f"kicad-team-tooling {package_version()}")
        except PackageNotFoundError:
            print("Package version unavailable: install kicad-team-tooling first.", file=sys.stderr)
            return 1
        return 0
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: kicad-team COMMAND [options]\n")
        print("Commands: " + ", ".join(COMMANDS))
        print("Run 'kicad-team COMMAND --help' for command options.")
        print("Run 'kicad-team --version' for the installed tooling version.")
        return 0 if len(sys.argv) > 1 else 2
    command = sys.argv[1].replace("-", "_")
    if command not in COMMANDS:
        print(f"Unknown command: {sys.argv[1]}", file=sys.stderr)
        return 2
    sys.argv = [f"kicad-team {command}", *sys.argv[2:]]
    module = importlib.import_module(f"kicad_tooling.{command}")
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
