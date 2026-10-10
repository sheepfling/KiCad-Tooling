"""Evaluate the pinned clock-series cohort rule in an isolated environment.

Run this file with the cohort package installed and KICAD_CLI pointing to the
exact native KiCad executable. It is deliberately not a first-party lint rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eda_toolkit import __version__
from eda_toolkit.kicad import kicad_cli, sch_review
from eda_toolkit.kicad.sch_review import ReviewContext, rule_clock_series_resistor

EXPECTED_COMMIT = "53d1af8bc550f60415b4b8e51a6d2d5924ada03f"
EXPECTED_MODULE_SHA256 = "fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54"
EXPECTED_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
EXPECTED_NATIVE_KICAD_VERSION = "10.0.6"
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/design_lint/cohort-clock-series-native"
DEFAULT_REPORT = REPO_ROOT / "build/cohort-trials/kicad-skills-clock-native/report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inspect_rows() -> list[dict[str, object]]:
    expectations = json.loads((FIXTURE_ROOT / "expectations.json").read_text(encoding="utf-8"))
    expected_cases = expectations["cases"]
    fixtures = sorted(FIXTURE_ROOT.glob("*.kicad_sch"))
    if {path.stem for path in fixtures} != set(expected_cases):
        raise ValueError("clock-series fixtures and expectations.json do not match")

    rows = []
    for path in fixtures:
        context = ReviewContext(path, use_cli=True)
        if context.netlist.get("source") != "kicad-cli":
            raise RuntimeError(f"{path.name}: candidate did not use the native netlist")
        findings = rule_clock_series_resistor(context)
        violations = [
            violation
            for sheet in (context.erc or {}).get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        expected = expected_cases[path.stem]
        rows.append(
            {
                "fixture": path.name,
                "source_sha256": _sha256(path),
                "expected_candidate_finding": expected["candidate_finding"],
                "fixture_disposition": expected["disposition"],
                "observed_candidate_finding": bool(findings),
                "finding_count": len(findings),
                "findings": [
                    {"rule": finding.rule, "location": finding.location, "message": finding.message}
                    for finding in findings
                ],
                "netlist_source": context.netlist["source"],
                "native_erc_errors": sum(v.get("severity") == "error" for v in violations),
                "native_erc_warnings": sum(v.get("severity") == "warning" for v in violations),
            }
        )
    return rows


def evaluate(output: Path) -> int:
    module_path = Path(sch_review.__file__).resolve()
    module_sha256 = _sha256(module_path)
    native_version = kicad_cli.version()
    if module_sha256 != EXPECTED_MODULE_SHA256:
        raise RuntimeError(f"candidate source hash mismatch: {module_sha256}")
    if native_version != EXPECTED_NATIVE_KICAD_VERSION:
        raise RuntimeError(
            f"expected KiCad {EXPECTED_NATIVE_KICAD_VERSION}, found {native_version!r}"
        )

    first = _inspect_rows()
    second = _inspect_rows()
    canonical = lambda rows: json.dumps(rows, sort_keys=True, separators=(",", ":"))
    repeatable = canonical(first) == canonical(second)
    matches = all(
        row["expected_candidate_finding"] == row["observed_candidate_finding"] for row in first
    )
    clean_erc = all(row["native_erc_errors"] == 0 for row in first)
    report = {
        "candidate_repository": "https://github.com/sabas0ba/kicad_skills",
        "candidate_commit": EXPECTED_COMMIT,
        "candidate_package": "eda-toolkit",
        "candidate_package_version": __version__,
        "candidate_module_sha256": module_sha256,
        "candidate_license_sha256": EXPECTED_LICENSE_SHA256,
        "native_kicad_version": native_version,
        "repeatable_targeted_findings": repeatable,
        "expected_matches": sum(
            row["expected_candidate_finding"] == row["observed_candidate_finding"] for row in first
        ),
        "case_count": len(first),
        "native_erc_error_free": clean_erc,
        "rows": first,
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    (output.parent / "report.sha256").write_text(
        hashlib.sha256(payload.encode("utf-8")).hexdigest() + "\n", encoding="ascii"
    )

    print(
        f"cases={len(first)} matches={report['expected_matches']} "
        f"repeatable={repeatable} native={native_version} erc_errors_free={clean_erc}"
    )
    for row in first:
        print(
            f"{row['fixture']}: findings={row['finding_count']} "
            f"erc_errors={row['native_erc_errors']} intent={row['fixture_disposition']}"
        )
    print(f"report={output}")
    return 0 if repeatable and matches and clean_erc else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return evaluate(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
