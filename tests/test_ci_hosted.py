"""Behavioral checks for reusable hosted planning, shards and retained failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import DEFAULT, patch

import pytest

from kicad_tooling.ci_hosted import (
    TWO_PIN_COMPONENT_FIXTURE_CASES,
    HostedLog,
    electrical_lane,
    gate_result,
    markdown_checks,
    matrix_lane,
    native_lane,
    plan_lane,
    plan_scope,
    portable_lane,
    release_fixture,
    release_lane,
)
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.electrical_setup import initialize as init_electrical
from kicad_tooling.hwrepo.initialization import initialize
from kicad_tooling.hwrepo.layout import RepositoryLayout, layout
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    CommandEvidence,
    ElectricalAnalysisContract,
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
    ProjectConfig,
)
from kicad_tooling.hwrepo.sharding import ProjectShard, shard_projects
from kicad_tooling.hwrepo.template import preflight
from tests.support import TEST_ROOT, initialize_git, reference_root

SERIAL_LABEL_EXPECTED_NETS = json.loads(
    (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/serial-peer-connector-reference-native/"
        "serial-label-expected-nets.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Hosted native orchestration uses a Unix runner"
)
def test_native_lane_cannot_pass_when_declared_electrical_fails(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    initialize_git(root)
    subprocess.run(
        (
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic source",
        ),
        check=True,
        capture_output=True,
    )
    log = HostedLog(root, "native")
    with (
        patch.object(log, "run") as run,
        patch(
            "kicad_tooling.ci_hosted.connector_return_lint_fixture_lane"
        ) as connector_return_fixture,
        patch("kicad_tooling.ci_hosted.usb_data_path_fixture_lane") as usb_fixture,
        patch("kicad_tooling.ci_hosted.power_path_fixture_lane") as power_path_fixture,
        patch("kicad_tooling.ci_hosted.stm32_pin_map_fixture_lane") as stm32_fixture,
        patch("kicad_tooling.ci_hosted.led_rail_fixture_lane") as led_fixture,
        patch("kicad_tooling.ci_hosted.two_pin_component_fixture_lane") as component_fixture,
        patch(
            "kicad_tooling.ci_hosted.component_peer_power_output_fixture_lane"
        ) as peer_power_fixture,
        patch("kicad_tooling.ci_hosted.component_rating_fixtures_lane") as voltage_rating_fixture,
        patch("kicad_tooling.ci_hosted.power_sequence_fixture_lane") as sequence_fixture,
        patch("kicad_tooling.ci_hosted.ic_rail_capacitor_fixture_lane") as rail_cap_fixture,
        patch.multiple(
            "kicad_tooling.ci_hosted",
            pcb_signal_path_drc_fixture_lane=DEFAULT,
            component_peer_signal_input_fixture_lane=DEFAULT,
            component_peer_signal_output_fixture_lane=DEFAULT,
        ) as other_native_fixtures,
        patch("kicad_tooling.ci_hosted.pcb_return_fixture_lane") as pcb_fixture,
        patch("kicad_tooling.ci_hosted.pcb_access_fixture_lane") as access_fixture,
        patch("kicad_tooling.ci_hosted.pcb_decoupling_fixture_lane") as decoupling_fixture,
        patch("kicad_tooling.ci_hosted.pcb_switching_loop_fixture_lane") as switching_loop_fixture,
        patch(
            "kicad_tooling.ci_hosted.pcb_reference_plane_via_fixture_lane"
        ) as reference_plane_fixture,
        patch(
            "kicad_tooling.ci_hosted.pcb_reference_plane_narrow_void_fixture_lane"
        ) as narrow_void_fixture,
        patch(
            "kicad_tooling.ci_hosted.electrical_lane",
            side_effect=RuntimeError("Electrical measurement failed"),
        ) as electrical,
        pytest.raises(RuntimeError, match="Electrical measurement failed"),
    ):
        native_lane(
            root,
            project="controller",
            image="fixture@sha256:" + "a" * 64,
            pr_head="",
            fault_probes=True,
            log=log,
        )
    expected_kwargs = {
        "project": "controller",
        "image": "fixture@sha256:" + "a" * 64,
        "log": log,
    }
    electrical.assert_called_once_with(
        root, "controller", log, native_summary="build/review/controller/summary.json"
    )
    for fixture in (
        connector_return_fixture,
        usb_fixture,
        power_path_fixture,
        stm32_fixture,
        led_fixture,
        component_fixture,
        peer_power_fixture,
        other_native_fixtures["component_peer_signal_output_fixture_lane"],
        other_native_fixtures["component_peer_signal_input_fixture_lane"],
        voltage_rating_fixture,
        sequence_fixture,
        rail_cap_fixture,
        pcb_fixture,
        access_fixture,
        decoupling_fixture,
        switching_loop_fixture,
        reference_plane_fixture,
        narrow_void_fixture,
    ):
        fixture.assert_called_once_with(root, **expected_kwargs)
    stages = [call.args[0] for call in run.call_args_list]
    assert "native-check" in stages
    assert "fault-probes" not in stages
    assert stages[-2:] == ["source-diff", "index-diff"]


class HostedCiTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="hosted-ci-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )

    def test_shards_partition_a_tag_and_never_claim_full_acceptance(self) -> None:
        projects = ("z", "a", "c", "b", "d", "e")
        shards = [shard_projects(projects, f"{index}/3") for index in (1, 2, 3)]
        self.assertEqual(
            tuple(sorted(project for shard in shards for project in shard)), tuple(sorted(projects))
        )
        self.assertTrue(all(len(shard) == 2 for shard in shards))
        plan = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="tag",
            value="training",
            exclude_tag=None,
            shard="1/2",
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(len(plan.projects), 3)
        self.assertIn("Partial project shard 1/2", plan.reasons)
        full_shard = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="full",
            value=None,
            exclude_tag=None,
            shard="1/2",
        )
        self.assertEqual(full_shard.scope, "focused")
        self.assertEqual(len(full_shard.projects), 3)

    def test_bad_or_empty_shards_fail_before_checks(self) -> None:
        for value in ("0/2", "1/0", "3/2", "1:2", "", "2/3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ProjectShard.parse(value).select(("controller",))
        with self.assertRaisesRegex(ValueError, "base branch"):
            plan_scope(
                self.root,
                event="local",
                base=None,
                focus="branch",
                value=None,
                exclude_tag=None,
                shard=None,
            )

    def test_branch_focus_uses_the_same_git_impact_scope(self) -> None:
        initialize_git(self.root)

        def git(*args: str) -> str:
            return subprocess.run(
                ("git", "-C", str(self.root), *args), check=True, capture_output=True, text=True
            ).stdout.strip()

        git(
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Initial source",
        )
        base = git("rev-parse", "HEAD")
        board = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        board.write_bytes(board.read_bytes() + b"\n")
        git("add", "--all")
        git(
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Board change",
        )
        plan = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="branch",
            value=base,
            exclude_tag=None,
            shard=None,
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, ("controller",))
        pr_plan = plan_scope(
            self.root,
            event="pull_request",
            base=base,
            focus="full",
            value=None,
            exclude_tag=None,
            shard=None,
        )
        self.assertEqual(pr_plan, plan)
        pr_shard = plan_scope(
            self.root,
            event="pull_request",
            base=base,
            focus="full",
            value=None,
            exclude_tag=None,
            shard="1/1",
        )
        self.assertEqual(pr_shard.projects, plan.projects)
        self.assertIn("Partial project shard 1/1", pr_shard.reasons)

    def test_hosted_plan_and_native_matrix_outputs_agree_on_the_shard(self) -> None:
        destination = self.root / "github-output.txt"
        destination.write_text("", encoding="utf-8")
        args = argparse.Namespace(
            event="local",
            base="",
            focus="tag",
            value="training",
            exclude_tag="",
            shard="2/2",
            head="HEAD",
        )
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(destination)}):
            plan_lane(self.root, args, HostedLog(self.root, "plan"))
            plan = json.loads((self.root / "build/impact.json").read_text())
            matrix_lane(self.root, tuple(plan["projects"]), HostedLog(self.root, "matrix"))
        outputs = dict(line.split("=", 1) for line in destination.read_text().splitlines())
        selected = set(plan["projects"])
        self.assertEqual(outputs["scope"], "focused")
        self.assertEqual(set(outputs["projects"].split()), selected)
        self.assertEqual(json.loads(outputs["portable-matrix"])["os"], ["ubuntu-24.04"])
        self.assertEqual(outputs["has-projects"], "true")
        self.assertEqual(
            {entry["project"] for entry in json.loads(outputs["matrix"])["include"]},
            selected,
        )

    def test_focused_portable_lane_keeps_command_and_phase_logs(self) -> None:
        initialize_git(self.root)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic source",
            ),
            check=True,
            capture_output=True,
        )
        log = HostedLog(self.root, "portable")
        portable_lane(self.root, "focused", ("controller",), False, 2, log)
        log.finish()
        report = json.loads((self.root / "build/portable/portable.json").read_text())
        self.assertEqual(report["projects"], ["controller"])
        self.assertEqual(report["status"], "PASS")
        events = [json.loads(line) for line in log.events.read_text().splitlines()]
        self.assertTrue(
            any(item["stage"] == "portable-focused" and item["status"] == "PASS" for item in events)
        )
        self.assertTrue((log.directory / "portable-focused.stderr.log").is_file())

    def test_hosted_markdown_check_uses_the_installed_package_module(self) -> None:
        with patch.object(HostedLog, "run") as run:
            markdown_checks(self.root, HostedLog(self.root, "markdown"))
        commands = {call.args[0]: call.args[1] for call in run.call_args_list}
        self.assertEqual(
            commands["rumdl"],
            (
                sys.executable,
                "-I",
                "-m",
                "kicad_tooling.markdown_check",
                "check",
                ".",
                "--no-cache",
            ),
        )

    def test_failed_command_retains_stdout_stderr_and_exit_code(self) -> None:
        log = HostedLog(self.root, "failure-probe")
        with (
            redirect_stderr(StringIO()) as live,
            self.assertRaisesRegex(RuntimeError, "failed \\(7\\)"),
        ):
            log.run(
                "probe",
                (
                    sys.executable,
                    "-c",
                    'import sys; print("out"); print("err", file=sys.stderr); sys.exit(7)',
                ),
                cwd=self.root,
            )
        self.assertIn("out", (log.directory / "probe.stdout.log").read_text())
        self.assertIn("err", (log.directory / "probe.stderr.log").read_text())
        self.assertIn("out", live.getvalue())
        self.assertIn('"exit_code": 7', log.events.read_text())

    def test_electrical_lane_is_explicit_about_missing_and_pending_requirements(self) -> None:
        log = HostedLog(self.root, "electrical")
        electrical_lane(self.root, "controller", log)
        self.assertIn("NOT_CONFIGURED", log.events.read_text())
        with self.assertRaisesRegex(ValueError, "no electrical contract"):
            electrical_lane(self.root, "controller", log, required=True)
        init_electrical(self.root, "controller", "47")
        with self.assertRaisesRegex(ValueError, "unresolved electrical requirements"):
            electrical_lane(self.root, "controller", log)

    def test_declared_applicability_runs_in_hosted_lane_without_native_tools(self) -> None:
        setup = init_electrical(self.root, "controller", "47")
        na = AnalysisNotApplicable(
            mode="not_applicable", reason="Synthetic orchestration test only"
        )
        write_model(
            self.root / setup.contract,
            ElectricalAnalysisContract(
                project_id="controller",
                ngspice_version="47",
                grounding=na,
                pcb_return_paths=na,
                power=na,
                high_frequency=na,
                test_access=na,
            ),
        )
        log = HostedLog(self.root, "electrical")
        electrical_lane(self.root, "controller", log)
        report = json.loads((self.root / "build/electrical-controller.json").read_text())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual({row["status"] for row in report["checks"]}, {"NOT_APPLICABLE"})
        from kicad_tooling.ci_matrix import build_matrix

        self.assertTrue(build_matrix(self.root, ("controller",)).include[0].electrical)

    def test_pcb_return_fixture_checks_native_connectivity_zone_via_and_net_tie_evidence(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_return_fixture_lane
        from kicad_tooling.hwrepo.contracts import repo_path
        from kicad_tooling.hwrepo.electrical import selected_config
        from kicad_tooling.hwrepo.evidence import digest
        from kicad_tooling.hwrepo.pcb_return_paths import expected_probe_sha256

        config = selected_config(self.root, "controller")
        observed_boards: list[Path] = []

        def capture(
            root: Path, selected: ProjectConfig, output: Path
        ) -> tuple[CommandEvidence, PcbConnectivitySnapshot]:
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(selected.image, config.image)
            self.assertEqual(selected.kicad_version, config.kicad_version)
            board = repo_path(root, selected.project).with_suffix(".kicad_pcb")
            content = board.read_text(encoding="utf-8")
            self.assertTrue(output.is_relative_to(root))
            output.mkdir()
            observed_boards.append(board)
            fixture_id = Path(selected.project).stem
            is_via_fixture = fixture_id.startswith("alternate-layer-")
            is_plane_fixture = fixture_id in {"unstitched-planes", "stitched-planes"}
            is_zone_fixture = fixture_id.startswith("zone-") or is_plane_fixture
            is_unanchored_zone = fixture_id == "zone-unanchored-island"
            is_tie_fixture = fixture_id.startswith("net-tie-")
            is_isolation_fixture = fixture_id.startswith("isolation-")
            is_isolation_bridge = fixture_id == "isolation-bridged"
            tie_dnp = fixture_id == "net-tie-dnp"
            expected_connected = fixture_id in {
                "alternate-layer-via",
                "stitched-planes",
                "zone-connected",
                "zone-unanchored-island",
                "net-tie-connected",
                "isolation-open",
                "isolation-bridged",
            }
            is_split_zone = is_zone_fixture and ("split" in fixture_id or is_unanchored_zone)
            expected_islands = 2 if is_split_zone else 1
            expected_island_indices = (
                (0, 0) if is_unanchored_zone else (0, 1) if is_split_zone else (0, 0)
            )
            if is_via_fixture:
                self.assertIn('(layers "F.Cu" "B.Cu")', content)
                self.assertIn('(layer "F.Cu") (net 1)', content)
                if expected_connected:
                    self.assertIn("(segment (start 10 5) (end 15 5)", content)
                else:
                    self.assertNotIn("(segment (start 10 5) (end 15 5)", content)
            if is_zone_fixture:
                self.assertIn('(zone (net 1) (net_name "RETURN")', content)
                if expected_islands == 2:
                    if is_unanchored_zone:
                        self.assertIn("(segment (start -1 7) (end 21 7)", content)
                        self.assertIn("(island_removal_mode 1)", content)
                    else:
                        self.assertIn("(segment (start 10 -1) (end 10 11)", content)
            if is_plane_fixture:
                self.assertEqual(
                    content.count('(zone (net 1) (net_name "RETURN") (layer "F.Cu")'), 1
                )
                self.assertEqual(
                    content.count('(zone (net 1) (net_name "RETURN") (layer "B.Cu")'), 1
                )
                if fixture_id == "stitched-planes":
                    self.assertIn("(via (at 10 5) (size 0.8) (drill 0.3)", content)
                else:
                    self.assertNotIn("(via ", content)
            if is_tie_fixture:
                self.assertIn('(net_tie_pad_groups "1,2")', content)
                if tie_dnp:
                    self.assertIn("(attr smd dnp)", content)
            if is_isolation_fixture:
                self.assertIn('(net 1 "RETURN_A")', content)
                self.assertIn('(net 2 "RETURN_B")', content)
                if is_isolation_bridge:
                    self.assertIn('(net_tie_pad_groups "1,2")', content)
            connected_pads = ("J1.1", "J2.1") if expected_connected else ("J1.1",)
            connected_j2 = ("J1.1", "J2.1") if expected_connected else ("J2.1",)
            via_id = "d" * 64
            first_connected_vias = (
                (via_id,) if is_via_fixture or (is_plane_fixture and expected_connected) else ()
            )
            second_connected_vias = (
                (via_id,) if expected_connected and (is_via_fixture or is_plane_fixture) else ()
            )
            via_inventory = (
                (
                    PcbViaObservation(
                        id=via_id,
                        net="RETURN",
                        x_nm=10_000_000,
                        y_nm=5_000_000,
                        start_layer="F.Cu",
                        end_layer="B.Cu",
                        diameter_nm=800_000,
                        drill_nm=300_000,
                        kind="through",
                        multiplicity=1,
                    ),
                )
                if is_via_fixture or (is_plane_fixture and expected_connected)
                else ()
            )
            track_inventory = (
                (
                    PcbTrackObservation(
                        uuid="00000000-0000-0000-0000-000000000011",
                        net="RETURN",
                        layer="F.Cu",
                        width_nm=300_000,
                        start_nm=(5_000_000, 5_000_000),
                        end_nm=(10_000_000, 5_000_000),
                        geometry_kind="segment",
                        start_pads=("J1.1",),
                        end_pads=(),
                        start_vias=(),
                        end_vias=(via_id,),
                    ),
                    *(
                        (
                            PcbTrackObservation(
                                uuid="00000000-0000-0000-0000-000000000012",
                                net="RETURN",
                                layer="B.Cu",
                                width_nm=300_000,
                                start_nm=(10_000_000, 5_000_000),
                                end_nm=(15_000_000, 5_000_000),
                                geometry_kind="segment",
                                start_pads=(),
                                end_pads=("J2.1",),
                                start_vias=(via_id,),
                                end_vias=(),
                            ),
                        )
                        if expected_connected
                        else ()
                    ),
                )
                if is_via_fixture
                else ()
            )
            zone_identity = PcbZoneIdentity(
                uuid="00000000-0000-0000-0000-000000000001",
                layer="F.Cu",
            )
            back_zone_identity = PcbZoneIdentity(
                uuid="00000000-0000-0000-0000-000000000002",
                layer="B.Cu",
            )
            second_zone_identity = back_zone_identity if is_plane_fixture else zone_identity
            first_island = PcbZoneIslandIdentity(
                uuid=zone_identity.uuid,
                layer=zone_identity.layer,
                island_index=expected_island_indices[0],
            )
            second_island = PcbZoneIslandIdentity(
                uuid=second_zone_identity.uuid,
                layer=second_zone_identity.layer,
                island_index=expected_island_indices[1],
            )
            if is_tie_fixture:
                endpoint_pads = (
                    PcbPadConnectivityObservation(
                        pad="J1.1",
                        net="RETURN_A",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=("J1.1", "NT1.1"),
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                    PcbPadConnectivityObservation(
                        pad="J2.1",
                        net="RETURN_B",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=("J2.1", "NT1.2"),
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                )
                tie_pads = (
                    PcbPadConnectivityObservation(
                        pad="NT1.1",
                        net="RETURN_A",
                        footprint="Synthetic:NetTie-2",
                        dnp=tie_dnp,
                        connected_pads=("J1.1", "NT1.1"),
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                    PcbPadConnectivityObservation(
                        pad="NT1.2",
                        net="RETURN_B",
                        footprint="Synthetic:NetTie-2",
                        dnp=tie_dnp,
                        connected_pads=("J2.1", "NT1.2"),
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    ),
                )
            elif is_isolation_fixture:
                a_members = ("J1.1", "J3.1") + (("NT1.1",) if is_isolation_bridge else ())
                b_members = ("J2.1", "J4.1") + (("NT1.2",) if is_isolation_bridge else ())
                endpoint_pads = tuple(
                    PcbPadConnectivityObservation(
                        pad=reference,
                        net="RETURN_A" if reference in {"J1.1", "J3.1"} else "RETURN_B",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=members,
                        connected_zones=(),
                        connected_islands=(),
                        connected_vias=(),
                    )
                    for members, references in (
                        (a_members, ("J1.1", "J3.1")),
                        (b_members, ("J2.1", "J4.1")),
                    )
                    for reference in references
                )
                tie_pads = (
                    (
                        PcbPadConnectivityObservation(
                            pad="NT1.1",
                            net="RETURN_A",
                            footprint="Synthetic:NetTie-2",
                            dnp=False,
                            connected_pads=a_members,
                            connected_zones=(),
                            connected_islands=(),
                            connected_vias=(),
                        ),
                        PcbPadConnectivityObservation(
                            pad="NT1.2",
                            net="RETURN_B",
                            footprint="Synthetic:NetTie-2",
                            dnp=False,
                            connected_pads=b_members,
                            connected_zones=(),
                            connected_islands=(),
                            connected_vias=(),
                        ),
                    )
                    if is_isolation_bridge
                    else ()
                )
            else:
                endpoint_pads = (
                    PcbPadConnectivityObservation(
                        pad="J1.1",
                        net="RETURN",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=connected_pads,
                        connected_zones=(zone_identity,) if is_zone_fixture else (),
                        connected_islands=(first_island,) if is_zone_fixture else (),
                        connected_vias=first_connected_vias,
                    ),
                    PcbPadConnectivityObservation(
                        pad="J2.1",
                        net="RETURN",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=connected_j2,
                        connected_zones=(second_zone_identity,) if is_zone_fixture else (),
                        connected_islands=(second_island,) if is_zone_fixture else (),
                        connected_vias=second_connected_vias,
                    ),
                )
                tie_pads = ()
            if is_plane_fixture:
                zone_observations = (
                    PcbZoneObservation(
                        uuid=zone_identity.uuid,
                        layer=zone_identity.layer,
                        name="",
                        net="RETURN",
                        filled_island_count=1,
                        unanchored_pad_island_indexes=(),
                    ),
                    PcbZoneObservation(
                        uuid=back_zone_identity.uuid,
                        layer=back_zone_identity.layer,
                        name="",
                        net="RETURN",
                        filled_island_count=1,
                        unanchored_pad_island_indexes=(),
                    ),
                )
            elif is_zone_fixture:
                zone_observations = (
                    PcbZoneObservation(
                        uuid=zone_identity.uuid,
                        layer=zone_identity.layer,
                        name="",
                        net="RETURN",
                        filled_island_count=expected_islands,
                        unanchored_pad_island_indexes=(1,) if is_unanchored_zone else (),
                    ),
                )
            else:
                zone_observations = ()
            snapshot = PcbConnectivitySnapshot(
                board_sha256=digest(board),
                kicad_version=selected.kicad_version,
                image=selected.image,
                probe_sha256=expected_probe_sha256(),
                zones_refilled=True,
                pads=(*endpoint_pads, *tie_pads),
                net_ties=(
                    PcbNetTieObservation(
                        reference="NT1",
                        footprint="Synthetic:NetTie-2",
                        dnp=tie_dnp,
                        pad_groups=(("NT1.1", "NT1.2"),),
                    ),
                )
                if is_tie_fixture or is_isolation_bridge
                else (),
                zones=zone_observations,
                vias=via_inventory,
                tracks=track_inventory,
            )
            board_argument = "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix()
            return (
                CommandEvidence(
                    argv=(
                        "docker",
                        "run",
                        "--rm",
                        "--platform",
                        "linux/amd64",
                        "--network",
                        "none",
                        "--read-only",
                        "--tmpfs",
                        "/tmp:rw,nosuid,nodev,size=64m",
                        "-v",
                        f"{root}:/work:ro",
                        "-v",
                        f"{output}:/output:rw",
                        "-w",
                        "/work",
                        "--entrypoint",
                        "/usr/bin/python3",
                        selected.image,
                        "-I",
                        "-B",
                        "/output/native_pcb_probe.py",
                        board_argument,
                        "/output/snapshot.json",
                    ),
                    started_utc="2026-01-01T00:00:00Z",
                    returncode=0,
                ),
                snapshot,
            )

        log = HostedLog(self.root, "native-pcb-fixture")
        with patch(
            "kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity",
            side_effect=capture,
        ) as run_probe:
            pcb_return_fixture_lane(self.root, project="controller", image=config.image, log=log)

        self.assertEqual(run_probe.call_count, 14)
        self.assertEqual(len(observed_boards), 14)
        self.assertTrue(all(board.is_file() for board in observed_boards))
        events = [json.loads(line) for line in log.events.read_text().splitlines()]
        results = {
            event["stage"]: event
            for event in events
            if event["stage"].startswith("pcb-return-fixture/")
        }
        for fixture_id, connectivity in (
            ("alternate-layer-via", "connected"),
            ("alternate-layer-open", "open"),
            ("zone-connected", "connected"),
            ("unstitched-planes", "open"),
            ("stitched-planes", "connected"),
            ("zone-unanchored-island", "connected"),
            ("zone-split", "open"),
            ("zone-through-hole-split", "open"),
            ("net-tie-connected", "connected"),
            ("net-tie-dnp", "open"),
            ("isolation-open", "connected"),
            ("isolation-bridged", "connected"),
        ):
            with self.subTest(fixture=fixture_id):
                result = results[f"pcb-return-fixture/{fixture_id}"]
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["kicad_version"], config.kicad_version)
                self.assertEqual(result["expected_connectivity"], connectivity)
                if fixture_id == "alternate-layer-via":
                    self.assertEqual(result["via_identity_repeatable"], "true")
                if fixture_id == "stitched-planes":
                    self.assertEqual(result["plane_stitch_repeatable"], "true")
                    self.assertEqual(result["zone_layers"], "F.Cu,B.Cu")
                if fixture_id.startswith("isolation-"):
                    self.assertEqual(
                        result["expected_isolation"],
                        "separate" if fixture_id == "isolation-open" else "bridged",
                    )
                self.assertTrue((self.root / result["receipt"]).is_relative_to(self.root))

    def test_pcb_access_fixture_checks_native_probe_faults_controls_and_repeatability(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_access_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config
        from kicad_tooling.hwrepo.evidence import digest
        from kicad_tooling.hwrepo.models import (
            CommandEvidence,
            PcbAccessProbeObservation,
            PcbConnectivitySnapshot,
            PcbPadConnectivityObservation,
        )
        from kicad_tooling.hwrepo.pcb_return_paths import expected_probe_sha256

        config = selected_config(self.root, "controller")
        captured: list[tuple[Path, tuple[PcbAccessProbeRequest, ...]]] = []

        def capture(
            root: Path,
            selected: ProjectConfig,
            output: Path,
            requests: PcbAccessProbeRequestSet,
        ) -> tuple[CommandEvidence, PcbConnectivitySnapshot]:
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(selected.image, config.image)
            self.assertEqual(selected.kicad_version, config.kicad_version)
            board = root / Path(selected.project).with_suffix(".kicad_pcb")
            self.assertTrue(board.is_file())
            output.mkdir()
            request_path = output / "access-probe-requests.json"
            write_model(request_path, requests)
            captured.append((board, tuple(requests.requests)))
            observations = (
                PcbAccessProbeObservation(
                    endpoint="J1.1",
                    side="front",
                    target_net="TARGET_ACCESS",
                    target_exposed=True,
                    obstacle="J4.1",
                    obstacle_net="FOREIGN_FRONT",
                    distance_nm=400_000,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=1_200_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J1.1",
                    side="back",
                    target_net="TARGET_ACCESS",
                    target_exposed=True,
                    obstacle="J5.1",
                    obstacle_net="FOREIGN_BACK",
                    distance_nm=800_000,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=1_200_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J7.1",
                    side="front",
                    target_net="TARGET_NO_NET_NEIGHBOR",
                    target_exposed=True,
                    obstacle="J8.1",
                    obstacle_net=None,
                    distance_nm=400_000,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=800_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J9.1",
                    side="front",
                    target_net="TARGET_FRONT_ONLY",
                    target_exposed=True,
                    obstacle="J10.1",
                    obstacle_net="FOREIGN_FRONT_ONLY",
                    distance_nm=400_000,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=300_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J9.1",
                    side="back",
                    target_net="TARGET_FRONT_ONLY",
                    target_exposed=False,
                    obstacle=None,
                    obstacle_net=None,
                    distance_nm=None,
                    target_aperture_shape=None,
                    target_aperture_diameter_nm=None,
                ),
                PcbAccessProbeObservation(
                    endpoint="J11.1",
                    side="front",
                    target_net="TARGET_APERTURE_SMALL",
                    target_exposed=True,
                    obstacle="J12.1",
                    obstacle_net="TARGET_APERTURE_BOUNDARY",
                    distance_nm=9_500_001,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=400_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J12.1",
                    side="front",
                    target_net="TARGET_APERTURE_BOUNDARY",
                    target_exposed=True,
                    obstacle="J13.1",
                    obstacle_net="TARGET_APERTURE_RECT",
                    distance_nm=9_500_000,
                    target_aperture_shape="circle",
                    target_aperture_diameter_nm=800_000,
                ),
                PcbAccessProbeObservation(
                    endpoint="J13.1",
                    side="front",
                    target_net="TARGET_APERTURE_RECT",
                    target_exposed=True,
                    obstacle="J12.1",
                    obstacle_net="TARGET_APERTURE_BOUNDARY",
                    distance_nm=9_500_001,
                    target_aperture_shape="unsupported",
                    target_aperture_diameter_nm=None,
                ),
                PcbAccessProbeObservation(
                    endpoint="J14.1",
                    side="front",
                    target_net="TARGET_APERTURE_DRILLED",
                    target_exposed=True,
                    obstacle="J13.1",
                    obstacle_net="TARGET_APERTURE_RECT",
                    distance_nm=9_500_000,
                    target_aperture_shape="unsupported",
                    target_aperture_diameter_nm=None,
                ),
            )
            pads = tuple(
                PcbPadConnectivityObservation(
                    pad=reference,
                    net=net,
                    footprint=footprint,
                    dnp=dnp,
                    connected_pads=(reference,),
                    connected_zones=(),
                    connected_islands=(),
                    connected_vias=(),
                    positions_nm=((0, 0),),
                )
                for reference, net, footprint, dnp in (
                    ("J1.1", "TARGET_ACCESS", "Synthetic:AccessTarget", False),
                    ("J2.1", "TARGET_ACCESS", "Synthetic:AccessNeighbor", False),
                    ("J3.1", "FOREIGN_DNP", "Synthetic:AccessNeighbor", True),
                    ("J4.1", "FOREIGN_FRONT", "Synthetic:AccessNeighbor", False),
                    ("J5.1", "FOREIGN_BACK", "Synthetic:AccessNeighbor", False),
                    (
                        "J7.1",
                        "TARGET_NO_NET_NEIGHBOR",
                        "Synthetic:AccessTarget",
                        False,
                    ),
                    ("J8.1", None, "Synthetic:AccessNeighbor", False),
                    ("J9.1", "TARGET_FRONT_ONLY", "Synthetic:AccessTarget", False),
                    ("J10.1", "FOREIGN_FRONT_ONLY", "Synthetic:AccessNeighbor", False),
                    (
                        "J11.1",
                        "TARGET_APERTURE_SMALL",
                        "Synthetic:AccessTarget",
                        False,
                    ),
                    (
                        "J12.1",
                        "TARGET_APERTURE_BOUNDARY",
                        "Synthetic:AccessTarget",
                        False,
                    ),
                    (
                        "J13.1",
                        "TARGET_APERTURE_RECT",
                        "Synthetic:AccessTarget",
                        False,
                    ),
                    (
                        "J14.1",
                        "TARGET_APERTURE_DRILLED",
                        "Synthetic:AccessTarget",
                        False,
                    ),
                )
            )
            snapshot = PcbConnectivitySnapshot(
                schema_version="10",
                board_sha256=digest(board),
                kicad_version=selected.kicad_version,
                image=selected.image,
                probe_sha256=expected_probe_sha256(),
                zones_refilled=True,
                pads=pads,
                net_ties=(),
                zones=(),
                vias=(),
                access_probe_observations=observations,
                access_probe_requests_sha256=digest(request_path),
                tracks=(),
                copper_layers=("F.Cu", "B.Cu"),
            )
            board_argument = "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix()
            command = CommandEvidence(
                argv=(
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,nosuid,nodev,size=64m",
                    "-v",
                    f"{root}:/work:ro",
                    "-v",
                    f"{output}:/output:rw",
                    "-w",
                    "/work",
                    "--entrypoint",
                    "/usr/bin/python3",
                    selected.image,
                    "-I",
                    "-B",
                    "/output/native_pcb_probe.py",
                    board_argument,
                    "/output/snapshot.json",
                    "/output/access-probe-requests.json",
                ),
                started_utc="2026-01-01T00:00:00Z",
                returncode=0,
            )
            return command, snapshot

        log = HostedLog(self.root, "native-pcb-access-fixture")
        with patch(
            "kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity",
            side_effect=capture,
        ) as run_probe:
            pcb_access_fixture_lane(
                self.root,
                project="controller",
                image=config.image,
                log=log,
            )

        self.assertEqual(run_probe.call_count, 2)
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0][0].read_bytes(), captured[1][0].read_bytes())
        self.assertEqual(captured[0][1], captured[1][1])
        requests = {(item.endpoint, item.side) for item in captured[0][1]}
        self.assertEqual(
            requests,
            {
                ("J1.1", "front"),
                ("J1.1", "back"),
                ("J7.1", "front"),
                ("J9.1", "front"),
                ("J9.1", "back"),
                ("J11.1", "front"),
                ("J12.1", "front"),
                ("J13.1", "front"),
                ("J14.1", "front"),
            },
        )
        result = next(
            json.loads(line)
            for line in log.events.read_text().splitlines()
            if json.loads(line).get("stage") == "pcb-access-fixture/probe-envelope"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["kicad_version"], config.kicad_version)
        self.assertEqual(result["repeatable"], "true")
        self.assertTrue((self.root / result["receipt"]).is_relative_to(self.root))

    def test_pcb_return_fixture_rejects_an_untested_kicad_minor_before_native_execution(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_return_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        config = selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-fixture-version")
        with (
            patch(
                "kicad_tooling.hwrepo.electrical.selected_config",
                return_value=unsupported,
            ),
            patch("kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_return_fixture_lane(self.root, project="controller", image=config.image, log=log)
        probe.assert_not_called()

    def test_pcb_access_fixture_rejects_an_untested_kicad_minor_before_native_execution(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_access_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        config = selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-access-fixture-version")
        with (
            patch(
                "kicad_tooling.hwrepo.electrical.selected_config",
                return_value=unsupported,
            ),
            patch("kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_access_fixture_lane(self.root, project="controller", image=config.image, log=log)
        probe.assert_not_called()

    def test_pcb_decoupling_fixture_rejects_an_untested_kicad_minor_before_native_execution(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_decoupling_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        config = selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-decoupling-fixture-version")
        with (
            patch(
                "kicad_tooling.hwrepo.electrical.selected_config",
                return_value=unsupported,
            ),
            patch("kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_decoupling_fixture_lane(
                self.root,
                project="controller",
                image=config.image,
                log=log,
            )
        probe.assert_not_called()

    def test_pcb_switching_loop_fixture_rejects_an_untested_kicad_minor(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_switching_loop_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        config = selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-switching-loop-fixture-version")
        with (
            patch(
                "kicad_tooling.hwrepo.electrical.selected_config",
                return_value=unsupported,
            ),
            patch("kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_switching_loop_fixture_lane(
                self.root,
                project="controller",
                image=config.image,
                log=log,
            )
        probe.assert_not_called()

    def test_reference_plane_via_fixture_rejects_an_untested_kicad_minor(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import (
            pcb_reference_plane_narrow_void_fixture_lane,
            pcb_reference_plane_via_fixture_lane,
        )
        from kicad_tooling.hwrepo.electrical import selected_config

        config = selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-reference-via-fixture-version")
        with (
            patch(
                "kicad_tooling.hwrepo.electrical.selected_config",
                return_value=unsupported,
            ),
            patch("kicad_tooling.hwrepo.pcb_return_paths.capture_native_pcb_connectivity") as probe,
        ):
            for lane in (
                pcb_reference_plane_via_fixture_lane,
                pcb_reference_plane_narrow_void_fixture_lane,
            ):
                with (
                    self.subTest(lane=lane.__name__),
                    self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
                ):
                    lane(
                        self.root,
                        project="controller",
                        image=config.image,
                        log=log,
                    )
        probe.assert_not_called()

    def test_release_rehearsal_restores_examples_after_adoption_without_copying_live_data(
        self,
    ) -> None:
        self.assertEqual(initialize(self.root, "adopted-team").status, "PASS")
        private_paths = (
            "projects/private-board/design.txt",
            "products/private-product/design.txt",
            "libraries/private-library/design.txt",
            "hardware/private-board/design.txt",
        )
        for name in private_paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "Private live source must remain outside rehearsal.\n", encoding="utf-8"
            )
        (self.root / "kicad-tooling.toml").write_text(
            '[layout]\ndiscovery = "private-catalog/projects.json"\n'
            'products = "private-catalog/products.json"\nnew_project_root = "hardware"\n',
            encoding="utf-8",
        )
        (self.root / "LICENSE").write_text("Adopter-specific notice.\n", encoding="utf-8")
        # Neither live default catalogs nor custom layout catalogs define the fixture.
        (self.root / "catalog/projects.json").write_text("{}\n", encoding="utf-8")
        preserved = {
            name: (self.root / name).read_bytes()
            for name in (
                *private_paths,
                "kicad-tooling.toml",
                "template-adoption.json",
                "LICENSE",
                "catalog/projects.json",
                "examples/projects/arduino-uno-status-led/project.json",
            )
        }
        log = HostedLog(self.root, "release-fixture")
        run = log.run
        target = self.root / "build/rehearsal-source"

        def stop_before_native(
            stage: str, argv: tuple[str, ...], *, cwd: Path, **kwargs: object
        ) -> Path:
            if stage == "release-prepare":
                self.assertEqual(cwd, target)
                self.assertEqual(layout(cwd), RepositoryLayout())
                self.assertEqual(preflight(cwd).status, "PASS")
                self.assertEqual(
                    {project.id for project in load_registry(cwd).projects},
                    {project.id for project in load_registry(reference_root()).projects},
                )
                self.assertIn("arduino-uno-status-led", argv)
                raise RuntimeError("Native release reached with public reference catalog")
            self.assertFalse(kwargs)
            return run(stage, argv, cwd=cwd)

        with (
            patch.object(log, "run", side_effect=stop_before_native),
            self.assertRaisesRegex(
                RuntimeError, "Native release reached with public reference catalog"
            ),
        ):
            release_lane(self.root, log)
        for name, original in preserved.items():
            self.assertEqual((self.root / name).read_bytes(), original, name)
        for name in (*private_paths, "kicad-tooling.toml", "template-adoption.json"):
            self.assertFalse((target / name).exists(), name)
        self.assertEqual(
            (target / "LICENSE").read_bytes(),
            (TEST_ROOT / "fixtures/scaffold-license.txt").read_bytes(),
        )
        self.assertEqual(
            (target / "catalog/projects.json").read_bytes(),
            (self.root / "examples/catalog/projects.json").read_bytes(),
        )
        manifest = json.loads(
            (target / "examples/projects/arduino-uno-status-led/project.json").read_text()
        )
        self.assertEqual(
            manifest["release_exports"]["supplier_formats"], ["odb", "ipc2581", "ipcd356"]
        )
        status = subprocess.run(
            ("git", "status", "--porcelain=v1"),
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(status.stdout, "")

    def test_release_rehearsal_requires_public_reference_fixtures(self) -> None:
        (self.root / "examples/catalog/projects.json").unlink()
        target = self.root / "build/rehearsal-source"
        with self.assertRaisesRegex(ValueError, "restore.*examples/catalog/projects.json"):
            release_fixture(self.root, target)
        self.assertFalse(target.exists())

    def test_release_rehearsal_rejects_public_fixture_symlinks_into_private_data(self) -> None:
        private = self.root / "projects/private-board"
        private.mkdir()
        (private / "secret.txt").write_text("Private source\n", encoding="utf-8")
        (self.root / "examples/projects/private-link").symlink_to(private, target_is_directory=True)
        target = self.root / "build/rehearsal-source"
        with self.assertRaisesRegex(ValueError, "must not follow a symlink"):
            release_fixture(self.root, target)
        self.assertFalse(target.exists())

    def test_final_gate_requires_rehearsal_only_for_complete_live_scope(self) -> None:
        gate_result("success", "focused", "success", "success", "success", "true", "skipped")
        gate_result("success", "full", "success", "success", "success", "true", "success")
        with self.assertRaises(ValueError):
            gate_result("success", "full", "success", "success", "success", "true", "skipped")
        with self.assertRaises(ValueError):
            gate_result("success", "focused", "success", "success", "skipped", "true", "skipped")


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") == "1",
    "native PCB fixtures run in the digest-pinned package acceptance lane",
)
class NativePcbAccessFixtureTests(unittest.TestCase):
    def test_native_probe_envelope_fixtures_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, pcb_access_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-pcb-access-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-pcb-access-{project}")
                pcb_access_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                result = next(
                    item
                    for item in events
                    if item.get("stage") == "pcb-access-fixture/probe-envelope"
                )
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["kicad_version"], version)
                self.assertEqual(result["repeatable"], "true")

    def test_pcb_geometry_probe_controls_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import (
            HostedLog,
            pcb_decoupling_fixture_lane,
            pcb_reference_plane_narrow_void_fixture_lane,
            pcb_reference_plane_via_fixture_lane,
            pcb_return_fixture_lane,
            pcb_switching_loop_fixture_lane,
        )
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-pcb-decoupling-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        reference_via_coverages: list[str] = []
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-pcb-decoupling-{project}")
                pcb_decoupling_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                result = next(
                    item
                    for item in events
                    if item.get("stage") == "pcb-decoupling-fixture/placement"
                )
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["kicad_version"], version)
                self.assertEqual(result["near_distance_nm"], 1_000_000)
                self.assertEqual(result["distant_distance_nm"], 15_000_000)
                self.assertEqual(result["connected_return_via_distance_nm"], 1_000_000)
                self.assertEqual(result["distant_return_via_fault_distance_nm"], 2_000_000)
                self.assertEqual(result["repeatable"], "true")
                protection_result = next(
                    item
                    for item in events
                    if item.get("stage") == "pcb-protection-path-fixture/entry"
                )
                self.assertEqual(protection_result["status"], "PASS")
                self.assertEqual(protection_result["kicad_version"], version)
                self.assertEqual(protection_result["connector_to_protector_distance_nm"], 650_000)
                self.assertEqual(protection_result["connected_reference_vias"], 1)
                self.assertEqual(protection_result["distance_fault_limit_um"], 649)
                self.assertEqual(protection_result["via_count_fault_minimum"], 2)
                self.assertEqual(
                    protection_result["nearby_reference_via_pad_distance_nm"], 1_500_000
                )
                self.assertEqual(protection_result["nearby_reference_via_radius_um"], 2000)
                self.assertEqual(protection_result["connected_vias_for_nearby_open_fault"], 0)
                self.assertEqual(protection_result["repeatable"], "true")
                self.assertEqual(len(protection_result["disconnected_signal_fault_sha256"]), 64)
                self.assertEqual(
                    len(protection_result["disconnected_nearby_reference_via_fault_sha256"]), 64
                )
                self.assertTrue(protection_result["receipt"].endswith("/protection-first"))
                width_result = next(
                    item for item in events if item.get("stage") == "pcb-track-width-fixture/screen"
                )
                self.assertEqual(width_result["status"], "PASS")
                self.assertEqual(width_result["kicad_version"], version)
                self.assertEqual(width_result["measured_width_nm"], 250_000)
                self.assertEqual(width_result["boundary_minimum_um"], 250)
                self.assertEqual(width_result["fault_minimum_um"], 251)
                self.assertEqual(width_result["repeatable"], "true")

                switching_log = HostedLog(root, f"native-pcb-switching-loop-{project}")
                pcb_switching_loop_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=switching_log,
                )
                switching_events = tuple(
                    json.loads(line) for line in switching_log.events.read_text().splitlines()
                )
                loop_results = tuple(
                    item
                    for item in switching_events
                    if item.get("stage", "").startswith("pcb-switching-loop-fixture/")
                )
                self.assertEqual(
                    {item["stage"] for item in loop_results},
                    {
                        "pcb-switching-loop-fixture/front-plane",
                        "pcb-switching-loop-fixture/arc-trace",
                        "pcb-switching-loop-fixture/inner-plane",
                        "pcb-switching-loop-fixture/split-inner-plane",
                    },
                )
                self.assertTrue(all(item["status"] == "PASS" for item in loop_results))
                front_plane_result = next(
                    item
                    for item in loop_results
                    if item["stage"] == "pcb-switching-loop-fixture/front-plane"
                )
                self.assertEqual(front_plane_result["resolved_trace_length_nm"], 15_000_000)
                self.assertGreater(front_plane_result["plane_contour_area_twice_nm2"], 0)
                arc_trace_result = next(
                    item
                    for item in loop_results
                    if item["stage"] == "pcb-switching-loop-fixture/arc-trace"
                )
                self.assertEqual(arc_trace_result["status"], "PASS")
                self.assertEqual(arc_trace_result["resolved_trace_length_nm"], "UNSUPPORTED_ARC")
                self.assertGreater(arc_trace_result["plane_contour_area_twice_nm2"], 0)
                inner_plane_result = next(
                    item
                    for item in loop_results
                    if item["stage"] == "pcb-switching-loop-fixture/inner-plane"
                )
                self.assertEqual(inner_plane_result["plane_contour_area_twice_nm2"], "NOT_TESTED")
                self.assertGreaterEqual(inner_plane_result["native_hole_ring_count"], 1)
                self.assertEqual(
                    inner_plane_result["clearance_hole_bounds_nm"],
                    "12399500,12399500,13600500,13600500",
                )
                reference_plane_result = next(
                    item
                    for item in switching_events
                    if item.get("stage") == "pcb-reference-plane-fixture/inner-plane"
                )
                self.assertEqual(reference_plane_result["status"], "PASS")
                self.assertEqual(reference_plane_result["kicad_version"], version)
                self.assertEqual(reference_plane_result["covered_fraction"], "4/15")
                self.assertEqual(reference_plane_result["fault_threshold"], 0.3)
                self.assertEqual(reference_plane_result["control_threshold"], 0.25)
                self.assertEqual(reference_plane_result["below_fault_threshold"], "true")
                self.assertEqual(reference_plane_result["repeatable"], "true")

                via_log = HostedLog(root, f"native-pcb-reference-via-{project}")
                pcb_reference_plane_via_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=via_log,
                )
                via_result = next(
                    item
                    for item in (
                        json.loads(line) for line in via_log.events.read_text().splitlines()
                    )
                    if item.get("stage") == "pcb-reference-plane-fixture/via-antipad"
                )
                self.assertEqual(via_result["status"], "PASS")
                self.assertEqual(via_result["kicad_version"], version)
                self.assertEqual(via_result["fault_threshold"], 0.75)
                self.assertEqual(via_result["control_threshold"], 0.5)
                self.assertEqual(via_result["intervals_remain_uncovered"], "true")
                self.assertEqual(via_result["repeatable"], "true")
                reference_via_coverages.append(via_result["covered_fraction"])

                narrow_void_log = HostedLog(root, f"native-pcb-reference-narrow-void-{project}")
                pcb_reference_plane_narrow_void_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=narrow_void_log,
                )
                narrow_void_result = next(
                    item
                    for item in (
                        json.loads(line) for line in narrow_void_log.events.read_text().splitlines()
                    )
                    if item.get("stage") == "pcb-reference-plane-fixture/narrow-void"
                )
                self.assertEqual(narrow_void_result["status"], "PASS")
                self.assertEqual(narrow_void_result["kicad_version"], version)
                self.assertEqual(narrow_void_result["minimum_fraction"], 0.65)
                from fractions import Fraction

                control_fraction = Fraction(narrow_void_result["control_coverage"])
                fault_fraction = Fraction(narrow_void_result["fault_coverage"])
                self.assertGreaterEqual(control_fraction, Fraction("0.65"))
                self.assertLess(fault_fraction, Fraction("0.65"))
                self.assertGreater(control_fraction, fault_fraction)
                self.assertEqual(narrow_void_result["control_below_threshold"], "false")
                self.assertEqual(narrow_void_result["fault_below_threshold"], "true")
                self.assertEqual(narrow_void_result["endpoint_via_hole_context"], "retained")
                self.assertEqual(narrow_void_result["repeatable"], "true")

                return_log = HostedLog(root, f"native-pcb-return-{project}")
                pcb_return_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=return_log,
                )
        self.assertEqual(len(set(reference_via_coverages)), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") == "1",
    "native connector fixtures run in the digest-pinned package acceptance lane",
)
class NativeConnectorReturnFixtureTests(unittest.TestCase):
    def test_native_netlist_split_return_fault_and_common_return_control(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, connector_return_lint_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-connector-return-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        normalized_pattern_hashes: dict[str, dict[str, str]] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-connector-return-{project}")
                connector_return_lint_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("connector-return-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "connector-return-fixture/native-export",
                        "connector-return-fixture/fault",
                        "connector-return-fixture/control",
                        "connector-return-fixture/unconnected-generic-power-input-fault",
                        "connector-return-fixture/unconnected-generic-power-input-control",
                        "connector-return-fixture/unconnected-generic-component-power-input-fault",
                        "connector-return-fixture/unconnected-generic-component-power-input-control",
                        "connector-return-fixture/unconnected-generic-component-power-input-no-connect-fault",
                        "connector-return-fixture/unconnected-generic-component-power-input-dnp-control",
                        "connector-return-fixture/cross-symbol-fault",
                        "connector-return-fixture/cross-symbol-control",
                        "connector-return-fixture/cross-symbol-open",
                        "connector-return-fixture/mapped-supply-fault",
                        "connector-return-fixture/mapped-supply-control",
                        "connector-return-fixture/channel-power-fault",
                        "connector-return-fixture/channel-power-control",
                        "connector-return-fixture/peer-power-fault",
                        "connector-return-fixture/peer-power-control",
                        "connector-return-fixture/peer-pin-outlier-fault",
                        "connector-return-fixture/peer-pin-outlier-control",
                        "connector-return-fixture/two-peer-open-fault",
                        "connector-return-fixture/two-peer-no-connect-fault",
                        "connector-return-fixture/two-peer-common-control",
                        "connector-return-fixture/single-offboard-port-control",
                        "connector-return-fixture/offboard-inventory-unreviewed",
                        "connector-return-fixture/offboard-interface-control",
                        "connector-return-fixture/peer-pin-minority-fault",
                        "connector-return-fixture/peer-pin-divergence-fault",
                        "connector-return-fixture/generic-placeholder-divergence-fault",
                        "connector-return-fixture/generic-placeholder-control",
                        "connector-return-fixture/peer-scope-split-return-fault",
                        "connector-return-fixture/peer-scope-separate-fault",
                        "connector-return-fixture/peer-scope-shared-fault",
                        "connector-return-fixture/peer-scope-shared-control",
                        "connector-return-fixture/four-db9-fault",
                        "connector-return-fixture/four-db9-control",
                        "connector-return-fixture/four-db9-neutral-fault",
                        "connector-return-fixture/four-db9-neutral-control",
                        "connector-return-fixture/ground-contract-common-fault",
                        "connector-return-fixture/ground-contract-common-control",
                        "connector-return-fixture/ground-contract-isolated-fault",
                        "connector-return-fixture/ground-contract-isolated-control",
                        "connector-return-fixture/pin-connectivity-contract-common-fault",
                        "connector-return-fixture/pin-connectivity-contract-common-control",
                        "connector-return-fixture/pin-connectivity-contract-isolated-fault",
                        "connector-return-fixture/pin-connectivity-contract-isolated-control",
                        "connector-return-fixture/pin-connectivity-contract-peer-common-open-fault",
                        "connector-return-fixture/pin-connectivity-contract-peer-common-control",
                        "connector-return-fixture/pin-connectivity-contract-peer-independent-control",
                        "connector-return-fixture/pin-connectivity-contract-peer-independent-common-net-mismatch",
                        "connector-return-fixture/pin-connectivity-contract-stale-pin-reference",
                        "connector-return-fixture/reviewed-role-fault",
                        "connector-return-fixture/reviewed-role-control",
                        "connector-return-fixture/reviewed-supply-fault",
                        "connector-return-fixture/reviewed-supply-control",
                        "connector-return-fixture/reviewed-supply-domain-control",
                    },
                )
                fault = results["connector-return-fixture/fault"]
                control = results["connector-return-fixture/control"]
                self.assertEqual(fault["status"], "PASS")
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(fault["findings"].split(",")),
                    {"connector.repeated_pin_function", "net.numbered_returns"},
                )
                self.assertEqual(control["status"], "PASS")
                self.assertEqual(control["lint_status"], "PASS")
                self.assertEqual(control["findings"], "none")
                generic_power_fault = results[
                    "connector-return-fixture/unconnected-generic-power-input-fault"
                ]
                generic_power_control = results[
                    "connector-return-fixture/unconnected-generic-power-input-control"
                ]
                self.assertEqual(generic_power_fault["status"], "PASS")
                self.assertEqual(generic_power_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    generic_power_fault["findings"].split(","),
                    ["connector.unconnected_power_input"] * 2,
                )
                self.assertEqual(
                    set(generic_power_fault["subjects"].split(";")),
                    {
                        "J1.1: generic native power-input pin is unassigned",
                        "J2.1: generic native power-input pin is unassigned",
                    },
                )
                self.assertEqual(
                    generic_power_fault["pin_electrical_types"],
                    "J1.1=power_in;J1.2=passive;J2.1=power_in;J2.2=passive",
                )
                self.assertEqual(generic_power_control["status"], "PASS")
                self.assertEqual(generic_power_control["lint_status"], "PASS")
                self.assertEqual(generic_power_control["findings"], "none")
                self.assertEqual(
                    generic_power_control["pin_electrical_types"],
                    generic_power_fault["pin_electrical_types"],
                )
                for case in (
                    "unconnected-generic-component-power-input-fault",
                    "unconnected-generic-component-power-input-no-connect-fault",
                ):
                    item = results[f"connector-return-fixture/{case}"]
                    self.assertEqual(item["status"], "PASS")
                    self.assertEqual(item["lint_status"], "REVIEW")
                    self.assertEqual(item["findings"], "component.unconnected_power_input")
                for case in (
                    "unconnected-generic-component-power-input-control",
                    "unconnected-generic-component-power-input-dnp-control",
                ):
                    item = results[f"connector-return-fixture/{case}"]
                    self.assertEqual(item["status"], "PASS")
                    self.assertEqual(item["lint_status"], "PASS")
                    self.assertEqual(item["findings"], "none")
                cross_fault = results["connector-return-fixture/cross-symbol-fault"]
                self.assertEqual(cross_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(cross_fault["subjects"].split(";")),
                    {
                        "multiple connector symbols: ground/return",
                        "multiple connector symbols: PWR",
                    },
                )
                self.assertIn("J3.1=SHIELD", cross_fault["pin_functions"])
                cross_control = results["connector-return-fixture/cross-symbol-control"]
                self.assertEqual(cross_control["lint_status"], "PASS")
                self.assertEqual(cross_control["findings"], "none")
                cross_open = results["connector-return-fixture/cross-symbol-open"]
                self.assertEqual(cross_open["lint_status"], "REVIEW")
                self.assertEqual(
                    cross_open["subjects"], "multiple connector symbols: ground/return"
                )
                channel_fault = results["connector-return-fixture/channel-power-fault"]
                channel_control = results["connector-return-fixture/channel-power-control"]
                self.assertEqual(channel_fault["status"], "PASS")
                self.assertEqual(channel_fault["lint_status"], "REVIEW")
                self.assertIn("net.numbered_power_rails", channel_fault["findings"].split(","))
                self.assertIn("CH VDD", channel_fault["subjects"].split(";"))
                self.assertEqual(channel_control["status"], "PASS")
                self.assertEqual(channel_control["lint_status"], "PASS")
                self.assertEqual(channel_control["findings"], "none")
                self.assertIn("J1.3=VDD", channel_fault["pin_functions"])
                peer_power_fault = results["connector-return-fixture/peer-power-fault"]
                peer_power_control = results["connector-return-fixture/peer-power-control"]
                self.assertEqual(peer_power_fault["status"], "PASS")
                self.assertEqual(peer_power_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(peer_power_fault["findings"].split(",")),
                    {"connector.repeated_pin_function", "net.numbered_power_rails"},
                )
                self.assertIn("J3.1=1", peer_power_fault["pin_functions"])
                self.assertEqual(peer_power_control["status"], "PASS")
                self.assertEqual(peer_power_control["lint_status"], "PASS")
                self.assertEqual(peer_power_control["findings"], "none")
                peer_pin_fault = results["connector-return-fixture/peer-pin-outlier-fault"]
                peer_pin_control = results["connector-return-fixture/peer-pin-outlier-control"]
                self.assertEqual(peer_pin_fault["status"], "PASS")
                self.assertEqual(peer_pin_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    peer_pin_fault["findings"], "connector.peer_pin_assignment_outlier"
                )
                self.assertEqual(peer_pin_fault["subjects"], "Lint:PeerPowerPort pin 1")
                self.assertEqual(peer_pin_fault["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
                self.assertEqual(peer_pin_control["status"], "PASS")
                self.assertEqual(peer_pin_control["lint_status"], "PASS")
                self.assertEqual(peer_pin_control["findings"], "none")
                for (
                    case,
                    expected_connectors,
                    expected_outliers,
                    expected_common,
                    expected_open,
                ) in (
                    ("peer-pin-outlier-fault", 3, 1, 1, 1),
                    ("peer-pin-outlier-control", 3, 0, 2, 0),
                    ("two-peer-open-fault", 2, 1, 1, 1),
                    ("two-peer-no-connect-fault", 2, 1, 1, 1),
                    ("two-peer-common-control", 2, 0, 2, 0),
                ):
                    result = results[f"connector-return-fixture/{case}"]
                    coverage = json.loads(result["connector_peer_pin_coverage"])
                    self.assertEqual(coverage["status"], "EVALUATED")
                    self.assertEqual(coverage["netlist_sha256"], result["netlist_sha256"])
                    self.assertEqual(coverage["connector_candidate_count"], expected_connectors)
                    self.assertEqual(coverage["fitted_connector_count"], expected_connectors)
                    self.assertEqual(coverage["exact_symbol_peer_group_count"], 1)
                    self.assertEqual(coverage["exact_symbol_pin_group_count"], 2)
                    self.assertEqual(coverage["incomplete_pin_inventory_references"], [])
                    self.assertEqual(coverage["peer_pin_outlier_finding_count"], expected_outliers)
                    self.assertEqual(
                        coverage["exact_symbol_pin_groups_with_common_assignment_count"],
                        expected_common,
                    )
                    self.assertEqual(
                        coverage["exact_symbol_pin_groups_with_open_assignment_count"],
                        expected_open,
                    )
                two_peer_fault = results["connector-return-fixture/two-peer-open-fault"]
                two_peer_control = results["connector-return-fixture/two-peer-common-control"]
                self.assertEqual(two_peer_fault["status"], "PASS")
                self.assertEqual(two_peer_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    two_peer_fault["findings"], "connector.peer_pin_assignment_outlier"
                )
                self.assertEqual(two_peer_fault["subjects"], "Lint:PeerPowerPort pin 1")
                two_peer_no_connect_fault = results[
                    "connector-return-fixture/two-peer-no-connect-fault"
                ]
                self.assertEqual(two_peer_no_connect_fault["status"], "PASS")
                self.assertEqual(two_peer_no_connect_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    two_peer_no_connect_fault["findings"],
                    "connector.peer_pin_assignment_outlier",
                )
                self.assertEqual(two_peer_no_connect_fault["subjects"], "Lint:PeerPowerPort pin 1")
                self.assertEqual(two_peer_control["status"], "PASS")
                self.assertEqual(two_peer_control["lint_status"], "PASS")
                self.assertEqual(two_peer_control["findings"], "none")
                offboard_control = results["connector-return-fixture/offboard-interface-control"]
                self.assertEqual(offboard_control["status"], "PASS")
                self.assertEqual(offboard_control["coverage_status"], "COMPLETE")
                self.assertEqual(offboard_control["lint_status"], "PASS")
                self.assertEqual(offboard_control["findings"], "none")
                self.assertEqual(offboard_control["repeatable"], "true")
                offboard_inventory = results[
                    "connector-return-fixture/offboard-inventory-unreviewed"
                ]
                self.assertEqual(offboard_inventory["coverage_status"], "UNDECLARED")
                self.assertEqual(offboard_inventory["lint_status"], "REVIEW")
                self.assertEqual(offboard_inventory["findings"], "none")
                self.assertEqual(offboard_inventory["repeatable"], "true")
                peer_pin_minority = results["connector-return-fixture/peer-pin-minority-fault"]
                self.assertEqual(peer_pin_minority["status"], "PASS")
                self.assertEqual(peer_pin_minority["lint_status"], "REVIEW")
                self.assertEqual(
                    peer_pin_minority["findings"], "connector.peer_pin_assignment_outlier"
                )
                self.assertEqual(peer_pin_minority["subjects"], "Lint:PeerPowerPort pin 1")
                self.assertEqual(peer_pin_minority["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
                peer_pin_divergence = results["connector-return-fixture/peer-pin-divergence-fault"]
                self.assertEqual(peer_pin_divergence["status"], "PASS")
                self.assertEqual(peer_pin_divergence["lint_status"], "REVIEW")
                self.assertEqual(
                    peer_pin_divergence["findings"],
                    "connector.peer_pin_assignment_divergence",
                )
                self.assertEqual(peer_pin_divergence["subjects"], "Lint:PeerPowerPort pin 1")
                self.assertEqual(peer_pin_divergence["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
                placeholder_fault = results[
                    "connector-return-fixture/generic-placeholder-divergence-fault"
                ]
                placeholder_control = results[
                    "connector-return-fixture/generic-placeholder-control"
                ]
                self.assertEqual(placeholder_fault["status"], "PASS")
                self.assertEqual(placeholder_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    placeholder_fault["findings"],
                    "connector.peer_pin_assignment_divergence",
                )
                self.assertEqual(placeholder_fault["subjects"], "Lint:PeerPowerPort pin 1")
                self.assertIn("J1.1=Pin_1", placeholder_fault["pin_functions"])
                self.assertEqual(placeholder_control["status"], "PASS")
                self.assertEqual(placeholder_control["lint_status"], "PASS")
                self.assertEqual(placeholder_control["findings"], "none")
                peer_scope_separate = results["connector-return-fixture/peer-scope-separate-fault"]
                peer_scope_shared = results["connector-return-fixture/peer-scope-shared-fault"]
                peer_scope_control = results["connector-return-fixture/peer-scope-shared-control"]
                self.assertEqual(peer_scope_separate["status"], "PASS")
                self.assertEqual(peer_scope_separate["coverage_status"], "COMPLETE")
                self.assertEqual(peer_scope_separate["lint_status"], "REVIEW")
                self.assertEqual(peer_scope_separate["findings"], "connector.repeated_pin_function")
                self.assertEqual(peer_scope_separate["group_scope"], "separate per-port groups")
                self.assertEqual(peer_scope_shared["status"], "PASS")
                self.assertEqual(peer_scope_shared["coverage_status"], "COMPLETE")
                self.assertEqual(peer_scope_shared["lint_status"], "REVIEW")
                self.assertEqual(
                    set(peer_scope_shared["findings"].split(",")),
                    {
                        "connector.repeated_pin_function",
                        "connector.peer_pin_assignment_divergence",
                    },
                )
                self.assertEqual(peer_scope_shared["group_scope"], "shared uart-peer-set")
                self.assertEqual(peer_scope_control["status"], "PASS")
                self.assertEqual(peer_scope_control["coverage_status"], "COMPLETE")
                self.assertEqual(peer_scope_control["lint_status"], "PASS")
                self.assertEqual(peer_scope_control["findings"], "none")
                db9_fault = results["connector-return-fixture/four-db9-fault"]
                db9_control = results["connector-return-fixture/four-db9-control"]
                self.assertEqual(db9_fault["status"], "PASS")
                self.assertEqual(db9_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(db9_fault["findings"].split(",")),
                    {"connector.repeated_pin_function", "net.numbered_returns"},
                )
                self.assertIn("J4.7=GND", db9_fault["pin_functions"])
                self.assertIn("J4.9=GND", db9_fault["pin_functions"])
                self.assertEqual(db9_control["status"], "PASS")
                self.assertEqual(db9_control["lint_status"], "PASS")
                self.assertEqual(db9_control["findings"], "none")
                grounding_expectations = {
                    "ground-contract-common-fault": "FAIL",
                    "ground-contract-common-control": "PASS",
                    "ground-contract-isolated-fault": "PASS",
                    "ground-contract-isolated-control": "FAIL",
                }
                for case, expected_contract_status in grounding_expectations.items():
                    result = results[f"connector-return-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["contract_status"], expected_contract_status)
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["grounding_contract_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    results["connector-return-fixture/ground-contract-common-fault"]["checks"],
                    "grounding/0V PWM=FAIL;grounding/component-coverage=PASS;"
                    "grounding/return-net-review=FAIL",
                )
                self.assertEqual(
                    results["connector-return-fixture/ground-contract-common-control"]["checks"],
                    "grounding/0V PWM=PASS;grounding/component-coverage=PASS",
                )
                pin_connectivity_expectations = {
                    "common-fault": "FAIL",
                    "common-control": "PASS",
                    "isolated-fault": "PASS",
                    "isolated-control": "FAIL",
                    "peer-common-open-fault": "FAIL",
                    "peer-common-control": "PASS",
                    "peer-independent-control": "PASS",
                    "peer-independent-common-net-mismatch": "FAIL",
                    "stale-pin-reference": "FAIL",
                }
                for case, expected_contract_status in pin_connectivity_expectations.items():
                    result = results[f"connector-return-fixture/pin-connectivity-contract-{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["contract_status"], expected_contract_status)
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["pin_connectivity_contract_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    results["connector-return-fixture/pin-connectivity-contract-common-fault"][
                        "checks"
                    ],
                    "pin-connectivity/db9-common-return=FAIL",
                )
                self.assertEqual(
                    results["connector-return-fixture/pin-connectivity-contract-common-control"][
                        "checks"
                    ],
                    "pin-connectivity/db9-common-return=PASS",
                )
                self.assertEqual(
                    results["connector-return-fixture/pin-connectivity-contract-isolated-fault"][
                        "checks"
                    ],
                    ";".join(
                        f"pin-connectivity/db9-{reference}-isolated-return=PASS"
                        for reference in range(1, 5)
                    ),
                )
                self.assertEqual(
                    results["connector-return-fixture/pin-connectivity-contract-isolated-control"][
                        "checks"
                    ],
                    ";".join(
                        f"pin-connectivity/db9-{reference}-isolated-return=FAIL"
                        for reference in range(1, 5)
                    ),
                )
                self.assertEqual(
                    results[
                        "connector-return-fixture/pin-connectivity-contract-peer-common-open-fault"
                    ]["checks"],
                    "pin-connectivity/peer-common-power=FAIL",
                )
                self.assertEqual(
                    results[
                        "connector-return-fixture/pin-connectivity-contract-peer-common-control"
                    ]["checks"],
                    "pin-connectivity/peer-common-power=PASS",
                )
                self.assertEqual(
                    results[
                        "connector-return-fixture/pin-connectivity-contract-peer-independent-control"
                    ]["checks"],
                    "pin-connectivity/peer-independent-power-outputs=PASS;"
                    "pin-connectivity/peer-j3-power-unused=PASS",
                )
                self.assertEqual(
                    results[
                        "connector-return-fixture/"
                        "pin-connectivity-contract-peer-independent-common-net-mismatch"
                    ]["checks"],
                    "pin-connectivity/peer-independent-power-outputs=FAIL;"
                    "pin-connectivity/peer-j3-power-unused=FAIL",
                )
                stale_pin = results[
                    "connector-return-fixture/pin-connectivity-contract-stale-pin-reference"
                ]
                self.assertEqual(stale_pin["relationship"], "stale-symbol-pin")
                self.assertIn(
                    "unknown symbol pins=['J1.99']",
                    json.loads(stale_pin["check_details"])["pin-connectivity/stale-pin-reference"],
                )
                neutral_fault = results["connector-return-fixture/four-db9-neutral-fault"]
                neutral_control = results["connector-return-fixture/four-db9-neutral-control"]
                self.assertEqual(neutral_fault["status"], "PASS")
                self.assertEqual(neutral_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(neutral_fault["findings"].split(",")),
                    {"connector.repeated_pin_function", "connector.no_connected_return"},
                )
                self.assertEqual(
                    set(neutral_fault["subjects"].split(";")),
                    {
                        "Lint:DB9: 7",
                        "Lint:DB9: 9",
                        *(f"J{reference}: no connected return" for reference in range(1, 5)),
                    },
                )
                self.assertIn("J1.7=7", neutral_fault["pin_functions"])
                self.assertIn("J1.9=9", neutral_fault["pin_functions"])
                self.assertEqual(neutral_control["status"], "PASS")
                self.assertEqual(neutral_control["lint_status"], "REVIEW")
                self.assertEqual(
                    set(neutral_control["findings"].split(",")),
                    {"connector.no_connected_return"},
                )
                self.assertEqual(
                    set(neutral_control["subjects"].split(";")),
                    {f"J{reference}: no connected return" for reference in range(1, 5)},
                )
                mapped_role_fault = results["connector-return-fixture/reviewed-role-fault"]
                mapped_role_control = results["connector-return-fixture/reviewed-role-control"]
                self.assertEqual(mapped_role_fault["status"], "PASS")
                self.assertEqual(mapped_role_fault["coverage_status"], "COMPLETE")
                self.assertEqual(mapped_role_fault["lint_status"], "REVIEW")
                self.assertEqual(mapped_role_fault["findings"], "connector.repeated_pin_function")
                self.assertEqual(mapped_role_fault["repeatable"], "true")
                self.assertEqual(mapped_role_control["status"], "PASS")
                self.assertEqual(mapped_role_control["coverage_status"], "COMPLETE")
                self.assertEqual(mapped_role_control["lint_status"], "PASS")
                self.assertEqual(mapped_role_control["findings"], "none")
                self.assertEqual(mapped_role_control["repeatable"], "true")
                mapped_supply_fault = results["connector-return-fixture/reviewed-supply-fault"]
                mapped_supply_control = results["connector-return-fixture/reviewed-supply-control"]
                mapped_supply_domain_control = results[
                    "connector-return-fixture/reviewed-supply-domain-control"
                ]
                self.assertEqual(mapped_supply_fault["status"], "PASS")
                self.assertEqual(mapped_supply_fault["coverage_status"], "COMPLETE")
                self.assertEqual(mapped_supply_fault["lint_status"], "REVIEW")
                self.assertEqual(mapped_supply_fault["findings"], "connector.repeated_pin_function")
                self.assertEqual(mapped_supply_fault["repeatable"], "true")
                self.assertEqual(mapped_supply_control["coverage_status"], "COMPLETE")
                self.assertEqual(mapped_supply_control["lint_status"], "PASS")
                self.assertEqual(mapped_supply_control["findings"], "none")
                self.assertEqual(mapped_supply_control["repeatable"], "true")
                self.assertEqual(mapped_supply_domain_control["coverage_status"], "COMPLETE")
                self.assertEqual(mapped_supply_domain_control["lint_status"], "PASS")
                self.assertEqual(mapped_supply_domain_control["findings"], "none")
                self.assertEqual(mapped_supply_domain_control["repeatable"], "true")
                for result in (fault, control, channel_fault, channel_control):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                for case in (
                    "cross-symbol-fault",
                    "cross-symbol-control",
                    "cross-symbol-open",
                    "mapped-supply-fault",
                    "mapped-supply-control",
                    "four-db9-fault",
                    "four-db9-control",
                    "four-db9-neutral-fault",
                    "four-db9-neutral-control",
                    "ground-contract-common-fault",
                    "ground-contract-common-control",
                    "ground-contract-isolated-fault",
                    "ground-contract-isolated-control",
                    "pin-connectivity-contract-common-fault",
                    "pin-connectivity-contract-common-control",
                    "pin-connectivity-contract-isolated-fault",
                    "pin-connectivity-contract-isolated-control",
                    "pin-connectivity-contract-peer-common-open-fault",
                    "pin-connectivity-contract-peer-common-control",
                    "pin-connectivity-contract-peer-independent-control",
                    "pin-connectivity-contract-peer-independent-common-net-mismatch",
                    "pin-connectivity-contract-stale-pin-reference",
                    "peer-power-fault",
                    "peer-power-control",
                    "peer-pin-outlier-fault",
                    "peer-pin-outlier-control",
                    "two-peer-open-fault",
                    "two-peer-no-connect-fault",
                    "two-peer-common-control",
                    "single-offboard-port-control",
                    "peer-pin-minority-fault",
                    "peer-pin-divergence-fault",
                    "generic-placeholder-divergence-fault",
                    "generic-placeholder-control",
                    "peer-scope-split-return-fault",
                    "unconnected-generic-power-input-fault",
                    "unconnected-generic-power-input-control",
                ):
                    result = results[f"connector-return-fixture/{case}"]
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                normalized_pattern_hashes[version] = {
                    case: results[f"connector-return-fixture/{case}"]["normalized_netlist_sha256"]
                    for case in (
                        "four-db9-fault",
                        "four-db9-control",
                        "four-db9-neutral-fault",
                        "four-db9-neutral-control",
                        "peer-power-fault",
                        "peer-power-control",
                        "peer-pin-outlier-fault",
                        "peer-pin-outlier-control",
                        "two-peer-open-fault",
                        "two-peer-no-connect-fault",
                        "two-peer-common-control",
                        "single-offboard-port-control",
                        "peer-pin-minority-fault",
                        "peer-pin-divergence-fault",
                        "generic-placeholder-divergence-fault",
                        "generic-placeholder-control",
                        "peer-scope-split-return-fault",
                        "reviewed-role-fault",
                        "reviewed-role-control",
                        "reviewed-supply-fault",
                        "reviewed-supply-control",
                        "reviewed-supply-domain-control",
                        "unconnected-generic-power-input-fault",
                        "unconnected-generic-power-input-control",
                    )
                }
        self.assertEqual(
            normalized_pattern_hashes["10.0.0"],
            normalized_pattern_hashes["10.0.5"],
        )

    def test_native_netlist_connector_inventory_candidates_and_test_point_control(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, connector_inventory_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-connector-inventory-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-connector-inventory-{project}")
                connector_inventory_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("connector-inventory-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "connector-inventory-fixture/native-export",
                        "connector-inventory-fixture/fault",
                        "connector-inventory-fixture/control",
                    },
                )
                fault = results["connector-inventory-fixture/fault"]
                control = results["connector-inventory-fixture/control"]
                self.assertEqual(fault["coverage_status"], "UNDECLARED")
                self.assertEqual(fault["candidate_references"], "U7")
                self.assertEqual(control["coverage_status"], "COMPLETE")
                self.assertEqual(control["candidate_references"], "none")
                for result in (fault, control):
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["coverage_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES") == "1",
    "native digital-peer fixtures run in the digest-pinned package acceptance lane",
)
class NativeDigitalPeerFixtureTests(unittest.TestCase):
    def test_native_pin_functions_drive_unrostered_and_rostered_review_cases(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, digital_peer_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-spi-participant-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hash = "0c5d901b4dc70ccb3c3818bd8fdf002955a6322b814ac2e7f8bab086d47d5e06"
        component_peer_netlist_hashes: dict[str, tuple[str, str]] = {}
        peer_voltage_netlist_hashes: dict[str, tuple[str, str, str]] = {}
        serial_peer_netlist_hashes: dict[str, tuple[str, str, str]] = {}
        serial_connector_netlist_hashes: dict[str, tuple[str, str]] = {}
        serial_label_netlist_hashes: dict[str, tuple[str, str]] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-spi-participant-{project}")
                digital_peer_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith(
                        ("spi-participant-fixture/", "component-peer-power-fixture/")
                    )
                }
                self.assertEqual(
                    set(results),
                    {
                        "spi-participant-fixture/native-export",
                        "spi-participant-fixture/unrostered",
                        "spi-participant-fixture/rostered",
                        "spi-participant-fixture/voltage-control",
                        "spi-participant-fixture/voltage-fault",
                        "spi-participant-fixture/peer-control",
                        "spi-participant-fixture/peer-fault",
                        "spi-participant-fixture/peer-translator-control",
                        "spi-participant-fixture/serial-control",
                        "spi-participant-fixture/serial-fault",
                        "spi-participant-fixture/serial-reference-fault",
                        "spi-participant-fixture/serial-connector-control",
                        "spi-participant-fixture/serial-connector-fault",
                        "spi-participant-fixture/serial-label-control",
                        "spi-participant-fixture/serial-label-fault",
                        "component-peer-power-fixture/control",
                        "component-peer-power-fixture/fault",
                    },
                )
                unrostered = results["spi-participant-fixture/unrostered"]
                self.assertEqual(unrostered["status"], "PASS")
                self.assertEqual(unrostered["lint_status"], "REVIEW")
                self.assertEqual(
                    set(unrostered["findings"].split(";")),
                    {"U1: SPI roster coverage", "U2: SPI roster coverage"},
                )
                self.assertEqual(
                    unrostered["pin_functions"],
                    "U1.1=SPI1_SCLK;U1.2=SPI1_COPI;U1.3=SPI1_CIPO;U1.4=SPI1_NSS;"
                    "U2.1=SPI1_SCLK;U2.2=SPI1_COPI;U2.3=SPI1_CIPO;U2.4=SPI1_NSS",
                )
                rostered = results["spi-participant-fixture/rostered"]
                self.assertEqual(rostered["status"], "PASS")
                self.assertEqual(rostered["lint_status"], "PASS")
                self.assertEqual(rostered["findings"], "none")
                voltage_control = results["spi-participant-fixture/voltage-control"]
                voltage_fault = results["spi-participant-fixture/voltage-fault"]
                self.assertEqual(voltage_control["compatibility_status"], "PASS")
                self.assertAlmostEqual(float(voltage_control["minimum_margin_v"]), 0.3)
                self.assertEqual(voltage_control["driver"], "U1.2/SPI_MOSI")
                self.assertEqual(voltage_control["receiver"], "U2.2/SPI_MOSI")
                self.assertEqual(voltage_fault["compatibility_status"], "FAIL")
                self.assertAlmostEqual(float(voltage_fault["minimum_margin_v"]), -1.4)
                self.assertEqual(voltage_fault["driver"], "U1.2/SPI_MOSI")
                self.assertEqual(voltage_fault["receiver"], "U2.2/SPI_MOSI")
                peer_control = results["spi-participant-fixture/peer-control"]
                peer_fault = results["spi-participant-fixture/peer-fault"]
                translator_control = results["spi-participant-fixture/peer-translator-control"]
                self.assertEqual(peer_control["lint_status"], "PASS")
                self.assertEqual(peer_control["peer_voltage_findings"], "none")
                self.assertEqual(peer_control["rail_assignments"], "+3V3=U1.2,U2.2")
                self.assertEqual(peer_fault["lint_status"], "REVIEW")
                self.assertEqual(peer_fault["peer_voltage_findings"], "bus.spi_peer_voltage_review")
                self.assertEqual(peer_fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
                self.assertEqual(
                    peer_fault["pin_functions"],
                    "U1.1=SPI1_SCLK;U1.2=VDD;U2.1=SPI1_SCLK;U2.2=VDD",
                )
                self.assertEqual(
                    peer_fault["pin_types"],
                    "U1.1=output;U1.2=power_in;U2.1=input;U2.2=power_in",
                )
                self.assertEqual(translator_control["lint_status"], "PASS")
                self.assertEqual(translator_control["peer_voltage_findings"], "none")
                self.assertEqual(
                    translator_control["signal_assignments"],
                    "SPI_A_SIDE=U1.1,U3.1;SPI_B_SIDE=U2.1,U3.2",
                )
                self.assertEqual(
                    translator_control["rail_assignments"],
                    "+3V3=U2.2,U3.4;+5V=U1.2,U3.3",
                )
                serial_control = results["spi-participant-fixture/serial-control"]
                serial_fault = results["spi-participant-fixture/serial-fault"]
                self.assertEqual(serial_control["lint_status"], "PASS")
                self.assertEqual(serial_control["peer_voltage_findings"], "none")
                self.assertEqual(serial_control["peer_reference_findings"], "none")
                self.assertEqual(serial_control["reference_assignments"], "GND=U1.3,U2.3")
                self.assertEqual(
                    serial_control["source_sha256"],
                    "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
                )
                self.assertEqual(serial_control["rail_assignments"], "+3V3=U1.2,U2.2")
                self.assertEqual(serial_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_fault["peer_voltage_findings"],
                    "bus.serial_peer_voltage_review",
                )
                self.assertEqual(
                    serial_fault["peer_reference_findings"],
                    "none",
                )
                self.assertEqual(
                    serial_fault["reference_assignments"],
                    "GND=U1.3,U2.3",
                )
                self.assertEqual(
                    serial_fault["source_sha256"],
                    "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
                )
                self.assertEqual(serial_fault["rail_assignments"], "+3V3=U2.2;+5V=U1.2")
                reference_fault = results["spi-participant-fixture/serial-reference-fault"]
                self.assertEqual(reference_fault["lint_status"], "REVIEW")
                self.assertEqual(reference_fault["peer_voltage_findings"], "none")
                self.assertEqual(
                    reference_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    reference_fault["reference_assignments"],
                    "GND_A=U1.3;GND_B=U2.3",
                )
                self.assertEqual(
                    reference_fault["source_sha256"],
                    "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
                )
                self.assertEqual(
                    reference_fault["rail_assignments"],
                    "+3V3=U1.2,U2.2",
                )
                serial_connector_control = results[
                    "spi-participant-fixture/serial-connector-control"
                ]
                serial_connector_fault = results["spi-participant-fixture/serial-connector-fault"]
                serial_label_control = results["spi-participant-fixture/serial-label-control"]
                serial_label_fault = results["spi-participant-fixture/serial-label-fault"]
                self.assertEqual(serial_connector_control["lint_status"], "REVIEW")
                self.assertEqual(serial_connector_control["peer_reference_findings"], "none")
                self.assertEqual(
                    serial_connector_control["reference_assignments"], "GND_A=J1.4,U1.4"
                )
                self.assertEqual(serial_connector_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_connector_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    serial_connector_fault["reference_assignments"],
                    "GND_A=U1.4;GND_B=J1.4",
                )
                self.assertEqual(
                    serial_connector_fault["signal_assignments"],
                    "UART_RX=J1.2,U1.2;UART_TX=J1.1,U1.1",
                )
                self.assertEqual(
                    serial_connector_fault["pin_functions"],
                    "J1.1=UART1_RX;J1.2=UART1_TX;J1.3=VDD;J1.4=GND;"
                    "U1.1=UART1_TX;U1.2=UART1_RX;U1.3=VDD;U1.4=GND",
                )
                self.assertEqual(
                    serial_connector_fault["pin_types"],
                    "J1.1=input;J1.2=output;J1.3=passive;J1.4=passive;"
                    "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in",
                )
                self.assertEqual(serial_label_control["lint_status"], "REVIEW")
                self.assertEqual(serial_label_control["peer_reference_findings"], "none")
                self.assertEqual(serial_label_control["reference_assignments"], "GND_A=U1.4,U2.4")
                self.assertEqual(serial_label_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    serial_label_fault["peer_reference_findings"],
                    "bus.serial_peer_reference_review",
                )
                self.assertEqual(
                    serial_label_fault["reference_assignments"], "GND_A=U1.4;GND_B=U2.4"
                )
                self.assertEqual(
                    serial_label_fault["signal_assignments"],
                    ";".join(
                        f"{net}={','.join(pins)}"
                        for net, pins in sorted(SERIAL_LABEL_EXPECTED_NETS.items())
                    ),
                )
                self.assertEqual(
                    serial_label_fault["pin_functions"],
                    "U1.1=B2;U1.2=B1;U1.3=VDD;U1.4=GND;U2.1=ADBUS0;U2.2=ADBUS1;U2.3=VDD;U2.4=GND",
                )
                self.assertEqual(
                    serial_label_fault["pin_types"],
                    "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in;"
                    "U2.1=input;U2.2=output;U2.3=passive;U2.4=passive",
                )
                self.assertEqual(
                    serial_fault["pin_functions"],
                    "U1.1=UART1_TX;U1.2=VDD;U1.3=GND;U2.1=UART1_RX;U2.2=VDD;U2.3=GND",
                )
                self.assertEqual(
                    serial_fault["pin_types"],
                    "U1.1=output;U1.2=power_in;U1.3=power_in;U2.1=input;U2.2=power_in;U2.3=power_in",
                )
                serial_peer_netlist_hashes[version] = (
                    serial_control["normalized_netlist_sha256"],
                    serial_fault["normalized_netlist_sha256"],
                    reference_fault["normalized_netlist_sha256"],
                )
                peer_voltage_netlist_hashes[version] = (
                    peer_control["normalized_netlist_sha256"],
                    peer_fault["normalized_netlist_sha256"],
                    translator_control["normalized_netlist_sha256"],
                )
                serial_connector_netlist_hashes[version] = (
                    serial_connector_control["normalized_netlist_sha256"],
                    serial_connector_fault["normalized_netlist_sha256"],
                )
                serial_label_netlist_hashes[version] = (
                    serial_label_control["normalized_netlist_sha256"],
                    serial_label_fault["normalized_netlist_sha256"],
                )
                component_peer_control = results["component-peer-power-fixture/control"]
                component_peer_fault = results["component-peer-power-fixture/fault"]
                self.assertEqual(component_peer_control["lint_status"], "PASS")
                self.assertEqual(component_peer_control["peer_power_findings"], "none")
                self.assertEqual(
                    component_peer_control["pin_assignments"],
                    "U1.1=IO_SHARED;U1.2=+3V3;U1.3=GND;U2.1=IO_SHARED;U2.2=+3V3;U2.3=GND",
                )
                self.assertEqual(component_peer_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    component_peer_fault["peer_power_findings"],
                    "component.peer_power_pin_assignment_divergence;"
                    "component.peer_power_pin_assignment_divergence",
                )
                self.assertEqual(
                    component_peer_fault["divergent_pin_roles"],
                    "2:VDD:supply;3:GND:ground/return",
                )
                self.assertEqual(
                    component_peer_fault["pin_assignments"],
                    "U1.1=IO_SHARED;U1.2=+3V3;U1.3=AGND;U2.1=IO_SHARED;U2.2=+5V;U2.3=DGND",
                )
                expected_erc_signatures = {
                    "component-peer-power-fixture/control": (
                        "power_pin_not_driven;power_pin_not_driven",
                        (
                            "footprint_link_issues;footprint_link_issues;"
                            "lib_symbol_issues;lib_symbol_issues"
                        ),
                    ),
                    "component-peer-power-fixture/fault": (
                        (
                            "power_pin_not_driven;power_pin_not_driven;"
                            "power_pin_not_driven;power_pin_not_driven"
                        ),
                        (
                            "footprint_link_issues;footprint_link_issues;"
                            "isolated_pin_label;isolated_pin_label;isolated_pin_label;isolated_pin_label;"
                            "lib_symbol_issues;lib_symbol_issues"
                        ),
                    ),
                }
                for result in (component_peer_control, component_peer_fault):
                    expected_errors, expected_warnings = expected_erc_signatures[result["stage"]]
                    self.assertEqual(result["erc_error_types"], expected_errors)
                    self.assertEqual(result["erc_warning_types"], expected_warnings)
                component_peer_netlist_hashes[version] = (
                    component_peer_control["normalized_netlist_sha256"],
                    component_peer_fault["normalized_netlist_sha256"],
                )
                for result in (
                    unrostered,
                    rostered,
                    voltage_control,
                    voltage_fault,
                    peer_control,
                    peer_fault,
                    translator_control,
                    serial_control,
                    serial_fault,
                    reference_fault,
                    serial_connector_control,
                    serial_connector_fault,
                    component_peer_control,
                    component_peer_fault,
                ):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["repeatability_basis"],
                        (
                            "normalized_native_netlist_and_electrical_checks"
                            if "compatibility_status" in result
                            else (
                                "normalized_native_netlist_and_design_lint_report"
                                if "peer_voltage_findings" in result
                                or "peer_reference_findings" in result
                                or "peer_power_findings" in result
                                else "normalized_netlist_contract"
                            )
                        ),
                    )
                    if "peer_power_findings" in result:
                        self.assertEqual(result["erc_report_version"], version)
                        self.assertEqual(
                            result["normalized_erc_sha256"],
                            result["repeat_normalized_erc_sha256"],
                        )
                        expected_component_peer_hashes = {
                            "component-peer-power-fixture/control": "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
                            "component-peer-power-fixture/fault": "92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3",
                        }
                        self.assertEqual(
                            result["source_sha256"],
                            expected_component_peer_hashes[result["stage"]],
                        )
                    elif "peer_voltage_findings" in result or "peer_reference_findings" in result:
                        expected_peer_hashes = {
                            "spi-participant-fixture/peer-control": "427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd",
                            "spi-participant-fixture/peer-fault": "98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4",
                            "spi-participant-fixture/peer-translator-control": "58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1",
                            "spi-participant-fixture/serial-control": "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
                            "spi-participant-fixture/serial-fault": "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
                            "spi-participant-fixture/serial-reference-fault": "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
                            "spi-participant-fixture/serial-connector-control": "7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16",
                            "spi-participant-fixture/serial-connector-fault": "ee9ce9a51a78c422da96e260720247bb09403abe314921952f29c5d9ba110c20",
                            "spi-participant-fixture/serial-label-control": "a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561",
                            "spi-participant-fixture/serial-label-fault": "2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20",
                        }
                        self.assertEqual(
                            result["source_sha256"], expected_peer_hashes[result["stage"]]
                        )
                    else:
                        self.assertEqual(result["source_sha256"], expected_source_hash)
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(
            component_peer_netlist_hashes["10.0.0"],
            component_peer_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            component_peer_netlist_hashes["10.0.0"],
            (
                "27b214dc9bd5b33dc7732f1155267462fb7a4efdcd2ed8efb7614ad3e489c0b6",
                "afb64b0e55b04276c8c2d45e94a6aeec056a424aeff2bb349be5aba78b36a1f9",
            ),
        )
        self.assertEqual(serial_peer_netlist_hashes["10.0.0"], serial_peer_netlist_hashes["10.0.5"])
        self.assertEqual(
            peer_voltage_netlist_hashes["10.0.0"], peer_voltage_netlist_hashes["10.0.5"]
        )
        self.assertEqual(
            serial_connector_netlist_hashes["10.0.0"],
            serial_connector_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            serial_label_netlist_hashes["10.0.0"],
            serial_label_netlist_hashes["10.0.5"],
        )
        self.assertEqual(
            serial_peer_netlist_hashes["10.0.0"],
            (
                "ab26230622e20694fa31df7921381d1c0b629a2f4b5b99a24aa05e7ffa99aac8",
                "c5781c55ed8d12e5fa71b6d4302e9de5893d29014ad392c9e8a6b942368ea11c",
                "c92f4dffc776643127fb64b419f0d117acc97c6ec800549b51e990c407b5da60",
            ),
        )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_EMPTY_NETLIST_FIXTURES") == "1",
    "native empty-netlist evidence fixtures run in the digest-pinned package acceptance lane",
)
class NativeEmptyNetlistEvidenceFixtureTests(unittest.TestCase):
    def test_native_empty_inventory_trigger_and_nonempty_control_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, empty_netlist_evidence_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-empty-netlist-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_toolchains = {
            "controller": (
                "10.0.0",
                (
                    "ghcr.io/kicad/kicad:10.0.0@sha256:"
                    "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
                ),
            ),
            "raspberry-pi-status-led": (
                "10.0.5",
                (
                    "ghcr.io/kicad/kicad:10.0.5@sha256:"
                    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
                ),
            ),
        }
        normalized_hashes_by_version: dict[str, dict[str, str]] = {}
        for project, (version, image) in expected_toolchains.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual((config.kicad_version, config.image), (version, image))
                log = HostedLog(root, f"native-empty-netlist-{project}")
                empty_netlist_evidence_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("empty-netlist-evidence/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "empty-netlist-evidence/native-export",
                        "empty-netlist-evidence/empty",
                        "empty-netlist-evidence/nonempty-control",
                    },
                )
                self.assertEqual(results["empty-netlist-evidence/native-export"]["status"], "PASS")
                normalized_hashes_by_version[version] = {}
                for case in ("empty", "nonempty-control"):
                    result = results[f"empty-netlist-evidence/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    normalized_hashes_by_version[version][case] = result[
                        "normalized_netlist_sha256"
                    ]
                    if case == "empty":
                        self.assertEqual(result["component_count"], 0)
                        self.assertEqual(result["net_count"], 0)
                    else:
                        self.assertGreater(result["component_count"], 0)
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(
            normalized_hashes_by_version["10.0.0"],
            normalized_hashes_by_version["10.0.5"],
        )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES") == "1",
    "native I2C pull-up fixtures run in the digest-pinned package acceptance lane",
)
class NativeI2cPullupFixtureTests(unittest.TestCase):
    def test_native_array_channel_fault_and_control_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, i2c_pullup_native_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-i2c-pullup-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        normalized_hashes_by_version: dict[str, dict[str, str]] = {}
        for project, version in (
            ("controller", "10.0.0"),
            ("raspberry-pi-status-led", "10.0.5"),
        ):
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-i2c-pullup-{project}")
                i2c_pullup_native_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("i2c-pullup-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "i2c-pullup-fixture/native-export",
                        "i2c-pullup-fixture/control",
                        "i2c-pullup-fixture/fault",
                    },
                )
                self.assertEqual(results["i2c-pullup-fixture/native-export"]["status"], "PASS")
                control = results["i2c-pullup-fixture/control"]
                fault = results["i2c-pullup-fixture/fault"]
                normalized_hashes_by_version[version] = {
                    "control": control["normalized_netlist_sha256"],
                    "fault": fault["normalized_netlist_sha256"],
                }
                self.assertEqual((control["sda"], control["scl"]), ("PASS", "PASS"))
                self.assertEqual((fault["sda"], fault["scl"]), ("FAIL", "PASS"))
                for result in (control, fault):
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(
            normalized_hashes_by_version["10.0.0"],
            normalized_hashes_by_version["10.0.5"],
        )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES") == "1",
    "native CAN termination fixtures run in the digest-pinned package acceptance lane",
)
class NativeCanTerminationFixtureTests(unittest.TestCase):
    def test_native_split_midpoint_reference_fault_and_control_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, can_termination_native_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-can-termination-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        normalized_hashes_by_version: dict[str, dict[str, str]] = {}
        for project, version in (
            ("controller", "10.0.0"),
            ("raspberry-pi-status-led", "10.0.5"),
        ):
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                log = HostedLog(root, f"native-can-termination-{project}")
                can_termination_native_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("can-termination-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "can-termination-fixture/native-export",
                        "can-termination-fixture/control",
                        "can-termination-fixture/fault",
                    },
                )
                self.assertEqual(results["can-termination-fixture/native-export"]["status"], "PASS")
                control = results["can-termination-fixture/control"]
                fault = results["can-termination-fixture/fault"]
                normalized_hashes_by_version[version] = {
                    "control": control["normalized_netlist_sha256"],
                    "fault": fault["normalized_netlist_sha256"],
                }
                self.assertEqual(
                    (
                        control["signal_pins"],
                        control["unlisted_direct"],
                        control["split_path"],
                        control["midpoint_capacitor"],
                    ),
                    ("PASS", "PASS", "PASS", "PASS"),
                )
                self.assertEqual(
                    (
                        fault["signal_pins"],
                        fault["unlisted_direct"],
                        fault["split_path"],
                        fault["midpoint_capacitor"],
                    ),
                    ("PASS", "PASS", "PASS", "FAIL"),
                )
                for result in (control, fault):
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(set(normalized_hashes_by_version), {"10.0.0", "10.0.5"})
        if set(normalized_hashes_by_version) == {"10.0.0", "10.0.5"}:
            self.assertEqual(
                normalized_hashes_by_version["10.0.0"],
                normalized_hashes_by_version["10.0.5"],
            )


class SerialPeerReferenceBondFixtureDefinitionTests(unittest.TestCase):
    def test_native_sources_and_bond_map_are_pinned_and_well_formed(self) -> None:
        from kicad_tooling.hwrepo.contracts import read_model
        from kicad_tooling.hwrepo.models import SerialPeerAnalysis

        fixture_root = (
            Path(__file__).resolve().parent
            / "fixtures/design_lint/serial-peer-reference-bond-native"
        )
        expected_hashes = {
            "serial-reference-bond-control.kicad_sch": (
                "d6efb587268b8a0dcdbb90eb4401090dcbd6d254742b3e2f718d6df12591c785"
            ),
            "serial-reference-bond-fault.kicad_sch": (
                "a8a41b85d776f521df90998e55c5fc8eb55f1afc4839ab50d997b7a9e190aed2"
            ),
            "serial-peer-map.json": (
                "db84fc9ef9ebbc019ccd5ced4ee0c8d686af201b9397375d658481caff58b6db"
            ),
        }
        for name, expected_hash in expected_hashes.items():
            path = fixture_root / name
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_hash)
            if path.suffix != ".kicad_sch":
                continue
            source = raw.decode("utf-8")
            for endpoint_wire in (
                "(wire (pts (xy 65 54.92) (xy 55 54.92))",
                "(wire (pts (xy 140 54.92) (xy 150 54.92))",
            ):
                with self.subTest(name=name, wire=endpoint_wire):
                    self.assertIn(endpoint_wire, source)
            identifiers = re.findall(r'\(uuid\s+"([^"]+)"\)', source)
            self.assertEqual(len(identifiers), len(set(identifiers)), name)
            depth = 0
            quoted = False
            escaped = False
            for character in source:
                if quoted:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        quoted = False
                elif character == '"':
                    quoted = True
                elif character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                self.assertGreaterEqual(depth, 0, name)
            self.assertEqual(depth, 0, name)
            self.assertFalse(quoted, name)

        requirement = read_model(fixture_root / "serial-peer-map.json", SerialPeerAnalysis)
        self.assertEqual(len(requirement.links), 1)
        link = requirement.links[0]
        self.assertEqual(link.id, "serial-bond")
        self.assertEqual(link.reference_policy, "bonded")
        self.assertIsNotNone(link.reference_bond)
        assert link.reference_bond is not None
        self.assertEqual(link.reference_bond.reference, "R3")


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES") == "1",
    "native serial peer fixtures run in the digest-pinned package acceptance lane",
)
class NativeSerialPeerFixtureTests(unittest.TestCase):
    def test_native_pin_functions_drive_unrostered_partial_and_complete_maps(self) -> None:
        from kicad_tooling.ci_hosted import (
            HostedLog,
            serial_peer_fixture_lane,
            serial_peer_net_label_fixture_lane,
            serial_peer_reference_bond_fixture_lane,
        )
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-serial-peer-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture = repository / "tests/fixtures/design_lint/serial-peer-native/endpoints.kicad_sch"
        alternate_fixture = (
            repository
            / "tests/fixtures/design_lint/serial-peer-native/alternate-function-endpoint.kicad_sch"
        )
        alternate_map = (
            repository
            / "tests/fixtures/design_lint/serial-peer-native/peer-map-alternate-function.json"
        )
        expected_source_hash = "7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060"
        expected_alternate_source_hash = hashlib.sha256(alternate_fixture.read_bytes()).hexdigest()
        expected_alternate_map_hash = hashlib.sha256(alternate_map.read_bytes()).hexdigest()
        expected_normalized_hash = (
            "b1c218d4e398b4ae9d311732a2a8227887e3e8cce1b9759fbd2aa2f0be4320fd"
        )
        expected_bond_source_hashes = {
            "control": "d6efb587268b8a0dcdbb90eb4401090dcbd6d254742b3e2f718d6df12591c785",
            "fault": "a8a41b85d776f521df90998e55c5fc8eb55f1afc4839ab50d997b7a9e190aed2",
        }
        expected_bond_map_hash = "db84fc9ef9ebbc019ccd5ced4ee0c8d686af201b9397375d658481caff58b6db"
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), expected_source_hash)
        normalized_hashes: dict[str, str] = {}
        alternate_normalized_hashes: dict[str, str] = {}
        bond_normalized_hashes: dict[str, dict[str, str]] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-serial-peer-{project}")
                serial_peer_fixture_lane(root, project=project, image=config.image, log=log)
                serial_peer_net_label_fixture_lane(
                    root, project=project, image=config.image, log=log
                )
                serial_peer_reference_bond_fixture_lane(
                    root, project=project, image=config.image, log=log
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith(
                        (
                            "serial-peer-fixture/",
                            "serial-peer-net-label-fixture/",
                            "serial-peer-reference-bond-fixture/",
                        )
                    )
                }
                self.assertEqual(
                    set(results),
                    {
                        "serial-peer-fixture/native-export",
                        "serial-peer-fixture/unrostered",
                        "serial-peer-fixture/partial",
                        "serial-peer-fixture/complete",
                        "serial-peer-net-label-fixture/native-export",
                        "serial-peer-net-label-fixture/unrostered",
                        "serial-peer-net-label-fixture/mapped",
                        "serial-peer-reference-bond-fixture/native-export",
                        "serial-peer-reference-bond-fixture/control",
                        "serial-peer-reference-bond-fixture/fault",
                    },
                )
                expected_findings: dict[str, set[str]] = {
                    "unrostered": {"J1", "J2", "J3", "J4"},
                    "partial": {"J3", "J4"},
                    "complete": set(),
                }
                expected_map_hashes: dict[str, str] = {
                    "unrostered": "none",
                    "partial": "a0ed823e11c1612aaa12c8baeca75b1f6b1211ae925970fa2c018c6b8c2a24f4",
                    "complete": "abed02ee20a713a60a7a0715133d8e02acf170fbc904faa170649dcb9d98c673",
                }
                native = results["serial-peer-fixture/native-export"]
                self.assertEqual(native["status"], "PASS")
                self.assertEqual(native["kicad_version"], version)
                self.assertEqual(native["image"], expected_images[project])
                self.assertEqual(native["source_sha256"], expected_source_hash)
                self.assertEqual(native["repeatable"], "true")
                self.assertEqual(native["normalized_netlist_sha256"], expected_normalized_hash)
                self.assertEqual(
                    native["normalized_netlist_sha256"],
                    native["repeat_normalized_netlist_sha256"],
                )
                normalized_hashes[project] = native["normalized_netlist_sha256"]
                for case, expected_references in expected_findings.items():
                    result = results[f"serial-peer-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(
                        result["lint_status"], "PASS" if not expected_references else "REVIEW"
                    )
                    self.assertEqual(
                        {
                            item.split(":", 1)[0]
                            for item in result["findings"].split(";")
                            if item != "none"
                        },
                        expected_references,
                    )
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_source_hash)
                    self.assertEqual(result["authored_map_sha256"], expected_map_hashes[case])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertEqual(
                        result["pin_functions"],
                        "J1.1=TX;J1.2=RX;J2.1=TX;J2.2=RX;J3.1=TX;J3.2=RX;J4.1=TX;J4.2=RX",
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
                label_native = results["serial-peer-net-label-fixture/native-export"]
                self.assertEqual(label_native["status"], "PASS")
                self.assertEqual(label_native["kicad_version"], version)
                self.assertEqual(label_native["image"], expected_images[project])
                self.assertEqual(label_native["source_sha256"], expected_alternate_source_hash)
                self.assertEqual(label_native["repeatable"], "true")
                self.assertEqual(
                    label_native["normalized_netlist_sha256"],
                    label_native["repeat_normalized_netlist_sha256"],
                )
                self.assertEqual(
                    label_native["pin_functions"],
                    "J5.1=Pin_1;J5.2=Pin_2;U1.1=PA2;U1.2=PA3",
                )
                alternate_normalized_hashes[project] = label_native["normalized_netlist_sha256"]
                for case, expected_status, expected_count, expected_basis, expected_map in (
                    ("unrostered", "REVIEW", 1, "net_label", "none"),
                    ("mapped", "PASS", 0, "none", expected_alternate_map_hash),
                ):
                    result = results[f"serial-peer-net-label-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["lint_status"], expected_status)
                    self.assertEqual(result["source_sha256"], expected_alternate_source_hash)
                    self.assertEqual(result["authored_map_sha256"], expected_map)
                    self.assertEqual(result["discovery_basis"], expected_basis)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    finding_text = result["findings"]
                    self.assertEqual(finding_text != "none", expected_count == 1)
                    if expected_count:
                        self.assertIn("U1: serial-peer map coverage (UART)", finding_text)
                label_receipt = root / label_native["command_receipt"]
                self.assertTrue(label_receipt.is_file())
                label_command = json.loads(label_receipt.read_text())
                label_mounts = tuple(
                    label_command["argv"][index + 1]
                    for index, item in enumerate(label_command["argv"][:-1])
                    if item == "-v"
                )
                self.assertEqual(len(label_mounts), 2)
                self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in label_mounts), 1)
                self.assertEqual(sum(item.endswith(":/output:rw") for item in label_mounts), 1)
                bond_native = results["serial-peer-reference-bond-fixture/native-export"]
                self.assertEqual(bond_native["status"], "PASS")
                self.assertEqual(bond_native["kicad_version"], version)
                self.assertEqual(bond_native["image"], expected_images[project])
                self.assertEqual(
                    bond_native["source_hashes"],
                    ";".join(
                        f"{case}:{expected_bond_source_hashes[case]}"
                        for case in ("control", "fault")
                    ),
                )
                self.assertEqual(bond_native["authored_map_sha256"], expected_bond_map_hash)
                bond_normalized_hashes[project] = {}
                for case, expected_status, expected_failure in (
                    ("control", "PASS", "none"),
                    ("fault", "FAIL", "serial/serial-bond/reference"),
                ):
                    result = results[f"serial-peer-reference-bond-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_bond_source_hashes[case])
                    self.assertEqual(result["authored_map_sha256"], expected_bond_map_hash)
                    self.assertEqual(result["reference_status"], expected_status)
                    self.assertEqual(result["failed_checks"], expected_failure)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    bond_normalized_hashes[project][case] = result["normalized_netlist_sha256"]
                    if case == "fault":
                        self.assertIn(
                            "R3.2 is on FLOATING_GND; expected GND_B",
                            result["reference_detail"],
                        )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(set(normalized_hashes.values()), {expected_normalized_hash})
        self.assertEqual(len(set(alternate_normalized_hashes.values())), 1)
        for case in ("control", "fault"):
            self.assertEqual(
                {bond_normalized_hashes[project][case] for project in expected_versions},
                {bond_normalized_hashes["controller"][case]},
            )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_CAN_PEER_FIXTURES") == "1",
    "native CAN peer fixtures run in the digest-pinned package acceptance lane",
)
class NativeCanPeerFixtureTests(unittest.TestCase):
    def test_native_exports_distinguish_common_and_asymmetric_peer_pairs(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, can_peer_assignment_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-can-peer-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_can_hashes = {
            "peer-control": "9adfa39101f0caaa60bde8ca1770659382d6bfc1677e1b2272847bb76d943135",
            "peer-fault": "60e310e7faae4cee9b8982b1d2abc5be3e8d6c48d815dd9808ae82e7578ecbc6",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-can-peer-{project}")
                can_peer_assignment_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("can-peer-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "can-peer-fixture/native-export",
                        "can-peer-fixture/peer-control",
                        "can-peer-fixture/peer-fault",
                    },
                )
                control = results["can-peer-fixture/peer-control"]
                fault = results["can-peer-fixture/peer-fault"]
                self.assertEqual(control["lint_status"], "PASS")
                self.assertEqual(control["findings"], "none")
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertEqual(fault["findings"], "bus.can_peer_assignment_divergence")
                for case, result in (("peer-control", control), ("peer-fault", fault)):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["erc_errors"], "0")
                    self.assertEqual(
                        set(result["erc_warning_types"].split(";")),
                        {"footprint_link_issues", "lib_symbol_issues"},
                    )
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(result["source_sha256"], expected_can_hashes[case])
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_OPEN_DRAIN_FIXTURES") == "1",
    "native open-output bias fixtures run in the digest-pinned package acceptance lane",
)
class NativeOpenDrainBiasFixtureTests(unittest.TestCase):
    def test_native_exports_distinguish_bias_polarity_and_dnp_faults(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, open_drain_bias_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-open-drain-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_hashes = {
            "collector-control": "bdb0b34256ef9bac90b7fba687abe5998400c29da2f2467cd1a43e8b1029c177",
            "collector-fault": "bb4d7075d2892bf2991a3b840ba1db956cdf6a2f6caba1538ef1381c0d937714",
            "emitter-control": "3f2bcdb733865867bef38ba1fe790518e8aa35225e04117220dcac07e53645f0",
            "emitter-fault": "b987e6f281edc13de3587614cb3bb19ed80bfeeaccde783dcf1492ef598826e1",
        }
        expected_netlist_hashes = {
            "collector-control": "bb5b9b6e92a414fd42ee6afe6318e341a6a535bd7d4e1983dc69d3c977758e34",
            "collector-fault": "6913b490585e072c7641a1800540bb4859b0009d68d4e4428ad2925417f85b20",
            "emitter-control": "4dce56e48d3b8082026f65dad1d9dd69b7466224ad617786566396aae6f74c9d",
            "emitter-fault": "6efc7bd50862e1190ebd70962b50dfbfe813f74d51aa8f88d2b7f2f3bc385588",
        }
        expected_cases = {
            "collector-control": ("PASS", "none", "open_collector", "none"),
            "collector-fault": (
                "REVIEW",
                "signal.open_collector_input_without_visible_bias",
                "open_collector",
                "R1",
            ),
            "emitter-control": ("PASS", "none", "open_emitter", "none"),
            "emitter-fault": (
                "REVIEW",
                "signal.open_emitter_input_without_visible_bias",
                "open_emitter",
                "R1",
            ),
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-open-drain-{project}")
                open_drain_bias_fixture_lane(root, project=project, image=config.image, log=log)
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
                        *(f"open-drain-bias-fixture/{case}" for case in expected_cases),
                    },
                )
                for case, (status, finding, output_type, dnp_resistor) in expected_cases.items():
                    result = results[f"open-drain-bias-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["lint_status"], status)
                    self.assertEqual(result["findings"], finding)
                    self.assertEqual(result["open_output_type"], output_type)
                    self.assertEqual(result["input_type"], "input")
                    self.assertEqual(result["dnp_resistor"], dnp_resistor)
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["erc_errors"], "0")
                    self.assertEqual(
                        set(result["erc_warning_types"].split(";")),
                        {"footprint_link_issues", "isolated_pin_label", "lib_symbol_issues"},
                    )
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(result["source_sha256"], expected_hashes[case])
                    self.assertEqual(
                        result["normalized_netlist_sha256"], expected_netlist_hashes[case]
                    )
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertRegex(result["normalized_erc_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(
                        result["normalized_erc_sha256"], result["repeat_normalized_erc_sha256"]
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_USB_C_PORT_FIXTURES") == "1",
    "native USB-C port fixtures run in the digest-pinned package acceptance lane",
)
class NativeUsbCPortFixtureTests(unittest.TestCase):
    def test_native_role_prompt_covers_unknown_source_and_sink_topologies(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, usb_c_port_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-usb-c-port-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hashes = {
            "connector": "42935f2e21f3b86acc33a87916072b466d5c75b61cddd472a40fb6219d59ce9a",
            "source-rp-control": "b9913fa1e44adaaa3837257dc0756bcb39411b9bb79dcd1568c1a264248a1f8f",
            "sink-rd-control": "5ac40420e4adcc7f2005e1808f1ebdeb765fd4907113bfa5be657407d2d6d789",
            "vbus-capacitance-control": "d664fe8ece994d847c133187c14bcc279c2466eb917ddddddac4faa22c17c6ca",
            "vbus-capacitance-fault": "c126f173af020b3aa2eeebf74657064685e87eac684b4b197a15d82992970560",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-usb-c-port-{project}")
                usb_c_port_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("usb-c-port-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "usb-c-port-fixture/native-export",
                        "usb-c-port-fixture/unmapped",
                        "usb-c-port-fixture/mapped",
                        "usb-c-port-fixture/source-rp-control",
                        "usb-c-port-fixture/sink-rd-control",
                        "usb-c-port-fixture/vbus-capacitance-control",
                        "usb-c-port-fixture/vbus-capacitance-fault",
                    },
                )
                unmapped = results["usb-c-port-fixture/unmapped"]
                self.assertEqual(unmapped["status"], "PASS")
                self.assertEqual(unmapped["lint_status"], "REVIEW")
                self.assertEqual(unmapped["findings"], "J1: USB-C role-map coverage")
                self.assertEqual(unmapped["cc_pin_functions"], "J1.4=CC1;J1.5=CC2")
                mapped = results["usb-c-port-fixture/mapped"]
                self.assertEqual(mapped["status"], "PASS")
                self.assertEqual(mapped["lint_status"], "PASS")
                self.assertEqual(mapped["findings"], "none")
                for case in ("source-rp-control", "sink-rd-control"):
                    with self.subTest(fixture=case):
                        result = results[f"usb-c-port-fixture/{case}"]
                        self.assertEqual(result["status"], "PASS")
                        self.assertEqual(result["lint_status"], "REVIEW")
                        self.assertEqual(result["findings"], "J1: USB-C role-map coverage")
                        self.assertEqual(result["cc_pin_functions"], "J1.4=CC1;J1.5=CC2")
                        self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                        self.assertEqual(result["fixture_case"], case)
                capacitance_control = results["usb-c-port-fixture/vbus-capacitance-control"]
                self.assertEqual(capacitance_control["status"], "PASS")
                self.assertEqual(capacitance_control["check_status"], "PASS")
                self.assertEqual(capacitance_control["expected_check_status"], "PASS")
                self.assertEqual(float(capacitance_control["observed_nf"]), 4700.0)
                capacitance_fault = results["usb-c-port-fixture/vbus-capacitance-fault"]
                self.assertEqual(capacitance_fault["status"], "PASS")
                self.assertEqual(capacitance_fault["check_status"], "FAIL")
                self.assertEqual(capacitance_fault["expected_check_status"], "FAIL")
                self.assertEqual(float(capacitance_fault["observed_nf"]), 2200.0)
                for case, result in (
                    ("connector", unmapped),
                    ("connector", mapped),
                    ("source-rp-control", results["usb-c-port-fixture/source-rp-control"]),
                    ("sink-rd-control", results["usb-c-port-fixture/sink-rd-control"]),
                    ("vbus-capacitance-control", capacitance_control),
                    ("vbus-capacitance-fault", capacitance_fault),
                ):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["repeat_normalized_netlist_sha256"],
                        result["normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") == "1",
    "native USB data-path fixtures run in the digest-pinned package acceptance lane",
)
class NativeUsbDataPathFixtureTests(unittest.TestCase):
    def test_integrated_and_external_phy_topologies_with_bypass_fault(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, usb_data_path_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-usb-data-path-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hashes = {
            "integrated-direct": "e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27",
            "external-series": "87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f",
            "external-series-reference-bond-control": "5a178e443dcac77c4342d9b3e86a254556f71bbdc1b707bcb2bb23a1459bd9f3",
            "external-series-reference-fault": "25e0cea0682898c5300b27024436717fc9b9b50743ef256b922e98909e0520ab",
            "external-bypass": "0b6173339fc0e2f937247c6eb5aaea1ac51b0b7a26a31058c25119333cb8f0c2",
            "peer-reference-fault": "4aa97359832c162f5476f1002970ab039b9275d2fae4539a053bec5980bb4bc1",
            "peer-reference-control": "26a52a7f4010f376b44d0fa39780c886dc4859bc9dac1ddb4206d8033ee35ec2",
            "usb-c-peer-reference-fault": "b07cb10e9467cb2e34d79cd5ce696a76d9feeb004f3ac218d4d2e0f27a3f510e",
            "usb-c-peer-reference-control": "456f8d1f23735db18f4ec1b0c347cc1ab1d396af3b957c40d9158e535015a70f",
            "usb-multiport-peer-reference-fault": "9cbc4ebc8692b02fc9ef8b6a1723d926536b2b7a74251ff4d37e045cdacae615",
            "usb-multiport-peer-reference-control": "80f5af92083dbc5a3fce319dabb5c80efb535899e482ff6ad952a41f576df0d0",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-usb-data-path-{project}")
                usb_data_path_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("usb-data-path-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "usb-data-path-fixture/native-export",
                        "usb-data-path-fixture/integrated-direct",
                        "usb-data-path-fixture/external-series",
                        "usb-data-path-fixture/external-series-reference-bond-control",
                        "usb-data-path-fixture/external-series-reference-fault",
                        "usb-data-path-fixture/external-bypass",
                        "usb-data-path-fixture/peer-reference-fault",
                        "usb-data-path-fixture/peer-reference-control",
                        "usb-data-path-fixture/usb-c-peer-reference-fault",
                        "usb-data-path-fixture/usb-c-peer-reference-control",
                        "usb-data-path-fixture/usb-multiport-peer-reference-fault",
                        "usb-data-path-fixture/usb-multiport-peer-reference-control",
                    },
                )
                for case in (
                    "integrated-direct",
                    "external-series",
                    "external-series-reference-bond-control",
                ):
                    self.assertEqual(results[f"usb-data-path-fixture/{case}"]["status"], "PASS")
                    self.assertEqual(
                        results[f"usb-data-path-fixture/{case}"]["usb_path_findings"], "none"
                    )
                bonded_control = results[
                    "usb-data-path-fixture/external-series-reference-bond-control"
                ]
                self.assertEqual(bonded_control["usb_reference_findings"], "none")
                series_peer_fault = results["usb-data-path-fixture/external-series-reference-fault"]
                self.assertEqual(series_peer_fault["status"], "PASS")
                self.assertEqual(series_peer_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    series_peer_fault["usb_reference_findings"],
                    "J1 / U1: USB reference-domain review (port 1)",
                )
                fault = results["usb-data-path-fixture/external-bypass"]
                self.assertEqual(fault["status"], "PASS")
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertEqual(
                    set(fault["usb_path_findings"].split(";")),
                    {
                        "external-usb-phy: USB D+ path",
                        "external-usb-phy: USB D- path",
                    },
                )
                peer_fault = results["usb-data-path-fixture/peer-reference-fault"]
                self.assertEqual(peer_fault["status"], "PASS")
                self.assertEqual(peer_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    peer_fault["usb_reference_findings"],
                    "J1 / U1: USB reference-domain review",
                )
                peer_control = results["usb-data-path-fixture/peer-reference-control"]
                self.assertEqual(peer_control["status"], "PASS")
                self.assertEqual(peer_control["usb_reference_findings"], "none")
                usb_c_fault = results["usb-data-path-fixture/usb-c-peer-reference-fault"]
                self.assertEqual(usb_c_fault["status"], "PASS")
                self.assertEqual(usb_c_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    usb_c_fault["usb_reference_findings"],
                    "J1 / U1: USB reference-domain review",
                )
                usb_c_control = results["usb-data-path-fixture/usb-c-peer-reference-control"]
                self.assertEqual(usb_c_control["status"], "PASS")
                self.assertEqual(usb_c_control["usb_reference_findings"], "none")
                multiport_fault = results[
                    "usb-data-path-fixture/usb-multiport-peer-reference-fault"
                ]
                self.assertEqual(multiport_fault["status"], "PASS")
                self.assertEqual(multiport_fault["lint_status"], "REVIEW")
                self.assertEqual(
                    multiport_fault["usb_reference_findings"],
                    "J1 / U1: USB reference-domain review (port 1);"
                    "J2 / U1: USB reference-domain review (port 2)",
                )
                multiport_control = results[
                    "usb-data-path-fixture/usb-multiport-peer-reference-control"
                ]
                self.assertEqual(multiport_control["status"], "PASS")
                self.assertEqual(multiport_control["usb_reference_findings"], "none")
                for case in (
                    "integrated-direct",
                    "external-series",
                    "external-series-reference-bond-control",
                    "external-series-reference-fault",
                    "external-bypass",
                    "peer-reference-fault",
                    "peer-reference-control",
                    "usb-c-peer-reference-fault",
                    "usb-c-peer-reference-control",
                    "usb-multiport-peer-reference-fault",
                    "usb-multiport-peer-reference-control",
                ):
                    result = results[f"usb-data-path-fixture/{case}"]
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(result["repeatability_basis"], "normalized_netlist_contract")
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_STM32_PIN_MAP_FIXTURES") == "1",
    "native STM32 pin-map fixtures run in the digest-pinned package acceptance lane",
)
class NativeStm32PinMapFixtureTests(unittest.TestCase):
    def test_cube_mx_and_schematic_pin_map_faults_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, stm32_pin_map_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-stm32-pin-map-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture_root = repository / "tests/fixtures/design_lint/stm32-pin-map-native"
        expected_source_hashes = {
            "valid.kicad_sch": "5656bf52778eb58d224d7b211999cb816c26bbf7220fc6430887b74ee3b42716",
            "net-drift.kicad_sch": "399e94cf7213b926e435c1053a43da4ad6a2e82a419d8763ebd3df10b4b50738",
            "valid.ioc": "f36873f874ab1ac1252ec8012b491042eca3ed24129dbd51d5f6053d50821c42",
            "signal-drift.ioc": "5bcd5d407060c7c7978e773f1929e6713c275b23c6cc7563faecce2e6a61867a",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected_source_hashes
            },
            expected_source_hashes,
        )
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-stm32-pin-map-{project}")
                stm32_pin_map_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("stm32-pin-map-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "stm32-pin-map-fixture/native-export",
                        "stm32-pin-map-fixture/control",
                        "stm32-pin-map-fixture/net-drift",
                        "stm32-pin-map-fixture/signal-drift",
                    },
                )
                self.assertEqual(results["stm32-pin-map-fixture/control"]["lint_status"], "PASS")
                self.assertEqual(results["stm32-pin-map-fixture/control"]["mismatch_pins"], "none")
                for case in ("net-drift", "signal-drift"):
                    result = results[f"stm32-pin-map-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["lint_status"], "REVIEW")
                    self.assertEqual(result["mismatch_pins"], "PA0")
                for case in ("control", "net-drift", "signal-drift"):
                    result = results[f"stm32-pin-map-fixture/{case}"]
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertIn(result["source_sha256"], expected_source_hashes.values())
                    self.assertIn(result["ioc_sha256"], expected_source_hashes.values())
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_LED_RAIL_FIXTURES") == "1",
    "native LED rail fixtures run in the digest-pinned package acceptance lane",
)
class NativeLedRailFixtureTests(unittest.TestCase):
    def test_direct_rail_and_output_driven_led_faults_with_series_controls(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, led_rail_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-led-rail-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hashes = {
            "direct-rails": "998164b255a1ec4c71a1faf1681366ea0bf3e253cc1a9833d3a6c85b838816b8",
            "series-control": "00d7ab8dc51351f400f5599526304ab4576ced2d9cd9f583f093cb37705456c3",
            "parallel-resistor": "b5fef4b342eccddf9b582ad725ee69aa910b595c92f44042e999c6810459cffd",
            "direct-output": "a71215195b1273c29ebbe318d52d32ba7db568a8cb49476ed34bea0252fbdfb2",
            "series-return-control": "d64eac25b88d7d355e81f8f05001976f15ea989d9b518086499e30e7ef48ba2c",
            "parallel-output-resistor": "1c37d1e6c7a70f460f4525f25c1d0ebe89dd8db0cbe8e17b415a15827a9422a0",
            "custom-direct-output": "2e2d6909d49c5815c5254aea14125ac6243fba0d45307d875c2563d657bc4f7b",
            "custom-series-return-control": "c5a254ead0887da399cd2ace46db4fde8231711abdb602304eac7e1be68ff047",
        }
        expected_findings: dict[str, set[str]] = {
            "direct-rails": {"D1: LED directly spans supply and return"},
            "series-control": set(),
            "parallel-resistor": {"D1: LED directly spans supply and return"},
            "direct-output": set(),
            "series-return-control": set(),
            "parallel-output-resistor": set(),
            "custom-direct-output": set(),
            "custom-series-return-control": set(),
        }
        expected_output_findings: dict[str, set[str]] = {
            "direct-rails": set(),
            "series-control": set(),
            "parallel-resistor": set(),
            "direct-output": {"D1: LED directly shares an output net and a rail"},
            "series-return-control": set(),
            "parallel-output-resistor": {"D1: LED directly shares an output net and a rail"},
            "custom-direct-output": {"D1: LED directly shares an output net and a rail"},
            "custom-series-return-control": set(),
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-led-rail-{project}")
                led_rail_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("led-rail-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "led-rail-fixture/native-export",
                        "led-rail-fixture/direct-rails",
                        "led-rail-fixture/series-control",
                        "led-rail-fixture/parallel-resistor",
                        "led-rail-fixture/direct-output",
                        "led-rail-fixture/series-return-control",
                        "led-rail-fixture/parallel-output-resistor",
                        "led-rail-fixture/custom-direct-output",
                        "led-rail-fixture/custom-series-return-control",
                    },
                )
                self.assertEqual(results["led-rail-fixture/native-export"]["status"], "PASS")
                for case, expected in expected_findings.items():
                    result = results[f"led-rail-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(
                        set(result["led_rule_findings"].split(";"))
                        if result["led_rule_findings"] != "none"
                        else set(),
                        expected,
                    )
                    self.assertEqual(
                        set(result["led_output_rule_findings"].split(";"))
                        if result["led_output_rule_findings"] != "none"
                        else set(),
                        expected_output_findings[case],
                    )
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES") == "1",
    "native complementary-pair fixtures run in the digest-pinned package acceptance lane",
)
class NativeComplementaryPairFixtureTests(unittest.TestCase):
    def test_usb_superspeed_fault_and_control_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, complementary_pair_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-complementary-pair-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        normalized_hashes: dict[str, dict[str, str]] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-complementary-pair-{project}")
                complementary_pair_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                results = {
                    item["stage"]: item
                    for item in (json.loads(line) for line in log.events.read_text().splitlines())
                    if item.get("stage", "").startswith("complementary-pair-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "complementary-pair-fixture/native-export",
                        "complementary-pair-fixture/fault",
                        "complementary-pair-fixture/control",
                    },
                )
                fault = results["complementary-pair-fixture/fault"]
                control = results["complementary-pair-fixture/control"]
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertEqual(fault["pair_findings"], "J1: USB SuperSpeed RX pair")
                self.assertIn("J1.4=StdA_SSRX-", fault["pin_functions"])
                self.assertEqual(control["lint_status"], "PASS")
                self.assertEqual(control["pair_findings"], "none")
                for result in (fault, control):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(result["normalized_netlist_sha256"], r"^[0-9a-f]{64}$")
                normalized_hashes[version] = {
                    case: results[f"complementary-pair-fixture/{case}"]["normalized_netlist_sha256"]
                    for case in ("fault", "control")
                }
        if len(normalized_hashes) != len(expected_versions):
            return
        self.assertEqual(normalized_hashes["10.0.0"], normalized_hashes["10.0.5"])


class TwoPinComponentFixtureManifestTests(unittest.TestCase):
    def test_every_native_case_resolves_under_the_read_only_fixture_mount(self) -> None:
        fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
        self.assertEqual(len(TWO_PIN_COMPONENT_FIXTURE_CASES), 14)
        for case, (
            relative_source,
            _rule_id,
            _expected_findings,
        ) in TWO_PIN_COMPONENT_FIXTURE_CASES.items():
            with self.subTest(case=case):
                source = (fixture_root / relative_source).resolve()
                self.assertTrue(source.is_relative_to(fixture_root.resolve()))
                self.assertTrue(
                    source.is_file(), f"native fixture source is missing: {relative_source}"
                )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") == "1",
    "native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
class NativeTwoPinComponentFixtureTests(unittest.TestCase):
    def test_passive_diode_and_fuse_fault_controls_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, two_pin_component_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-two-pin-component-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture_root = repository / "tests/fixtures/design_lint"
        expected_source_hashes = {
            "two-pin-components/same-net.kicad_sch": "54de8ccfcffb2d7e44a84fb4b5892872046bc963c2294242498d9b653d526a2b",
            "two-pin-components/distinct-nets.kicad_sch": "338deb4b9194e37a80813b3a3c447d21c14fa59fef78b0925898f595a27fbdea",
            "two-pin-components/same-net-diode.kicad_sch": "c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b",
            "two-pin-components/distinct-nets-diode.kicad_sch": "74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928",
            "two-pin-crystals/same-net-crystal.kicad_sch": "0a55a739bcce60cacafaadf2c9995c0ff3ef07caf4284745b420a8e0f2de2b1a",
            "two-pin-crystals/distinct-nets-crystal.kicad_sch": "4c4fa54184ba74eb8194016a166e068c1a41646b4e59686d187395d981c4bc13",
            "two-pin-fuses/same-net-fuse.kicad_sch": "b69792902442ef89c103f5a4b783b73633b88d9519ab01c5b77df9b654df62ca",
            "two-pin-fuses/distinct-nets-fuse.kicad_sch": "c9c6afa14db03137c1bbc78b82875d159f79b5ebabbb7ea21c6eac1e33fc6edb",
            "two-pin-fuses/same-net-polyfuse.kicad_sch": "1537a762c427dbc77e3afb35fd2faecb494e69674b8ca3f7e04e7497fd96e3ad",
            "two-pin-fuses/distinct-nets-polyfuse.kicad_sch": "f4d7ba7f0d27d295c725f2286dace93fa4163b3dbb04130d0c913f05660fc037",
            "two-pin-ferrites/same-net-ferrite.kicad_sch": "8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7",
            "two-pin-ferrites/distinct-nets-ferrite.kicad_sch": "199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7",
            "two-pin-switches/same-net-spst.kicad_sch": "1ddb2e72f4759c3edddd0f1c7077090c911fa3cbd36d48ef5a0850d6146c25b4",
            "two-pin-switches/distinct-nets-spst.kicad_sch": "2f9e43e716fe6bc89645734768ced5ff5491ba8b62330aa1c544db236d31e147",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected_source_hashes
            },
            expected_source_hashes,
        )
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-two-pin-component-{project}")
                two_pin_component_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("two-pin-component-fixture/")
                }
                expected_cases = (
                    "native-export",
                    "same-net-passive",
                    "distinct-nets-passive",
                    "same-net-diode",
                    "distinct-nets-diode",
                    "same-net-crystal",
                    "distinct-nets-crystal",
                    "same-net-fuse",
                    "distinct-nets-fuse",
                    "same-net-polyfuse",
                    "distinct-nets-polyfuse",
                    "same-net-ferrite",
                    "distinct-nets-ferrite",
                    "same-net-switch",
                    "distinct-nets-switch",
                )
                self.assertEqual(
                    set(results),
                    {f"two-pin-component-fixture/{case}" for case in expected_cases},
                )
                native_export = results["two-pin-component-fixture/native-export"]
                self.assertEqual(native_export["status"], "PASS")
                case_expectations = (
                    (
                        "same-net-passive",
                        "two-pin-components/same-net.kicad_sch",
                        "component.two_pin_passive_same_net",
                        "R1 (10k resistor) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-passive",
                        "two-pin-components/distinct-nets.kicad_sch",
                        "component.two_pin_passive_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-diode",
                        "two-pin-components/same-net-diode.kicad_sch",
                        "component.two_pin_diode_same_net",
                        "D1 (1N4148 diode) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-diode",
                        "two-pin-components/distinct-nets-diode.kicad_sch",
                        "component.two_pin_diode_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-crystal",
                        "two-pin-crystals/same-net-crystal.kicad_sch",
                        "component.two_pin_crystal_same_net",
                        "Y1 (16 MHz crystal) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-crystal",
                        "two-pin-crystals/distinct-nets-crystal.kicad_sch",
                        "component.two_pin_crystal_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-fuse",
                        "two-pin-fuses/same-net-fuse.kicad_sch",
                        "component.two_pin_fuse_same_net",
                        "F1 (1A fuse) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-fuse",
                        "two-pin-fuses/distinct-nets-fuse.kicad_sch",
                        "component.two_pin_fuse_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-polyfuse",
                        "two-pin-fuses/same-net-polyfuse.kicad_sch",
                        "component.two_pin_fuse_same_net",
                        "F1 (1A polyfuse) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-polyfuse",
                        "two-pin-fuses/distinct-nets-polyfuse.kicad_sch",
                        "component.two_pin_fuse_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-ferrite",
                        "two-pin-ferrites/same-net-ferrite.kicad_sch",
                        "component.two_pin_ferrite_same_net",
                        "FB1 (600R@100MHz ferrite_bead) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-ferrite",
                        "two-pin-ferrites/distinct-nets-ferrite.kicad_sch",
                        "component.two_pin_ferrite_same_net",
                        "none",
                        "PASS",
                    ),
                    (
                        "same-net-switch",
                        "two-pin-switches/same-net-spst.kicad_sch",
                        "component.two_pin_switch_same_net",
                        "SW1 (Synthetic SPST switch) has both pins on one net",
                        "REVIEW",
                    ),
                    (
                        "distinct-nets-switch",
                        "two-pin-switches/distinct-nets-spst.kicad_sch",
                        "component.two_pin_switch_same_net",
                        "none",
                        "PASS",
                    ),
                )
                for (
                    case_name,
                    source_name,
                    rule_id,
                    expected_findings,
                    lint_status,
                ) in case_expectations:
                    with self.subTest(case=case_name):
                        case = results[f"two-pin-component-fixture/{case_name}"]
                        self.assertEqual(case["status"], "PASS")
                        self.assertEqual(case["lint_status"], lint_status)
                        self.assertEqual(case["component_rule"], rule_id)
                        self.assertEqual(case["component_findings"], expected_findings)
                        self.assertEqual(case["kicad_version"], version)
                        self.assertEqual(case["image"], expected_images[project])
                        self.assertEqual(case["source_sha256"], expected_source_hashes[source_name])
                        self.assertEqual(case["repeatable"], "true")
                        self.assertEqual(
                            case["normalized_netlist_sha256"],
                            case["repeat_normalized_netlist_sha256"],
                        )
                        receipt = root / case["command_receipt"]
                        self.assertTrue(receipt.is_file())
                        command = json.loads(receipt.read_text())
                        mounts = tuple(
                            command["argv"][index + 1]
                            for index, item in enumerate(command["argv"][:-1])
                            if item == "-v"
                        )
                        self.assertEqual(len(mounts), 2)
                        self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                        self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_NET_DC_REFERENCE_FIXTURES") == "1",
    "native DC-reference fixtures run in the digest-pinned package acceptance lane",
)
class NativeNetDcReferenceFixtureTests(unittest.TestCase):
    def test_connector_capacitor_only_fault_and_controls_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, net_dc_reference_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-net-dc-reference-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture_root = repository / "tests/fixtures/design_lint/net-dc-reference"
        expected_source_hashes = {
            "fault.kicad_sch": "34678343d148878ab7ab470a3dd99e049ccfc08969cbd419548397602e5c483a",
            "control.kicad_sch": "312d7a1f6cd61c4c2e05f31ec57e5688c22610f7bb76dd18271d53eba86eb2ec",
            "dnp-control.kicad_sch": "fecaddc449493001871d6ca049b1d764030d7f72860e3aa11aa492fdcf570924",
        }
        actual_source_hashes = {
            name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
            for name in expected_source_hashes
        }
        self.assertEqual(actual_source_hashes, expected_source_hashes)

        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-net-dc-reference-{project}")
                net_dc_reference_fixture_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("net-dc-reference-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "net-dc-reference-fixture/native-export",
                        "net-dc-reference-fixture/fault",
                        "net-dc-reference-fixture/control",
                        "net-dc-reference-fixture/dnp-control",
                    },
                )
                self.assertEqual(
                    results["net-dc-reference-fixture/native-export"]["status"], "PASS"
                )
                native = results["net-dc-reference-fixture/native-export"]
                receipt = root / native["command_receipt"]
                self.assertTrue(receipt.is_file())
                command = json.loads(receipt.read_text())
                argv = command["argv"]
                self.assertIn(expected_images[project], argv)
                self.assertIn("--network", argv)
                self.assertIn("none", argv)
                self.assertIn("--read-only", argv)
                mounts = tuple(
                    argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v"
                )
                self.assertEqual(len(mounts), 2)
                self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
                fault = results["net-dc-reference-fixture/fault"]
                control = results["net-dc-reference-fixture/control"]
                dnp_control = results["net-dc-reference-fixture/dnp-control"]
                self.assertEqual(fault["status"], "PASS")
                self.assertEqual(fault["lint_status"], "REVIEW")
                self.assertIn("ANALOG_IN", fault["finding"])
                self.assertEqual(fault["erc_error_types"], "none")
                self.assertEqual(control["status"], "PASS")
                self.assertEqual(control["lint_status"], "PASS")
                self.assertEqual(control["finding"], "none")
                self.assertEqual(control["erc_error_types"], "none")
                self.assertEqual(dnp_control["status"], "PASS")
                self.assertEqual(dnp_control["lint_status"], "PASS")
                self.assertEqual(dnp_control["finding"], "none")
                self.assertEqual(dnp_control["erc_error_types"], "none")
                for result, name in (
                    (fault, "fault.kicad_sch"),
                    (control, "control.kicad_sch"),
                    (dnp_control, "dnp-control.kicad_sch"),
                ):
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["source_sha256"], expected_source_hashes[name])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertEqual(
                        result["normalized_erc_sha256"], result["repeat_normalized_erc_sha256"]
                    )


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES") == "1",
    "native component rating fixtures run in the digest-pinned package acceptance lane",
)
class NativeComponentRatingFixtureTests(unittest.TestCase):
    def test_component_and_connector_rating_controls_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import (
            HostedLog,
            component_rating_fixtures_lane,
        )
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-component-rating-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        fixture = (
            repository
            / "tests/fixtures/design_lint/component-voltage-ratings/rating-control.kicad_sch"
        )
        power_fixture = (
            repository
            / "tests/fixtures/design_lint/component-voltage-ratings/power-control.kicad_sch"
        )
        contact_fixture = (
            repository
            / "tests/fixtures/design_lint/component-voltage-ratings/contact-control.kicad_sch"
        )
        mosfet_fixture = repository / "tests/fixtures/design_lint/mosfet-stress/mosfet.kicad_sch"
        expected_fixture_sha256 = "c3dd7c1e551613664c776875e217d7580238d04f5f40fe093ff6a86b1fa82af0"
        expected_power_fixture_sha256 = (
            "0c3f36df5ce9601d5424a9928da7c13b07199c95a4c80e9c59675c96618beba1"
        )
        expected_contact_fixture_sha256 = (
            "a210495b6df2c7f43ca4d44361c6be6f022d31116dbd4efa200c76faf03f3182"
        )
        expected_mosfet_fixture_sha256 = (
            "92e70feba1b173c5cbcf8bf2bc9d820be1f7bf1116448e76b072da0b7d1119b6"
        )
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), expected_fixture_sha256)
        self.assertEqual(
            hashlib.sha256(power_fixture.read_bytes()).hexdigest(), expected_power_fixture_sha256
        )
        self.assertEqual(
            hashlib.sha256(contact_fixture.read_bytes()).hexdigest(),
            expected_contact_fixture_sha256,
        )
        self.assertEqual(
            hashlib.sha256(mosfet_fixture.read_bytes()).hexdigest(), expected_mosfet_fixture_sha256
        )
        normalized_hashes: dict[str, str] = {}
        power_normalized_hashes: dict[str, str] = {}
        contact_normalized_hashes: dict[str, str] = {}
        mosfet_normalized_hashes: dict[str, str] = {}
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-component-rating-{project}")
                component_rating_fixtures_lane(root, project=project, image=config.image, log=log)
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("component-voltage-rating-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "component-voltage-rating-fixture/native-export",
                        "component-voltage-rating-fixture/control",
                        "component-voltage-rating-fixture/over-limit-fault",
                    },
                )
                native = results["component-voltage-rating-fixture/native-export"]
                self.assertEqual(native["status"], "PASS")
                self.assertEqual(native["fixture_sha256"], expected_fixture_sha256)
                self.assertEqual(native["kicad_version"], version)
                self.assertEqual(native["image"], expected_images[project])
                self.assertEqual(native["repeatable"], "true")
                self.assertEqual(native["repeatability_basis"], "normalized_netlist_and_erc")
                self.assertEqual(
                    native["normalized_netlist_sha256"],
                    native["repeat_normalized_netlist_sha256"],
                )
                self.assertEqual(
                    native["normalized_erc_sha256"],
                    native["repeat_normalized_erc_sha256"],
                )
                self.assertEqual(native["native_erc_error_types"], "none")
                normalized_hashes[project] = native["normalized_netlist_sha256"]
                self.assertEqual(
                    results["component-voltage-rating-fixture/control"]["utilization_status"],
                    "PASS",
                )
                self.assertEqual(
                    results["component-voltage-rating-fixture/over-limit-fault"][
                        "utilization_status"
                    ],
                    "FAIL",
                )
                for case in (
                    "component-voltage-rating-fixture/control",
                    "component-voltage-rating-fixture/over-limit-fault",
                ):
                    self.assertEqual(results[case]["kicad_version"], version)
                    self.assertEqual(results[case]["image"], expected_images[project])
                    self.assertEqual(results[case]["fixture_sha256"], expected_fixture_sha256)
                    self.assertEqual(results[case]["repeatable"], "true")
                    self.assertEqual(
                        results[case]["normalized_erc_sha256"],
                        native["normalized_erc_sha256"],
                    )
                    self.assertEqual(results[case]["native_erc_error_types"], "none")
                power_results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("component-power-rating-fixture/")
                }
                self.assertEqual(
                    set(power_results),
                    {
                        "component-power-rating-fixture/native-export",
                        "component-power-rating-fixture/control",
                        "component-power-rating-fixture/over-limit-fault",
                    },
                )
                power_native = power_results["component-power-rating-fixture/native-export"]
                self.assertEqual(power_native["status"], "PASS")
                self.assertEqual(power_native["fixture_sha256"], expected_power_fixture_sha256)
                self.assertEqual(power_native["kicad_version"], version)
                self.assertEqual(power_native["image"], expected_images[project])
                self.assertEqual(power_native["repeatable"], "true")
                self.assertEqual(
                    power_native["repeatability_basis"], "normalized_netlist_and_erc_types"
                )
                self.assertEqual(
                    power_native["normalized_netlist_sha256"],
                    power_native["repeat_normalized_netlist_sha256"],
                )
                self.assertEqual(
                    power_native["normalized_erc_sha256"],
                    power_native["repeat_normalized_erc_sha256"],
                )
                self.assertEqual(power_native["native_erc_error_types"], "none")
                power_normalized_hashes[project] = power_native["normalized_netlist_sha256"]
                self.assertEqual(
                    power_results["component-power-rating-fixture/control"]["utilization_status"],
                    "PASS",
                )
                self.assertEqual(
                    power_results["component-power-rating-fixture/over-limit-fault"][
                        "utilization_status"
                    ],
                    "FAIL",
                )
                for case in (
                    "component-power-rating-fixture/control",
                    "component-power-rating-fixture/over-limit-fault",
                ):
                    self.assertEqual(power_results[case]["kicad_version"], version)
                    self.assertEqual(power_results[case]["image"], expected_images[project])
                    self.assertEqual(
                        power_results[case]["fixture_sha256"], expected_power_fixture_sha256
                    )
                    self.assertEqual(power_results[case]["repeatable"], "true")
                    self.assertEqual(
                        power_results[case]["normalized_erc_sha256"],
                        power_native["normalized_erc_sha256"],
                    )
                    self.assertEqual(power_results[case]["native_erc_error_types"], "none")
                contact_results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("connector-contact-rating-fixture/")
                }
                self.assertEqual(
                    set(contact_results),
                    {
                        "connector-contact-rating-fixture/native-export",
                        "connector-contact-rating-fixture/control",
                        "connector-contact-rating-fixture/over-limit-fault",
                    },
                )
                contact_native = contact_results["connector-contact-rating-fixture/native-export"]
                self.assertEqual(contact_native["status"], "PASS")
                self.assertEqual(contact_native["fixture_sha256"], expected_contact_fixture_sha256)
                self.assertEqual(contact_native["kicad_version"], version)
                self.assertEqual(contact_native["image"], expected_images[project])
                self.assertEqual(contact_native["repeatable"], "true")
                self.assertEqual(
                    contact_native["repeatability_basis"], "normalized_netlist_and_erc_types"
                )
                self.assertEqual(
                    contact_native["normalized_netlist_sha256"],
                    contact_native["repeat_normalized_netlist_sha256"],
                )
                self.assertEqual(
                    contact_native["normalized_erc_sha256"],
                    contact_native["repeat_normalized_erc_sha256"],
                )
                self.assertEqual(contact_native["native_erc_error_types"], "none")
                contact_normalized_hashes[project] = contact_native["normalized_netlist_sha256"]
                self.assertEqual(
                    contact_results["connector-contact-rating-fixture/control"][
                        "utilization_status"
                    ],
                    "PASS",
                )
                self.assertEqual(
                    contact_results["connector-contact-rating-fixture/over-limit-fault"][
                        "utilization_status"
                    ],
                    "FAIL",
                )
                for case in (
                    "connector-contact-rating-fixture/control",
                    "connector-contact-rating-fixture/over-limit-fault",
                ):
                    self.assertEqual(contact_results[case]["kicad_version"], version)
                    self.assertEqual(contact_results[case]["image"], expected_images[project])
                    self.assertEqual(
                        contact_results[case]["fixture_sha256"], expected_contact_fixture_sha256
                    )
                    self.assertEqual(contact_results[case]["repeatable"], "true")
                    self.assertEqual(
                        contact_results[case]["normalized_erc_sha256"],
                        contact_native["normalized_erc_sha256"],
                    )
                    self.assertEqual(contact_results[case]["native_erc_error_types"], "none")
                mosfet_results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("component-mosfet-stress-fixture/")
                }
                self.assertEqual(
                    set(mosfet_results),
                    {
                        "component-mosfet-stress-fixture/native-export",
                        "component-mosfet-stress-fixture/control",
                        "component-mosfet-stress-fixture/over-limit-fault",
                    },
                )
                mosfet_native = mosfet_results["component-mosfet-stress-fixture/native-export"]
                self.assertEqual(mosfet_native["status"], "PASS")
                self.assertEqual(mosfet_native["fixture_sha256"], expected_mosfet_fixture_sha256)
                self.assertEqual(mosfet_native["kicad_version"], version)
                self.assertEqual(mosfet_native["image"], expected_images[project])
                self.assertEqual(mosfet_native["repeatable"], "true")
                self.assertEqual(
                    mosfet_native["repeatability_basis"], "normalized_netlist_and_erc_types"
                )
                self.assertEqual(
                    mosfet_native["normalized_netlist_sha256"],
                    mosfet_native["repeat_normalized_netlist_sha256"],
                )
                self.assertEqual(
                    mosfet_native["normalized_erc_sha256"],
                    mosfet_native["repeat_normalized_erc_sha256"],
                )
                self.assertEqual(mosfet_native["native_erc_error_types"], "none")
                mosfet_normalized_hashes[project] = mosfet_native["normalized_netlist_sha256"]
                self.assertEqual(
                    mosfet_results["component-mosfet-stress-fixture/control"]["utilization_status"],
                    "PASS",
                )
                self.assertEqual(
                    mosfet_results["component-mosfet-stress-fixture/over-limit-fault"][
                        "utilization_status"
                    ],
                    "FAIL",
                )
                for case in (
                    "component-mosfet-stress-fixture/control",
                    "component-mosfet-stress-fixture/over-limit-fault",
                ):
                    self.assertEqual(mosfet_results[case]["kicad_version"], version)
                    self.assertEqual(mosfet_results[case]["image"], expected_images[project])
                    self.assertEqual(
                        mosfet_results[case]["fixture_sha256"], expected_mosfet_fixture_sha256
                    )
                    self.assertEqual(mosfet_results[case]["repeatable"], "true")
                    self.assertEqual(mosfet_results[case]["native_erc_error_types"], "none")
                receipt = root / native["command_receipt"]
                self.assertTrue(receipt.is_file())
                command = json.loads(receipt.read_text())
                mounts = tuple(
                    command["argv"][index + 1]
                    for index, item in enumerate(command["argv"][:-1])
                    if item == "-v"
                )
                self.assertEqual(len(mounts), 3)
                self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                self.assertEqual(sum(item.endswith(":/mosfet-fixture:ro") for item in mounts), 1)
                self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)
        self.assertEqual(len(set(normalized_hashes.values())), 1)
        self.assertEqual(len(set(power_normalized_hashes.values())), 1)
        self.assertEqual(len(set(contact_normalized_hashes.values())), 1)
        self.assertEqual(len(set(mosfet_normalized_hashes.values())), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES") == "1",
    "native IC rail-capacitor fixtures run in the digest-pinned package acceptance lane",
)
class NativeIcRailCapacitorFixtureTests(unittest.TestCase):
    def test_missing_capacitor_and_controls_export_repeatably(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, ic_rail_capacitor_fixture_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-ic-rail-capacitor-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        expected_versions = {
            "controller": "10.0.0",
            "raspberry-pi-status-led": "10.0.5",
        }
        expected_images = {
            "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
            "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        }
        expected_source_hashes = {
            "positive-rail-no-cap": "09ec95768fb247b1ec781a078f585b27eee66ae7e40bc0251cefb7ebef511e7a",
            "positive-rail-cap-control": "2e67336b13f8ff9b62dd4e40bd45a4116e4d825d78f361537ea3693d4e18d4a2",
            "unrecognized-rail-control": "0d42a2f557d2488425a7b1767e7e3b782c4bfe2c2e11bc2344f41513c49c7fb9",
            "source-backed-control": "2a3632b71b5c7bc01b282cb2d23a5b49df5759364a99e588b98b659654c9d45f",
            "source-backed-no-cap": "5db3396470f1e3b8101e428dc25b41c4166f1748e4a68ad88a3ac2757173952a",
            "source-backed-dnp-capacitor": "8184bd9c297b40d0192af1e446206939ec7d5466bc8e306a0292472da7424b6c",
            "custom-capacitor-role-control": "338b39009694575fae172d6691ddd8d17804d74503ad73c374a53661373e789d",
            "custom-capacitor-role-wrong-return": "52edf68703b6fc4052fbb7197778108fc52c0a4ac4195bd533a1d1aaead8669a",
        }
        expected_findings: dict[str, tuple[str, set[str]]] = {
            "positive-rail-no-cap": ("REVIEW", {"+3V3: IC supply decoupling review"}),
            "positive-rail-cap-control": ("PASS", set()),
            "unrecognized-rail-control": ("REVIEW", set()),
            "source-backed-control": ("PASS", set()),
            "source-backed-no-cap": ("REVIEW", {"+3V3: IC supply decoupling review"}),
            "source-backed-dnp-capacitor": (
                "REVIEW",
                {"+3V3: IC supply decoupling review"},
            ),
            "custom-capacitor-role-control": ("PASS", set()),
            "custom-capacitor-role-wrong-return": (
                "REVIEW",
                {"+3V3: IC supply decoupling review"},
            ),
        }
        expected_source_path_findings = {
            "positive-rail-no-cap": "none",
            "positive-rail-cap-control": "none",
            "unrecognized-rail-control": ("LOCAL_A: power-input source-path review"),
            "source-backed-control": "none",
            "source-backed-no-cap": "none",
            "source-backed-dnp-capacitor": "none",
            "custom-capacitor-role-control": "none",
            "custom-capacitor-role-wrong-return": "none",
        }
        expected_power_pin_not_driven = {
            "positive-rail-no-cap",
            "positive-rail-cap-control",
            "unrecognized-rail-control",
        }
        for project, version in expected_versions.items():
            with self.subTest(project=project):
                config = selected_config(root, project)
                self.assertEqual(config.kicad_version, version)
                self.assertEqual(config.image, expected_images[project])
                log = HostedLog(root, f"native-ic-rail-capacitor-{project}")
                ic_rail_capacitor_fixture_lane(
                    root,
                    project=project,
                    image=config.image,
                    log=log,
                )
                events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
                results = {
                    item["stage"]: item
                    for item in events
                    if item.get("stage", "").startswith("ic-rail-cap-fixture/")
                }
                self.assertEqual(
                    set(results),
                    {
                        "ic-rail-cap-fixture/native-export",
                        "ic-rail-cap-fixture/positive-rail-no-cap",
                        "ic-rail-cap-fixture/positive-rail-cap-control",
                        "ic-rail-cap-fixture/unrecognized-rail-control",
                        "ic-rail-cap-fixture/source-backed-control",
                        "ic-rail-cap-fixture/source-backed-no-cap",
                        "ic-rail-cap-fixture/source-backed-dnp-capacitor",
                        "ic-rail-cap-fixture/custom-capacitor-role-control",
                        "ic-rail-cap-fixture/custom-capacitor-role-wrong-return",
                    },
                )
                native = results["ic-rail-cap-fixture/native-export"]
                self.assertEqual(native["status"], "PASS")
                for case, (expected_status, expected_case_findings) in expected_findings.items():
                    result = results[f"ic-rail-cap-fixture/{case}"]
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(result["lint_status"], expected_status)
                    self.assertEqual(
                        result["source_path_findings"], expected_source_path_findings[case]
                    )
                    self.assertEqual(
                        set(result["capacitor_findings"].split(";"))
                        if result["capacitor_findings"] != "none"
                        else set(),
                        expected_case_findings,
                    )
                    self.assertEqual(result["kicad_version"], version)
                    self.assertEqual(result["image"], expected_images[project])
                    self.assertEqual(result["repeatable"], "true")
                    self.assertEqual(result["source_sha256"], expected_source_hashes[case])
                    self.assertEqual(
                        result["normalized_netlist_sha256"],
                        result["repeat_normalized_netlist_sha256"],
                    )
                    self.assertEqual(
                        result["normalized_erc_sha256"],
                        result["repeat_normalized_erc_sha256"],
                    )
                    self.assertEqual(
                        result["power_pin_not_driven"],
                        "true" if case in expected_power_pin_not_driven else "false",
                    )
                    self.assertEqual(
                        "power_pin_not_driven" in result["native_erc_types"].split(","),
                        case in expected_power_pin_not_driven,
                    )
                    self.assertEqual(
                        result["native_erc_error_types"],
                        "power_pin_not_driven" if case in expected_power_pin_not_driven else "none",
                    )
                    receipt = root / result["command_receipt"]
                    self.assertTrue(receipt.is_file())
                    command = json.loads(receipt.read_text())
                    mounts = tuple(
                        command["argv"][index + 1]
                        for index, item in enumerate(command["argv"][:-1])
                        if item == "-v"
                    )
                    self.assertEqual(len(mounts), 2)
                    self.assertEqual(sum(item.endswith(":/fixtures:ro") for item in mounts), 1)
                    self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES") == "1",
    "native control-input demos run in the digest-pinned package acceptance lane",
)
class NativeControlInputDemoTests(unittest.TestCase):
    def test_native_public_demos_record_connected_bias_and_unconnected_controls(self) -> None:
        from kicad_tooling.ci_hosted import HostedLog, native_control_input_demo_lane
        from kicad_tooling.hwrepo.electrical import selected_config

        repository = Path(__file__).resolve().parents[1]
        acceptance = repository / "build/ci"
        acceptance.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-control-input-demo-project-", dir=acceptance))
        shutil.copytree(
            reference_root(),
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        project = "raspberry-pi-status-led"
        config = selected_config(root, project)
        self.assertEqual(config.kicad_version, "10.0.5")
        log = HostedLog(root, "native-control-input-demos")
        native_control_input_demo_lane(root, project=project, image=config.image, log=log)

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("control-input-demo/")
        }
        expected_candidates = {
            "cm5-minima": "none",
            "jetson-agx-thor": "J14.23|SDIO_~{RESET}|reset|input",
            "coldfire-xilinx": "VR201.4|SHDN|enable|input",
            "vme-wren": (
                "IC19.3|~{RESET}|reset|input;IC21.3|~{RESET}|reset|input;"
                "IC30.33|BOOT_B|boot/strap|input;IC30.38|BOOT_A|boot/strap|input"
            ),
            "por-alias-fixture": "U1.1|POR_B|reset|input",
        }
        expected_connected_bias = {
            "cm5-minima": (
                4,
                "7c96b511e8fa95eef6dc8fff36c45e92c34e1cfbcc54db7400a2e3149fdd9709",
            ),
            "jetson-agx-thor": (
                24,
                "04bd60403bf87f8a4edf249d582a5b7620974dd333b53e5e80c6db9af8dc9f71",
            ),
            "coldfire-xilinx": (
                2,
                "371dfc8d9313aabf215947750e2ad170d9c5b69f6f03a171ae90e81a73bfb929",
            ),
            "vme-wren": (
                12,
                "2ee541b32622143b5293f6add4da0d0c6b32137ec15521fd2bafb6fe9e3df050",
            ),
            "por-alias-fixture": (
                0,
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
            ),
        }
        self.assertEqual(
            set(results),
            {"control-input-demo/native-export"}
            | {f"control-input-demo/{sample}" for sample in expected_candidates},
        )
        native = results["control-input-demo/native-export"]
        self.assertEqual(native["status"], "PASS")
        receipt = root / native["command_receipt"]
        self.assertTrue(receipt.is_file())
        command = json.loads(receipt.read_text())
        argv = command["argv"]
        self.assertIn("none", argv)
        self.assertIn("--read-only", argv)
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        self.assertEqual(len(mounts), 2)
        self.assertEqual(sum(item.endswith(":/synthetic:ro") for item in mounts), 1)
        self.assertEqual(sum(item.endswith(":/output:rw") for item in mounts), 1)

        for sample, expected in expected_candidates.items():
            with self.subTest(sample=sample):
                result = results[f"control-input-demo/{sample}"]
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["kicad_version"], "10.0.5")
                self.assertEqual(result["image"], config.image)
                self.assertEqual(result["review_candidates"], expected)
                expected_count, expected_sha256 = expected_connected_bias[sample]
                bias_candidates = json.loads(result["connected_bias_candidates"])
                self.assertEqual(len(bias_candidates), expected_count)
                self.assertEqual(result["connected_bias_candidate_count"], str(expected_count))
                canonical_bias_candidates = json.dumps(
                    bias_candidates,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                self.assertEqual(
                    hashlib.sha256(canonical_bias_candidates).hexdigest(), expected_sha256
                )
                self.assertEqual(result["connected_bias_candidates_sha256"], expected_sha256)
                self.assertEqual(result["repeatable"], "true")
                self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(result["source_manifest_sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(int(result["source_manifest_entries"]), 0)
                self.assertRegex(result["raw_netlist_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(result["repeat_raw_netlist_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    result["normalized_netlist_sha256"],
                    result["repeat_normalized_netlist_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
