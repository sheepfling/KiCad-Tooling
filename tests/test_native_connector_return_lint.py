"""Exact-version source-to-netlist regression for synthetic return domains."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
)
from kicad_tooling.validate import read_netlist

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/design_lint/cohort-connector-ground-domains"
RECEIPTS = ROOT / "build/tests"


class NativeConnectorReturnLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cli_value = os.environ.get("KICAD_CONNECTOR_LINT_TEST_CLI")
        if not cli_value:
            raise unittest.SkipTest(
                "set KICAD_CONNECTOR_LINT_TEST_CLI for exact-version native source tests"
            )
        cls.cli = Path(cli_value).resolve()
        if not cls.cli.is_file():
            raise unittest.SkipTest("KICAD_CONNECTOR_LINT_TEST_CLI does not point to a file")
        version = subprocess.run(
            (str(cls.cli), "version"),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        if version != "10.0.6":
            raise unittest.SkipTest(
                f"native connector fixture requires KiCad 10.0.6, got {version}"
            )

    def test_native_netlist_distinguishes_split_and_common_return_domains(self) -> None:
        RECEIPTS.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="connector-return-lint-", dir=RECEIPTS) as temp:
            output = Path(temp)
            reports: dict[str, DesignLintReport] = {}
            for case in ("fault", "control"):
                netlist_path = output / f"{case}.netlist.xml"
                subprocess.run(
                    (
                        str(self.cli),
                        "sch",
                        "export",
                        "netlist",
                        "--format",
                        "kicadxml",
                        "--output",
                        str(netlist_path),
                        str(FIXTURES / f"{case}.kicad_sch"),
                    ),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                observed = read_netlist(netlist_path)
                digest = hashlib.sha256(netlist_path.read_bytes()).hexdigest()
                coach = ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-return-domains-{case}",
                    observed=observed,
                    netlist_sha256=digest,
                )
                reports[case] = evaluate(
                    coach.project_id,
                    coach,
                    DesignLintPolicy(),
                )

        fault = reports["fault"]
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(
            {finding.rule_id for finding in fault.findings},
            {"connector.repeated_pin_function", "net.numbered_returns"},
        )
        repeated_returns = next(
            finding
            for finding in fault.findings
            if finding.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(
            dict(repeated_returns.evidence),
            {
                "J1.1": ("GND1",),
                "J1.2": ("GND1",),
                "J2.1": ("GND2",),
                "J2.2": ("GND2",),
            },
        )
        self.assertEqual(reports["control"].status, "PASS")
        self.assertFalse(reports["control"].findings)


if __name__ == "__main__":
    unittest.main()
