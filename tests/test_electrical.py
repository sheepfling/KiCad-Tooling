"""Electrical requirements, negative engineering cases and runner evidence boundaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Required, TypedDict, cast
from unittest.mock import patch

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import (
    bound_inputs,
    load_analysis,
    policy_issues,
    power_budget_checks,
    selected_config,
)
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.generation import expected_outputs
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalCheck,
)
from kicad_tooling.hwrepo.spice import (
    expanded_deck,
    measured_checks,
    run_case,
    simulation_deck,
    simulator_version,
    waveform_checks,
)
from tests.electrical_simulation_support import ISLAND, NA, PROJECT, install_fixture

pytestmark = [pytest.mark.template_checkout]


class _ElectricalMeasureUpdate(TypedDict, total=False):
    minimum: Required[float]
    expression: Required[str]
    unit: Required[str]


class _PowerCaseUpdate(TypedDict, total=False):
    measures: Required[list[_ElectricalMeasureUpdate]]
    step_s: Required[float]
    source_sha256: Required[dict[str, str]]
    id: Required[str]


class _ElectricalPowerUpdate(TypedDict, total=False):
    startup: Required[list[_PowerCaseUpdate]]
    steady_state: Required[list[_PowerCaseUpdate]]


class _WaveformUpdate(TypedDict, total=False):
    step_s: Required[float]


class _SweepUpdate(TypedDict, total=False):
    stop_hz: Required[float]


class _ElectricalHighFrequencyUpdate(TypedDict, total=False):
    waveforms: Required[list[_WaveformUpdate]]
    sweeps: Required[list[_SweepUpdate]]


class _ElectricalGroundingDomainUpdate(TypedDict, total=False):
    pins: Required[list[str]]


class _ElectricalGroundingUpdate(TypedDict, total=False):
    domains: Required[list[_ElectricalGroundingDomainUpdate]]


class _ElectricalPayloadUpdate(TypedDict, total=False):
    grounding: Required[_ElectricalGroundingUpdate]
    power: Required[_ElectricalPowerUpdate]
    high_frequency: Required[_ElectricalHighFrequencyUpdate]


class ElectricalTests(unittest.TestCase):
    def stage(self) -> Path:
        from tests.support import reference_root

        temporary = tempfile.TemporaryDirectory(prefix="electrical-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "repository"
        shutil.copytree(reference_root(), root)
        return root

    def test_strict_contract_round_trip_and_schema(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        path = root / ISLAND / "tests/electrical.json"
        self.assertEqual(read_model(path, ElectricalAnalysisContract), contract)
        schema = json.loads(expected_outputs(root)["schemas/electrical-analysis-v1.schema.json"])
        self.assertEqual(schema, ElectricalAnalysisContract.model_json_schema())
        for key, value in (("schema_version", "2"), ("unknown", True), ("ngspice_version", 47)):
            raw = json.loads(contract.model_dump_json())
            raw[key] = value
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                read_model(path, ElectricalAnalysisContract)

    def test_invalid_ground_duplicates_windows_limits_and_model_bindings(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        mutations: tuple[Callable[[_ElectricalPayloadUpdate], None], ...] = (
            lambda d: d["grounding"]["domains"][0]["pins"].append("R1.2"),
            lambda d: d["power"]["startup"][0]["measures"][0].update(minimum=6.0),
            lambda d: d["power"]["startup"][0].update(step_s=1.0),
            lambda d: d["power"]["startup"][0].update(source_sha256={}),
            lambda d: d["high_frequency"]["waveforms"][0].update(step_s=1e-7),
            lambda d: d["high_frequency"]["sweeps"][0].update(stop_hz=1.0),
            lambda d: d["power"]["startup"][0]["measures"][0].update(expression="v(out)\nquit"),
            lambda d: d["power"]["steady_state"][0].update(id="startup"),
            lambda d: d["power"]["steady_state"][0]["measures"][1].update(unit="A"),
        )
        for mutation in mutations:
            raw: _ElectricalPayloadUpdate = cast(
                _ElectricalPayloadUpdate, json.loads(contract.model_dump_json())
            )
            mutation(raw)
            with self.assertRaises(ValueError):
                ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_budgets_reject_steady_peak_and_excess_peak_duration(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert spec.mode == "required"
        self.assertTrue(all(c.status == "PASS" for c in power_budget_checks(spec)))
        for field, value, expected in (
            ("continuous_limit_a", 0.01, "steady-current"),
            ("peak_limit_a", 1.0, "startup-current"),
            ("peak_duration_limit_s", 1e-5, "startup-duration"),
        ):
            changed = spec.model_copy(
                update={"rails": (spec.rails[0].model_copy(update={field: value}),)}
            )
            failures = [c.id for c in power_budget_checks(changed) if c.status == "FAIL"]
            self.assertIn(f"power/supply/{expected}", failures)

    def test_zero_startup_current_cannot_hide_steady_load(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert spec.mode == "required"
        load = spec.rails[0].loads[0].model_copy(update={"startup_a": 0.0})
        changed = spec.model_copy(
            update={"rails": (spec.rails[0].model_copy(update={"loads": (load,)}),)}
        )
        check = next(c for c in power_budget_checks(changed) if c.id.endswith("startup-current"))
        self.assertEqual(check.observed, 0.05)

    def test_binding_rejects_changed_source_model_wrong_project_and_escaping_contract(self) -> None:
        for kind in ("source", "model", "identity", "path"):
            with self.subTest(kind=kind):
                root = self.stage()
                contract = install_fixture(root)
                config = selected_config(root, PROJECT)
                self.assertEqual(policy_issues(root, config), ())
                if kind == "source":
                    target = root / config.required_inputs[0]
                    target.write_bytes(target.read_bytes() + b"\n")
                elif kind == "model":
                    target = root / ISLAND / "tests/electrical/startup.cir"
                    target.write_text(target.read_text().replace("100u", "200u"))
                elif kind == "identity":
                    assert config.electrical is not None
                    write_model(
                        root / config.electrical,
                        contract.model_copy(update={"project_id": "wrong"}),
                    )
                else:
                    config = config.model_copy(update={"electrical": "../elsewhere.json"})
                self.assertTrue(policy_issues(root, config))

    def test_undeclared_includes_control_code_and_unused_models_rejected(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        case = contract.power.startup[0]
        target = root / case.deck
        for text in (
            'title\n.include "hidden.lib"\n.end\n',
            "title\n.control\nquit\n.endc\n.end\n",
            'title\n.lib "hidden.lib" section\n.end\n',
            "title\n.end\nR1 a 0 1k\n",
        ):
            target.write_text(text)
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)

    def test_simulator_failure_missing_duplicate_nonfinite_and_out_of_limit_measurements(
        self,
    ) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        case = contract.power.startup[0]
        for stdout in (
            "",
            "check0 = nan",
            "check0 = 2\ncheck0 = 3",
            "check0 = 9",
            "check0 = 2\nError: transient failed",
        ):
            command = CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout=stdout
            )
            self.assertTrue(any(c.status == "FAIL" for c in measured_checks(case, command)))
        command = CommandEvidence(
            argv=("ngspice",), started_utc="fixture", returncode=0, stdout="check0 = 4.95"
        )
        self.assertEqual(measured_checks(case, command)[0].status, "PASS")
        deck = simulation_deck(root, case)
        self.assertIn("tran 9.999", deck)
        self.assertIn("set measureprec=15", deck)
        self.assertIn("set rawfileprec=17", deck)

    def test_missing_or_wrong_simulator_does_not_pass(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        write_model(
            root / ISLAND / "tests/electrical.json", contract.model_copy(update={"grounding": NA})
        )
        report = analyze(root, PROJECT, ngspice="missing-electrical-simulator")
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any(c.status == "NOT_RUN" for c in report.checks))
        self.assertTrue((Path(report.run_directory) / "ngspice-version.command.json").is_file())
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout="ngspice-46"
            ),
        ):
            self.assertRaisesRegex(
                ValueError,
                "Exact ngspice",
                simulator_version,
                Path(report.run_directory),
                "ngspice",
                "47",
            )

    def test_unconfigured_cli_is_explicit_nonzero_and_writes_a_receipt(self) -> None:
        root = self.stage()
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical",
                "--root",
                str(root),
                "--project",
                PROJECT,
                "--format",
                "json",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        self.assertEqual(json.loads(command.stdout)["status"], "NOT_CONFIGURED")

    def test_bound_inputs_and_policy_are_rechecked_after_execution(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        contract = contract.model_copy(update={"power": NA, "high_frequency": NA, "grounding": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        config = selected_config(root, PROJECT)
        self.assertIsNotNone(load_analysis(root, config))
        before = bound_inputs(root, config, contract)
        with patch("kicad_tooling.hwrepo.electrical_runner.bound_inputs", side_effect=[before, {}]):
            report = analyze(root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("changed during", report.checks[-1].detail)

    def test_timeout_receipt_and_missing_waveforms_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        output = root / "build/spice-test"
        output.mkdir(parents=True)
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=124, error="Timed out"
            ),
        ):
            _, checks = run_case(root, output, "ngspice", contract.power.startup[0])
        self.assertTrue(all(c.status == "FAIL" for c in checks))
        self.assertTrue((output / "startup/ngspice.command.json").is_file())

    def test_waveform_parser_rejects_truncated_nonfinite_and_uncovered_data(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        case = contract.power.startup[0]
        raw = root / "waveform.raw"
        content = "Title: test\nFlags: real\nNo. Variables: 2\nNo. Points: 3\nVariables:\n0 time time\n1 v(out) voltage\nValues:\n0 0\n0\n1 0.001\n4.9\n2 0.005\n5\n"
        raw.write_text(content)
        self.assertTrue(all(c.status == "PASS" for c in waveform_checks(raw, case)))
        for changed in (
            content.replace("2 0.005\n5\n", ""),
            content.replace("4.9", "nan"),
            content.replace("1 0.001", "1 -0.001"),
        ):
            raw.write_text(changed)
            with self.assertRaises(ValueError):
                waveform_checks(raw, case)
        raw.write_text(content.replace("0.001", "0.0001").replace("0.005", "0.0005"))
        self.assertTrue(any(c.status == "FAIL" for c in waveform_checks(raw, case)))

    def test_recursive_escaping_and_unlisted_model_includes_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        case = contract.power.startup[0]
        target = root / case.deck
        for include in ("startup.cir", "../other.cir", "/tmp/other.cir"):
            target.write_text(f'title\n.include "{include}"\n.end\n')
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)
        included = target.with_name("passive.lib")
        included.write_text("R1 in out 10\n")
        target.write_text('title\n.include "passive.lib"\n.end\n')
        case = case.model_copy(
            update={
                "model_sha256": {
                    case.deck: digest(target),
                    included.relative_to(root).as_posix(): digest(included),
                }
            }
        )
        self.assertIn("R1 in out 10", expanded_deck(root, case))
        target.write_text("title\nR1 in out 1\n.end\n")
        case = case.model_copy(
            update={"model_sha256": {**case.model_sha256, case.deck: digest(target)}}
        )
        with self.assertRaisesRegex(ValueError, "Unused model"):
            expanded_deck(root, case)

    def test_portable_gate_rejects_an_overload_and_cli_cannot_bypass_model_hashes(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert contract.power.mode == "required"
        overloaded = contract.power.model_copy(
            update={
                "rails": (
                    contract.power.rails[0].model_copy(update={"continuous_limit_a": 0.001}),
                ),
            }
        )
        write_model(
            root / ISLAND / "tests/electrical.json",
            contract.model_copy(update={"power": overloaded}),
        )
        from kicad_tooling.ci import project_static_pipeline

        result = project_static_pipeline(root, (PROJECT,))
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("steady-current" in issue for issue in result.registry.issues))
        write_model(root / ISLAND / "tests/electrical.json", contract)
        model = root / contract.power.startup[0].deck
        model.write_text(model.read_text() + "\n")
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.ci",
                "--root",
                str(root),
                "--electrical",
                "--project",
                PROJECT,
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        report = json.loads(command.stdout)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("stale reviewed model", report["projects"][0]["checks"][-1]["detail"])

    def test_combined_verification_cannot_pass_a_failed_electrical_lane(self) -> None:
        from kicad_tooling.verify import verify
        from tests.test_verify import VerifyTests, native_summary

        root = self.stage().resolve()
        contract = install_fixture(root).model_copy(update={"power": NA, "high_frequency": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        failed = ElectricalAnalysisReport(
            project_id=PROJECT,
            status="FAIL",
            run_directory=str(root / "build/simulation"),
            checks=(ElectricalCheck(id="grounding", status="FAIL", detail="Missing pin U1.2"),),
        )
        with (
            VerifyTests.runner_environment("10.0.0"),
            patch("kicad_tooling.verify.check_all", return_value=native_summary()),
            patch(
                "kicad_tooling.hwrepo.electrical_runner.analyze", return_value=failed
            ) as simulation,
        ):
            result = verify(
                root, PROJECT, depth="electrical", runner="local", ngspice="approved-ngspice"
            )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.electrical, failed)
        self.assertEqual(simulation.call_args.args[-1], "approved-ngspice")
        self.assertIn("electrical", result.next_actions[0])


if __name__ == "__main__":
    unittest.main()
