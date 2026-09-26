"""Run real KiCad against disposable broken fixture copies; never edit tracked source."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from .hwrepo.contracts import write_model
from .hwrepo.models import FaultProbeCase, FaultProbeReport
from .hwrepo.repository import ephemeral
from .validate import validate


def probe(root: Path, output: Path) -> FaultProbeReport:
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows: list[FaultProbeCase] = []
    for name in (
        "malformed_pcb",
        "missing_library",
        "erc_open_pin",
        "drc_unrouted",
        "parity_value",
        "missing_tool",
        "unknown_board",
    ):
        with tempfile.TemporaryDirectory(prefix="kicad-negative-") as temp:
            copy: Path = Path(temp)

            # Copy policy/catalog dependencies too, otherwise a missing preflight
            # dependency masks the intended ERC/DRC defect.
            def ignored(directory: str, names: list[str]) -> set[str]:
                return {
                    item
                    for item in names
                    if item == ".git"
                    or ephemeral(item)
                    or (
                        Path(directory) == root
                        and item in {"projects", "products", "libraries", "generated", "schemas"}
                    )
                }

            shutil.copytree(root, copy, dirs_exist_ok=True, ignore=ignored)
            # Deliberate defects belong to the reference fixture, independently
            # of an adopter's active projects, libraries and product catalogs.
            shutil.copytree(root / "examples/catalog", copy / "catalog", dirs_exist_ok=True)
            subprocess.run(("git", "init", "-q", str(copy)), check=True, capture_output=True)
            board: Path = copy / "examples/projects/controller/kicad/controller.kicad_pcb"
            sch: Path = copy / "examples/projects/controller/kicad/controller.kicad_sch"
            cli: str = "kicad-cli"
            expected: str = "preflight"
            if name == "malformed_pcb":
                board.write_text("This is not a KiCad PCB.\n")
                expected = "drc"
            elif name == "missing_library":
                (copy / "examples/projects/controller/kicad/Pilot.kicad_sym").unlink()
            elif name == "erc_open_pin":
                text: str = sch.read_text()
                if "(xy 76.2 71.12)" not in text:
                    raise ValueError("Open-pin mutation anchor missing")
                sch.write_text(text.replace("(xy 76.2 71.12)", "(xy 78.74 71.12)", 1))
                expected = "erc"
            elif name == "drc_unrouted":
                text, count = re.subn(
                    r"  \(segment \(start 100 100\)[^\n]*\)\n", "", board.read_text(), count=1
                )
                if count != 1:
                    raise ValueError("Track mutation anchor missing")
                board.write_text(text)
                expected = "drc"
            elif name == "parity_value":
                text = board.read_text()
                if '(property "Value" "1k"' not in text:
                    raise ValueError("Parity mutation anchor missing")
                board.write_text(
                    text.replace('(property "Value" "1k"', '(property "Value" "999k"', 1)
                )
                expected = "drc"
            elif name == "missing_tool":
                cli = "intentionally-missing-kicad-executable"
            else:
                # Selected checks reject undeclared sources inside their own
                # island; unrelated islands are intentionally outside scope.
                (copy / "examples/projects/controller/kicad/ghost.kicad_pro").write_text("{}\n")
                (copy / "examples/projects/controller/kicad/ghost.kicad_pcb").write_text(
                    "undeclared board\n"
                )
            report = validate(copy, output / name, cli)
            observed = report.checks.get(expected)
            passed = report.status == "FAIL" and observed is not None and observed.status == "FAIL"
            if name in {"erc_open_pin", "drc_unrouted", "parity_value"}:
                passed = passed and observed is not None and observed.returncode == 5
            if name == "parity_value" and (output / name / "drc.json").exists():
                raw: object = json.loads((output / name / "drc.json").read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    report_data = cast(Mapping[str, object], raw)
                    passed = passed and bool(report_data.get("schematic_parity"))
                else:
                    passed = False
            rows.append(
                FaultProbeCase(
                    id=name,
                    status="PASS" if passed else "FAIL",
                    expected_failing_check=expected,
                    observed_status=None if observed is None else observed.status,
                    observed_returncode=None if observed is None else observed.returncode,
                )
            )
    result = FaultProbeReport(
        cases=tuple(rows),
        status="PASS" if all(row.status == "PASS" for row in rows) else "FAIL",
    )
    write_model(output / "fault-summary.json", result)
    return result


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args: argparse.Namespace = parser.parse_args()
    result = probe(Path.cwd(), args.output.resolve())
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
