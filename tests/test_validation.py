"""Test the checker itself; these unit tests do not stand in for KiCad execution."""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.check_all import check_all
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ComponentIdentity,
    IgnoredChecks,
    NetlistIdentityReport,
    PcbOnlyValidationContract,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.validate import (
    check_netlist,
    check_report,
    hashes,
    read_netlist,
    validate,
)
from tests.support import initialize_git, reference_root

ROOT: Path = reference_root()
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root: Path = Path(self.temp.name)
        self.config = load_config(ROOT, ROOT / "examples/projects/controller/project.json")
    ####

    def report(self, data: JsonValue) -> Path:
        path: Path = self.root / "report.json"
        path.write_text(json.dumps(data))
        return path
    ####

    def fixture(self) -> None:
        for directory in (
            "catalog",
            "examples",
            "docs",
        ):
            shutil.copytree(ROOT / directory, self.root / directory)
        initialize_git(self.root)
    ####

    def test_erc_clean(self) -> None:
        data: JsonObject = {"kicad_version": "10.0.0", "sheets": [{"violations": []}]}
        self.assertEqual(check_report(self.report(data), "erc"), 0)
    ####

    def test_erc_all_findings_count(self) -> None:
        data: JsonObject = {"kicad_version": "10.0.0", "sheets": [{"violations": [{"severity": "warning"}, {"excluded": True}]}]}
        self.assertEqual(check_report(self.report(data), "erc"), 2)
    ####

    def test_incomplete_reports_rejected(self) -> None:
        for data in ({}, [], {"kicad_version": "10.0.0"}, {"kicad_version": "10.0.0", "sheets": []}):
            with self.subTest(data=data), self.assertRaises((ValueError, TypeError)):
                check_report(self.report(data), "erc")
            ####
        ####
    ####

    def test_drc_clean_requires_parity(self) -> None:
        data: JsonObject = {"kicad_version": "10.0.0", "violations": [], "unconnected_items": [], "schematic_parity": []}
        self.assertEqual(check_report(self.report(data), "drc"), 0)
        del data["schematic_parity"]
        with self.assertRaises((TypeError, ValueError)):
            check_report(self.report(data), "drc")
        ####
    ####

    def test_drc_counts_every_category(self) -> None:
        data: JsonObject = {"kicad_version": "10.0.0", "violations": [{}], "unconnected_items": [{}], "schematic_parity": [{}]}
        self.assertEqual(check_report(self.report(data), "drc"), 3)
    ####

    def test_pcb_only_drc_has_no_schematic_parity_requirement(self) -> None:
        config = ProjectConfig(
            schema_version="1",
            kind=ProjectKind.PCB_ONLY,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="legacy-layout",
            component_identity=ComponentIdentity(required=False, part_ids=()),
            toolchain_id="kicad-10.0.0",
            kicad_version="10.0.0",
            image="example.invalid/kicad@sha256:" + "a" * 64,
            project="projects/legacy-layout/kicad/legacy-layout.kicad_pro",
            source_roots=("projects/legacy-layout/kicad",),
            required_inputs=(
                "projects/legacy-layout/kicad/legacy-layout.kicad_pro",
                "projects/legacy-layout/kicad/legacy-layout.kicad_pcb",
            ),
            validation=PcbOnlyValidationContract(
                kind=ProjectKind.PCB_ONLY,
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
        )
        data: JsonObject = {
            "$schema": "https://schemas.kicad.org/drc.v1.json",
            "kicad_version": "10.0.0",
            "included_severities": ["error", "warning", "exclusion"],
            "ignored_checks": [],
            "violations": [],
            "unconnected_items": [],
        }
        self.assertEqual(check_report(self.report(data), "drc", config), 0)

    def test_native_validation_uses_escaped_bom_cells(self) -> None:
        self.fixture()
        self.assertIsInstance(self.config.validation, PcbValidationContract)
        components = dict(self.config.validation.components)
        components["R1"] = components["R1"].model_copy(
            update={"value": "=1+1", "footprint": " @unsafe"}
        )
        config = self.config.model_copy(update={
            "validation": self.config.validation.model_copy(update={"components": components}),
        })

        def run_kicad(argv: tuple[str, ...], _cwd: Path, output: Path, name: str) -> CommandEvidence:
            if name in {"erc", "drc"}:
                report: JsonObject = {
                    "$schema": f"https://schemas.kicad.org/{name}.v1.json",
                    "kicad_version": config.kicad_version,
                    "included_severities": ["error", "warning", "exclusion"],
                    "ignored_checks": [
                        {"key": key} for key in getattr(config.validation.expected_ignored_checks, name)
                    ],
                }
                if name == "erc":
                    report["sheets"] = [{"violations": []}]
                else:
                    report.update({
                        "violations": [], "unconnected_items": [], "schematic_parity": [],
                    })
                (output / f"{name}.json").write_text(json.dumps(report), encoding="utf-8")
            elif name == "schematic_svg":
                directory = output / "schematic"
                directory.mkdir()
                (directory / "sheet.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            elif name == "pcb_svg":
                (output / "pcb.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            elif name == "netlist":
                (output / "netlist.xml").write_text("<export/>", encoding="utf-8")
            return CommandEvidence(
                argv=argv, started_utc="2026-01-01T00:00:00+00:00", returncode=0,
                stdout=f"{config.kicad_version}\n" if name == "version" else "",
            )

        output = self.root / "native-review"
        with (
            patch("kicad_tooling.validate.load_config", return_value=config),
            patch("kicad_tooling.validate.cli_executable", return_value="fake-kicad-cli"),
            patch("kicad_tooling.validate.execute", side_effect=run_kicad),
            patch("kicad_tooling.validate.check_netlist"),
            patch("kicad_tooling.hwrepo.product.check_project_netlist",
                  return_value=NetlistIdentityReport(status="PASS")),
        ):
            result = validate(
                self.root, output, "fake-kicad-cli",
                Path("examples/projects/controller/project.json"),
            )
        self.assertEqual(result.status, "PASS", result.checks)
        with (output / "bom.csv").open(newline="", encoding="utf-8") as stream:
            rows = {row["Reference"]: row for row in csv.DictReader(stream)}
        self.assertEqual(rows["R1"]["Value"], "'=1+1")
        self.assertEqual(rows["R1"]["Footprint"], "' @unsafe")

    def test_pcb_only_native_lane_runs_board_checks_without_schematic_commands(self) -> None:
        self.fixture()
        for name in (
            "templates/pcb-only-project-config.example.json",
            "templates/project-tests/pcb_only.json",
        ):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        created = new_project(self.root, "legacy-layout", ProjectKind.PCB_ONLY, "kicad-10.0.5")
        self.assertEqual(created.status, "PASS", created.issues)
        island = self.root / "projects/legacy-layout/kicad"
        (island / "legacy-layout.kicad_pro").write_text("{}", encoding="utf-8")
        (island / "legacy-layout.kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")
        commands: list[tuple[str, ...]] = []

        def run_kicad(argv: tuple[str, ...], _cwd: Path, output: Path, name: str) -> CommandEvidence:
            commands.append(argv)
            if name == "version":
                return CommandEvidence(
                    argv=argv,
                    started_utc="2026-01-01T00:00:00+00:00",
                    returncode=0,
                    stdout="10.0.5\n",
                )
            if name == "drc":
                (output / "drc.json").write_text(json.dumps({
                    "$schema": "https://schemas.kicad.org/drc.v1.json",
                    "kicad_version": "10.0.5",
                    "included_severities": ["error", "warning", "exclusion"],
                    "ignored_checks": [],
                    "violations": [],
                    "unconnected_items": [],
                }), encoding="utf-8")
            elif name == "pcb_svg":
                (output / "pcb.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            else:
                raise AssertionError(f"Unexpected KiCad command: {name}")
            return CommandEvidence(
                argv=argv,
                started_utc="2026-01-01T00:00:00+00:00",
                returncode=0,
            )

        with (
            patch("kicad_tooling.validate.cli_executable", return_value="fake-kicad-cli"),
            patch("kicad_tooling.validate.execute", side_effect=run_kicad),
        ):
            result = validate(
                self.root,
                self.root / "pcb-only-native",
                "fake-kicad-cli",
                Path("projects/legacy-layout/project.json"),
            )
        self.assertEqual(result.status, "PASS", result.checks)
        self.assertEqual(set(result.checks), {
            "governance", "repository", "product_policy", "source_scope", "toolchain",
            "drc", "pcb_svg", "source_unchanged",
        })
        calls = "\n".join(" ".join(command[1:]) for command in commands)
        self.assertIn("pcb drc", calls)
        self.assertIn("pcb export svg", calls)
        self.assertNotIn("sch ", calls)

    def test_empty_netlist_cannot_pass(self) -> None:
        path: Path = self.root / "netlist.xml"
        path.write_text("<export><components/><nets/></export>")
        config = load_config(ROOT, ROOT / "examples/projects/controller/project.json")
        self.assertIsInstance(config.validation, PcbValidationContract)
        with self.assertRaises(ValueError):
            check_netlist(path, config.validation)

    def test_unfinished_import_contract_never_passes_an_empty_export(self) -> None:
        path = self.root / "empty.xml"
        path.write_text("<export><components/><nets/></export>")
        contract = PcbValidationContract(kind=ProjectKind.PCB, components={}, nets={},
                                        expected_ignored_checks=IgnoredChecks(erc=(), drc=()))
        with self.assertRaisesRegex(ValueError, "Complete the component"):
            check_netlist(path, contract)

    def test_realistic_net_names_and_missing_footprints_parse_and_connection_changes_fail(self) -> None:
        path = self.root / "native.xml"
        source = ('<export><components><comp ref="J1"><value>USB</value></comp></components>'
                  '<nets><net name="/+3.3V"><node ref="J1" pin="1"/></net>'
                  '<net name="/channel/D+[0]"><node ref="J1" pin="3"/></net></nets></export>')
        path.write_text(source)
        observed = read_netlist(path)
        self.assertIn("channel/D+[0]", observed.nets)
        self.assertEqual(observed.components["J1"].footprint, "")
        contract = PcbValidationContract(kind=ProjectKind.PCB, components=observed.components,
            nets=observed.nets, expected_ignored_checks=IgnoredChecks(erc=(), drc=()))
        self.assertEqual(check_netlist(path, contract), observed)
        path.write_text(source.replace('pin="3"', 'pin="2"'))
        with self.assertRaisesRegex(ValueError, "channel/D"):
            check_netlist(path, contract)

    def test_native_lane_rejects_nonportable_dependency_before_running_kicad(self) -> None:
        self.fixture()
        board = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        board.write_text(board.read_text() + '\n(model "/missing/machine-local.step")\n')
        result = check_all(self.root, self.root / "blocked-native", "intentionally-absent-kicad", ["controller"])
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.projects, ())
        self.assertIn("machine-local dependency", " ".join(result.repository.issues))
        ####
    ####

    def test_fixture_inventory_matches(self) -> None:
        config = load_config(ROOT, ROOT / "examples/projects/controller/project.json")
        self.assertEqual(set(hashes(ROOT, config.source_roots)), set(config.required_inputs))
    ####

    def test_missing_tool_is_failure(self) -> None:
        self.fixture()
        result = validate(self.root, self.root / "out", "intentionally-absent-kicad")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("missing", result.checks["preflight"].error or "")
    ####

    def test_missing_dependency_is_failure(self) -> None:
        self.fixture()
        (self.root / "examples/projects/controller/kicad/Pilot.kicad_sym").unlink()
        result = validate(self.root, self.root / "out", "intentionally-absent-kicad")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("inventory", result.checks["preflight"].error or "")
    ####

    def test_unknown_board_is_failure(self) -> None:
        self.fixture()
        (self.root / "examples/projects/controller/kicad/extra.kicad_pcb").write_text("unknown")
        result = validate(self.root, self.root / "out", "intentionally-absent-kicad")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("extra.kicad_pcb", result.checks["preflight"].error or "")
    ####

    def test_no_overwriting_retained_evidence(self) -> None:
        self.fixture()
        (self.root / "out").mkdir()
        with self.assertRaises(FileExistsError):
            validate(self.root, self.root / "out", "intentionally-absent-kicad")
        ####
    ####

    def test_source_hash_detects_mutation(self) -> None:
        self.fixture()
        before = hashes(self.root, self.config.source_roots)
        (self.root / "examples/projects/controller/kicad/controller.kicad_pro").write_text("{}")
        self.assertNotEqual(before, hashes(self.root, self.config.source_roots))
    ####

    def test_all_project_check_reports_missing_tool(self) -> None:
        self.fixture()
        result = check_all(self.root, self.root / "all-out", "intentionally-absent-kicad")
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.governance.status, "PASS")
        self.assertIn("controller", {project.id for project in result.projects})
        self.assertEqual(result.projects[0].status, "FAIL")
    ####

    def test_declared_shared_library_root_is_hashed(self) -> None:
        self.fixture()
        library: Path = self.root / "libraries/shared"
        library.mkdir(parents=True)
        source: Path = library / "Example.kicad_sym"
        source.write_text("(kicad_symbol_lib (version 20231120) (generator test))")
        scoped = hashes(self.root, ["examples/projects", "libraries/shared"])
        self.assertIn("libraries/shared/Example.kicad_sym", scoped)
        self.assertNotEqual(hashes(self.root, self.config.source_roots), scoped)
    ####
if __name__ == "__main__":
    unittest.main()
