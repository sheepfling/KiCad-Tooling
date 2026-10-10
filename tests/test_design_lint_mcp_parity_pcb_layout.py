"""Design-lint CLI/MCP parity cases: design lint mcp parity pcb layout."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

import os
import shutil
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
    PcbProtectionPathMap,
    PcbProtectionPathRequirement,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopPad,
    PcbSwitchingLoopRequirement,
    ProjectTestContract,
)
from kicad_tooling.hwrepo.pcb_track_width_models import (
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    pcb_native_snapshot_shim,
    run_mcp_parity,
)


class _DesignLintMcpParityPcbLayoutCases(McpParityHarness):
    async def _case_test_pcb_decoupling_track_width_and_switching_loop_map_parity(self) -> None:
        """Compare source-bound PCB geometry maps through both adapters."""
        fixture = (
            Path(__file__).parents[1]
            / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
        )
        board_path = self.island / "kicad/controller.kicad_pcb"
        shutil.copyfile(fixture, board_path)
        native = self.native_evidence()
        requirement = PcbDecouplingRequirement(
            id="synthetic-core-rail",
            basis="Synthetic pin map and placement threshold",
            ic_reference="U1",
            ic_footprint="Synthetic:IC_QFN",
            supply_pad="U1.1",
            return_pad="U1.2",
            supply_net="VDD",
            return_net="GND",
            capacitors=(
                PcbDecouplingCapacitor(
                    reference="C1",
                    footprint="Synthetic:Cap_0603",
                    supply_pad="C1.1",
                    return_pad="C1.2",
                ),
            ),
            selection="any",
            max_distance_um=1000,
            max_return_via_distance_um=1000,
        )
        policy = DesignLintPolicy(
            pcb_protection_path_map=PcbProtectionPathMap(
                basis="Synthetic mapped ESD entry pad and return-via coverage",
                requirements=(
                    PcbProtectionPathRequirement(
                        id="synthetic-usb-d-plus-protection",
                        connector_reference="J1",
                        connector_footprint="Synthetic:Conn1",
                        connector_signal_pad="J1.1",
                        protection_reference="D1",
                        protection_footprint="Synthetic:TVS",
                        protection_signal_pad="D1.1",
                        protection_reference_pad="D1.2",
                        signal_net="DATA",
                        reference_net="GND",
                        max_entry_distance_um=650,
                        minimum_reference_vias=1,
                        reference_via_radius_um=3000,
                    ),
                ),
            ),
            pcb_decoupling_map=PcbDecouplingMap(
                basis="Synthetic KiCad native report parity map",
                requirements=(requirement,),
            ),
            pcb_track_width_map=PcbTrackWidthMap(
                basis="Synthetic KiCad native width parity map",
                requirements=(
                    PcbTrackWidthRequirement(
                        id="synthetic-vdd-width",
                        basis="Synthetic 251 um screen against a 250 um track",
                        net="VDD",
                        minimum_width_um=251,
                    ),
                ),
            ),
            pcb_reference_plane_map=PcbReferencePlaneMap(
                basis="Synthetic adjacent-reference coverage parity map",
                requirements=(
                    PcbReferencePlaneRequirement(
                        id="synthetic-vdd-reference",
                        basis="Synthetic VDD route expected over adjacent GND copper",
                        signal_net="VDD",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=500,
                        minimum_referenced_fraction=0.9,
                        review_excluded_short_tracks=True,
                    ),
                    PcbReferencePlaneRequirement(
                        id="synthetic-data-reference",
                        basis="Synthetic DATA route with a mapped endpoint-via clearance",
                        signal_net="DATA",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=1,
                        minimum_referenced_fraction=0.9,
                    ),
                ),
            ),
            pcb_switching_loop_map=PcbSwitchingLoopMap(
                basis="Synthetic buck loop pad-center and return-plane mapping",
                requirements=(
                    PcbSwitchingLoopRequirement(
                        id="synthetic-buck-input-loop",
                        basis="Synthetic input-capacitor and switching-path mapping",
                        loop_pads=(
                            PcbSwitchingLoopPad(
                                pad="U1.1", footprint="Synthetic:IC_QFN", net="VDD"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.1", footprint="Synthetic:Cap_0603", net="VDD"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.2", footprint="Synthetic:Cap_0603", net="GND"
                            ),
                            PcbSwitchingLoopPad(
                                pad="U1.2", footprint="Synthetic:IC_QFN", net="GND"
                            ),
                        ),
                        return_net="GND",
                        return_plane_layer="B.Cu",
                        return_plane_pads=(
                            PcbSwitchingLoopPad(
                                pad="U1.2", footprint="Synthetic:IC_QFN", net="GND"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.2", footprint="Synthetic:Cap_0603", net="GND"
                            ),
                        ),
                        maximum_area_um2=1000,
                        route_edges=(
                            PcbSwitchingLoopEdge(
                                from_pad="U1.1",
                                to_pad="C1.1",
                                kind="trace",
                                net="VDD",
                                layers=("F.Cu",),
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C1.1",
                                to_pad="C1.2",
                                kind="component",
                                component_reference="C1",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C1.2",
                                to_pad="U1.2",
                                kind="plane",
                                net="GND",
                                plane_layer="B.Cu",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="U1.2",
                                to_pad="U1.1",
                                kind="component",
                                component_reference="U1",
                            ),
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        shim = self.base / "docker-shim"
        shim.mkdir()
        docker = shim / "docker"
        docker.write_text(
            pcb_native_snapshot_shim(),
            encoding="utf-8",
        )
        docker.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join((str(shim), environment["PATH"]))
        config = load_config(self.root, self.island / "project.json")

        async with Client(create_server(self.root), mode="legacy") as client:
            with patch.dict(os.environ, {"PATH": environment["PATH"]}):
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1,
                )
                mcp = await self.call(
                    client,
                    "inspect_design_lint",
                    DesignLintReport,
                    {
                        "project_id": "controller",
                        "native_summary": native.relative_to(self.root).as_posix(),
                    },
                )
        cli_result = cli.model_dump(mode="json")
        mcp_result = mcp.model_dump(mode="json")
        for report in (cli_result, mcp_result):
            report["pcb_decoupling"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_protection_path"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_track_width"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_reference_plane"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_switching_loop"]["snapshot_path"] = "<per-run native snapshot>"

        self.assertEqual(cli_result, mcp_result)
        self.assertEqual(mcp.status, "REVIEW", mcp.issues)
        self.assertEqual(mcp.pcb_decoupling.status, "COMPLETE")
        self.assertEqual(mcp.pcb_protection_path.status, "COMPLETE")
        self.assertEqual(
            mcp.pcb_protection_path.entries[0].connector_to_protection_distance_nm,
            650_000,
        )
        self.assertEqual(mcp.pcb_protection_path.entries[0].reference_vias_within_radius, 1)
        self.assertEqual(mcp.pcb_decoupling.entries[0].selected_capacitors, ("C1",))
        self.assertEqual(mcp.pcb_decoupling.entries[0].candidates[0].distance_nm, 500_000)
        self.assertEqual(
            mcp.pcb_decoupling.entries[0].candidates[0].return_via_distance_nm,
            0,
        )
        self.assertEqual(
            mcp.pcb_decoupling.entries[0].candidates[0].nearest_return_via_id,
            "e" * 64,
        )
        self.assertEqual(mcp.pcb_track_width.status, "COMPLETE")
        self.assertEqual(mcp.pcb_track_width.entries[0].tracks[0].width_nm, 250_000)
        self.assertTrue(mcp.pcb_track_width.entries[0].tracks[0].below_minimum)
        self.assertEqual(mcp.pcb_reference_plane.status, "INCOMPLETE")
        self.assertEqual(mcp.pcb_reference_plane.entries[0].tracks[0].reference_layer, "In1.Cu")
        self.assertEqual(mcp.pcb_reference_plane.entries[0].tracks[0].covered_fraction_numerator, 0)
        self.assertTrue(mcp.pcb_reference_plane.entries[0].tracks[0].below_minimum)
        self.assertTrue(mcp.pcb_reference_plane.entries[0].review_excluded_short_tracks)
        self.assertEqual(
            mcp.pcb_reference_plane.entries[0].excluded_short_track_uuids,
            ("00000000-0000-0000-0000-000000000104",),
        )
        self.assertEqual(mcp.pcb_switching_loop.status, "INCOMPLETE")
        loop = mcp.pcb_switching_loop.entries[0]
        self.assertEqual(loop.loop_area_twice_nm2, 1_000_000_000)
        self.assertEqual(loop.return_plane_status, "CONNECTED")
        self.assertEqual(loop.return_island_index, 0)
        self.assertEqual(loop.route_status, "INCOMPLETE")
        self.assertEqual(loop.route_edges[0].status, "RESOLVED")
        self.assertEqual(loop.route_edges[0].length_nm, 500_000)
        plane_edge = loop.route_edges[2]
        self.assertEqual(plane_edge.status, "DECLARED")
        self.assertIsNotNone(plane_edge.plane_zone_uuid)
        self.assertEqual(plane_edge.plane_island_index, 0)
        self.assertEqual(plane_edge.plane_island_area_twice_nm2, 2_000_000_000_000)
        route_finding = next(
            item for item in mcp.findings if item.rule_id == "pcb.switching_loop_geometry"
        )
        self.assertIn("length 500000 nm", route_finding.evidence["trace_route_edges"][0])
        finding = next(item for item in mcp.findings if item.rule_id == "pcb.minimum_track_width")
        self.assertEqual(finding.evidence["net"], ("VDD",))
        reference_finding = next(
            item
            for item in mcp.findings
            if item.rule_id == "pcb.reference_plane_coverage" and "VDD" in item.subject
        )
        self.assertIn("VDD", reference_finding.subject)
        data_reference = next(
            item
            for item in mcp.pcb_reference_plane.entries
            if item.id == "synthetic-data-reference"
        )
        data_measurement = data_reference.tracks[0]
        data_via_id = "f" * 64
        self.assertEqual(
            (
                data_measurement.covered_fraction_numerator,
                data_measurement.covered_fraction_denominator,
            ),
            (1, 2),
        )
        self.assertTrue(data_measurement.below_minimum)
        self.assertEqual(data_measurement.endpoint_via_ids, (data_via_id,))
        self.assertEqual(
            data_measurement.endpoint_via_ids_with_center_in_reference_holes,
            (data_via_id,),
        )
        data_reference_finding = next(
            item
            for item in mcp.findings
            if item.rule_id == "pcb.reference_plane_coverage"
            and "synthetic-data-reference" in item.subject
        )
        self.assertIn(
            "do not identify which clearance created a hole", data_reference_finding.message
        )
        self.assertEqual(
            data_reference_finding.evidence["endpoint_via_hole_candidates"],
            (data_via_id,),
        )
        assert mcp.pcb_decoupling.snapshot_path is not None
        snapshot_path = self.root / mcp.pcb_decoupling.snapshot_path
        self.assertEqual(digest(snapshot_path), mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(mcp.pcb_track_width.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(
            mcp.pcb_protection_path.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256
        )
        self.assertEqual(
            mcp.pcb_reference_plane.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256
        )
        self.assertEqual(mcp.pcb_switching_loop.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(config.kicad_version, "10.0.0")

    async def _case_test_missing_native_evidence_keeps_configured_pcb_width_gap_visible(
        self,
    ) -> None:
        """A failed native lane must not erase configured width-map coverage."""
        policy = DesignLintPolicy(
            pcb_track_width_map=PcbTrackWidthMap(
                basis="Synthetic authored width review",
                requirements=(
                    PcbTrackWidthRequirement(
                        id="synthetic-vdd-width",
                        basis="Synthetic minimum width",
                        net="VDD",
                        minimum_width_um=250,
                    ),
                ),
            )
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))
        missing_summary = self.root / "build/missing-native-summary.json"
        missing_summary.parent.mkdir(parents=True, exist_ok=True)
        missing_summary.write_text("{ malformed synthetic summary", encoding="utf-8")

        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(missing_summary),
                expected_exit=1,
            )
            mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": missing_summary.relative_to(self.root).as_posix(),
                },
            )

        for report in (cli, mcp):
            self.assertEqual(report.status, "BLOCKED")
            self.assertEqual(report.pcb_track_width.status, "BLOCKED")
            self.assertIn("native PCB geometry is unavailable", report.pcb_track_width.issue or "")


def test_pcb_decoupling_track_width_and_switching_loop_map_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPcbLayoutCases,
        "_case_test_pcb_decoupling_track_width_and_switching_loop_map_parity",
    )


def test_missing_native_evidence_keeps_configured_pcb_width_gap_visible() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPcbLayoutCases,
        "_case_test_missing_native_evidence_keeps_configured_pcb_width_gap_visible",
    )
