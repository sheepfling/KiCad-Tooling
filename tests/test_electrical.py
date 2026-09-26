"""Electrical requirements, negative engineering cases and runner evidence boundaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    policy_issues,
    power_budget_checks,
    selected_config,
)
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.generation import expected_outputs
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    CommandEvidence,
    ComponentContract,
    ElectricalAnalysisContract,
    FrequencyAnalysis,
    GroundDomain,
    GroundingAnalysis,
    HighFrequencyAnalysis,
    NetlistContract,
    PowerAnalysis,
    PowerLoad,
    PowerRail,
    SimulationMeasure,
    TransientAnalysis,
)
from kicad_tooling.hwrepo.spice import (
    expanded_deck,
    measured_checks,
    run_case,
    simulation_deck,
    simulator_version,
    waveform_checks,
)
from kicad_tooling.validate import hashes
from tests.support import TEMPLATE_ROOT, reference_root

PROJECT = "controller"
ISLAND = "examples/projects/controller"
NA = AnalysisNotApplicable(mode="not_applicable", reason="Synthetic test scope")


def install_fixture(root: Path, version: str = "47") -> ElectricalAnalysisContract:
    """Author synthetic requirements only in a disposable copy of the training island."""
    directory = root / ISLAND / "tests/electrical"
    directory.mkdir(parents=True)
    for name in ("startup.cir", "signal.cir"):
        shutil.copy2(TEMPLATE_ROOT / "templates/electrical" / name, directory / name)
    config = selected_config(root, PROJECT)
    source = hashes(root, config.source_roots)

    def model(name: str) -> dict[str, str]:
        path = directory / name
        return {path.relative_to(root).as_posix(): digest(path)}

    startup_model = model("startup.cir")
    signal_model = model("signal.cir")
    startup = TransientAnalysis(
        id="startup",
        basis="Synthetic 5 V source ramp into 100 uF through 1 ohm",
        deck=next(iter(startup_model)),
        source_sha256=source,
        model_sha256=startup_model,
        step_s=1e-6,
        stop_s=0.005,
        measures=(
            SimulationMeasure(
                id="peak-current",
                expression="-i(vrail)",
                statistic="max",
                unit="A",
                start=0.0,
                stop=0.001,
                maximum=5.1,
            ),
        ),
    )
    steady = startup.model_copy(
        update={
            "id": "steady-state",
            "measures": (
                SimulationMeasure(
                    id="average-current",
                    expression="-i(vrail)",
                    statistic="avg",
                    unit="A",
                    start=0.004,
                    stop=0.005,
                    minimum=0.049,
                    maximum=0.051,
                ),
                SimulationMeasure(
                    id="average-power",
                    expression="-v(supply)*i(vrail)",
                    statistic="avg",
                    unit="W",
                    start=0.004,
                    stop=0.005,
                    minimum=0.24,
                    maximum=0.26,
                ),
                SimulationMeasure(
                    id="rail-minimum",
                    expression="v(out)",
                    statistic="min",
                    unit="V",
                    start=0.004,
                    stop=0.005,
                    minimum=4.9,
                ),
            ),
        }
    )
    sweep = FrequencyAnalysis(
        id="passband",
        basis="Synthetic 50 ohm/10 pF first-order low-pass",
        deck=next(iter(signal_model)),
        source_sha256=source,
        model_sha256=signal_model,
        start_hz=1000.0,
        stop_hz=1e9,
        measures=(
            SimulationMeasure(
                id="gain",
                expression="db(v(out)/v(in))",
                statistic="min",
                unit="dB",
                start=1000.0,
                stop=1e6,
                minimum=-0.1,
                maximum=0.0,
            ),
        ),
    )
    waveform = TransientAnalysis(
        id="edges",
        basis="Synthetic 1 MHz source with 1 ns rise and fall times",
        deck=sweep.deck,
        source_sha256=source,
        model_sha256=signal_model,
        step_s=1e-10,
        stop_s=3e-6,
        measures=(
            SimulationMeasure(
                id="overshoot",
                expression="v(out)",
                statistic="max",
                unit="V",
                start=0.0,
                stop=3e-6,
                minimum=0.99,
                maximum=1.01,
            ),
        ),
    )
    contract = ElectricalAnalysisContract(
        project_id=PROJECT,
        ngspice_version=version,
        grounding=GroundingAnalysis(
            basis="Synthetic reference net, not protective earth",
            domains=(GroundDomain(net="PILOT_B", pins=("R1.2", "R2.2")),),
        ),
        power=PowerAnalysis(
            rails=(
                PowerRail(
                    id="supply",
                    basis="Synthetic derated supply and path limits",
                    voltage_v=5.0,
                    continuous_limit_a=0.1,
                    peak_limit_a=6.0,
                    peak_duration_limit_s=0.002,
                    loads=(
                        PowerLoad(
                            id="load",
                            basis="Synthetic worst case",
                            steady_a=0.05,
                            startup_a=5.0,
                            startup_s=0.001,
                        ),
                    ),
                ),
            ),
            startup=(startup,),
            steady_state=(steady,),
        ),
        high_frequency=HighFrequencyAnalysis(
            basis="Synthetic model only",
            frequency_hz=1e6,
            rise_time_s=1e-9,
            sweeps=(sweep,),
            waveforms=(waveform,),
        ),
    )
    path = root / ISLAND / "tests/electrical.json"
    write_model(path, contract)
    test_path = root / ISLAND / "tests/contract.json"
    raw = json.loads(test_path.read_text())
    raw["electrical"] = "tests/electrical.json"
    test_path.write_text(json.dumps(raw))
    return contract


class ElectricalTests(unittest.TestCase):
    def stage(self) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="electrical-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "repository"
        shutil.copytree(reference_root(), root)
        return root

    def ground(self) -> tuple[GroundingAnalysis, NetlistContract]:
        spec = GroundingAnalysis(
            basis="Independent pin requirements",
            domains=(
                GroundDomain(net="GND", pins=("U1.2", "J1.2")),
                GroundDomain(net="AGND", pins=("U2.2",)),
            ),
        )
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="fixture", footprint="") for ref in ("U1", "U2", "J1")
            },
            nets={"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",)},
        )
        return spec, observed

    def test_grounding_accepts_distinct_domains_and_rejects_missing_wrong_extra_pins(self) -> None:
        spec, observed = self.ground()
        self.assertTrue(all(c.status == "PASS" for c in grounding_checks(spec, observed)))
        for nets in (
            {"GND": ("U1.2",), "AGND": ("U2.2",)},
            {"GND": ("U1.2", "J1.2", "U2.2")},
            {"GND": ("U1.2", "J1.2", "U1.3"), "AGND": ("U2.2",)},
            {"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",), "SHORT": ("U1.2",)},
        ):
            with self.subTest(nets=nets):
                changed = observed.model_copy(update={"nets": nets})
                self.assertTrue(any(c.status == "FAIL" for c in grounding_checks(spec, changed)))

    def test_new_component_requires_ground_review_or_explicit_exemption(self) -> None:
        spec, observed = self.ground()
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "R1": ComponentContract(value="1k", footprint=""),
                }
            }
        )
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "FAIL")
        spec = spec.model_copy(
            update={"exempt_components": {"R1": "Series resistor, no ground pin"}}
        )
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "PASS")
        spec = spec.model_copy(update={"exempt_components": {"U1": "Contradictory exemption"}})
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "FAIL")

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
        mutations = (
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
            raw = json.loads(contract.model_dump_json())
            mutation(raw)
            with self.assertRaises(ValueError):
                ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_budgets_reject_steady_peak_and_excess_peak_duration(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert isinstance(spec, PowerAnalysis)
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
        assert isinstance(spec, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        assert isinstance(contract.power, PowerAnalysis)
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
        from kicad_tooling.hwrepo.models import ElectricalAnalysisReport, ElectricalCheck
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
