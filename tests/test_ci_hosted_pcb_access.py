"""Digest-pinned native PCB access and return-plane acceptance."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from tests.support import reference_root

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@unittest.skipUnless(
    os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") == "1",
    "native PCB fixtures run in the digest-pinned package acceptance lane",
)
class NativePcbAccessFixtureTests(unittest.TestCase):
    def test_pcb_geometry_probe_controls_on_supported_images(self) -> None:
        from kicad_tooling.ci_hosted import (
            HostedLog,
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
