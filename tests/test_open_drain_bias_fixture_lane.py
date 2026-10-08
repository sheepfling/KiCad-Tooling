"""Orchestration checks for native open-output bias regression fixtures."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedLog, open_drain_bias_fixture_lane
from kicad_tooling.hwrepo.contracts import KiCadErcReport, KiCadErcViolation
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, NetlistContract


def bias_netlist(*, output_type: str, rail: str, dnp: bool) -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic open-output driver", footprint="Synthetic:SOIC"
            ),
            "U2": ComponentContract(value="Synthetic digital input", footprint="Synthetic:SOIC"),
            "R1": ComponentContract(value="10k", footprint="Synthetic:0603"),
        },
        nets={
            "ALERT_N": ("U2.1", "U1.2", "R1.1"),
            rail: ("R1.2",),
        },
        dnp_components=("R1",) if dnp else (),
        component_symbols={
            "U1": "Synthetic:OpenOutputProbe",
            "U2": "Synthetic:OpenOutputProbe",
            "R1": "Device:R",
        },
        pin_functions={
            "U2.1": "OPEN_OUTPUT",
            "U1.2": "INPUT_PEER",
            "R1.1": "~",
            "R1.2": "~",
        },
        pin_electrical_types={
            "U2.1": output_type,
            "U1.2": "input",
            "R1.1": "passive",
            "R1.2": "passive",
        },
        component_pin_numbers={
            "U1": ("1", "2"),
            "U2": ("1", "2"),
            "R1": ("1", "2"),
        },
    )


class OpenDrainBiasFixtureLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="open-drain-bias-lane-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.image = "fixture.invalid/kicad@sha256:" + "a" * 64
        self.config = SimpleNamespace(image=self.image, kicad_version="10.0.0")

    def test_native_lane_checks_both_bias_polarities_and_dnp_faults(self) -> None:
        observed = {
            "collector-control": bias_netlist(output_type="open_collector", rail="+3V3", dnp=False),
            "collector-fault": bias_netlist(output_type="open_collector", rail="+3V3", dnp=True),
            "emitter-control": bias_netlist(output_type="open_emitter", rail="GND", dnp=False),
            "emitter-fault": bias_netlist(output_type="open_emitter", rail="GND", dnp=True),
        }

        def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(root, self.root)
            self.assertEqual(timeout, 600)
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertIn("--read-only", argv)
            self.assertIn(self.image, argv)
            self.assertIn('test "$actual" = "10.0.0"', argv[-1])
            self.assertIn("collector-control collector-fault", argv[-1])
            self.assertIn("emitter-control emitter-fault", argv[-1])
            mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
            self.assertEqual(len(mounts), 2)
            fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
            output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
            fixtures = Path(fixture_mount.removesuffix(":/fixtures:ro"))
            output = Path(output_mount.removesuffix(":/output:rw"))
            self.assertEqual(
                {item.name for item in fixtures.iterdir()},
                {f"{case}.kicad_sch" for case in observed},
            )
            for case in observed:
                for run in ("first", "repeat"):
                    (output / f"{case}.{run}.netlist.xml").write_text(
                        f"synthetic {case} netlist {run}\n", encoding="utf-8"
                    )
                    (output / f"{case}.{run}.erc.json").write_text(
                        '{"kicad_version":"10.0.0","sheets":[{"violations":[]}]}',
                        encoding="utf-8",
                    )
            return CommandEvidence(
                argv=argv,
                started_utc="2026-10-01T00:00:00+00:00",
                returncode=0,
                stdout="kicad_version=10.0.0\n",
            )

        def fake_read_netlist(path: Path) -> NetlistContract:
            case = path.name.split(".", 1)[0]
            return observed[case]

        log = HostedLog(self.root, "open-drain-bias")
        with (
            patch("kicad_tooling.hwrepo.electrical.selected_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_run_command),
            patch("kicad_tooling.validate.read_netlist", side_effect=fake_read_netlist),
            patch(
                "kicad_tooling.ci_hosted.read_kicad_erc_report",
                return_value=KiCadErcReport(
                    kicad_version="10.0.0",
                    violations=tuple(
                        KiCadErcViolation(
                            type=warning,
                            severity="warning",
                            description=None,
                            items=(),
                        )
                        for warning in (
                            "footprint_link_issues",
                            "isolated_pin_label",
                            "lib_symbol_issues",
                        )
                    ),
                ),
            ),
        ):
            open_drain_bias_fixture_lane(
                self.root,
                project="synthetic-project",
                image=self.image,
                log=log,
            )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("open-drain-bias-fixture/")
        }
        self.assertEqual(
            set(results),
            {
                "open-drain-bias-fixture/native-export",
                *(f"open-drain-bias-fixture/{case}" for case in observed),
            },
        )
        for case, result in results.items():
            if case.endswith("native-export"):
                continue
            is_fault = case.endswith("fault")
            is_emitter = "emitter" in case
            self.assertEqual(result["lint_status"], "REVIEW" if is_fault else "PASS")
            self.assertEqual(
                result["findings"],
                (
                    "signal.open_emitter_input_without_visible_bias"
                    if is_emitter
                    else "signal.open_collector_input_without_visible_bias"
                )
                if is_fault
                else "none",
            )
            self.assertEqual(
                result["open_output_type"], "open_emitter" if is_emitter else "open_collector"
            )
            self.assertEqual(result["erc_errors"], "0")
            self.assertEqual(
                set(result["erc_warning_types"].split(";")),
                {"footprint_link_issues", "isolated_pin_label", "lib_symbol_issues"},
            )
            self.assertEqual(result["repeatable"], "true")
            self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                result["normalized_netlist_sha256"], result["repeat_normalized_netlist_sha256"]
            )
            self.assertRegex(result["normalized_erc_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                result["normalized_erc_sha256"], result["repeat_normalized_erc_sha256"]
            )


if __name__ == "__main__":
    unittest.main()
