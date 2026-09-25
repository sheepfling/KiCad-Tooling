"""Run the KiCad project CLI from any project checkout."""
from __future__ import annotations

import importlib
import sys

COMMANDS = (
    "check_all", "check_toolchain", "ci", "ci_hosted", "ci_matrix", "contract_coach",
    "docs_policy", "electrical", "electrical_charts", "fault_probe", "governance_audit",
    "hardware", "impact", "lint_registry", "mcp", "metrics", "native_deps", "parts",
    "release", "sourcing", "surface", "template", "validate", "verify", "visualize",
)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: kicad-team COMMAND [options]\n")
        print("Commands: " + ", ".join(COMMANDS))
        print("Run 'kicad-team COMMAND --help' for command options.")
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
