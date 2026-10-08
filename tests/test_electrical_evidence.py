"""Release electrical evidence rejects stale, incomplete and relabeled receipts."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.electrical_evidence import required_projects, verify_electrical
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ControlBiasResistorRequirement,
    ControlInputsAnalysis,
    ControlLocalBiasRequirement,
    ControlPinRequirement,
    ControlSignalRequirement,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    PcbAccessAnalysis,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
    PinConnectivityAnalysis,
    PinRelationshipRule,
    ReleaseClass,
    ReleaseEvidence,
    ReleaseManifest,
    ReleaseStatus,
    RequiredTestAccess,
    ValidationSummary,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from kicad_tooling.hwrepo.models import (
    TestAccessProbeEnvelope as AccessProbeEnvelope,
)
from kicad_tooling.hwrepo.pcb_return_paths import (
    capture_native_pcb_connectivity,
    native_pcb_command_matches,
    native_probe_source,
)
from kicad_tooling.hwrepo.releasing import reference, retained_paths
from kicad_tooling.validate import hashes
from tests import test_contract_coach as coaching
from tests.support import initialize_git
from tests.test_component_power_ratings import (
    native_netlist_xml as component_power_netlist_xml,
)
from tests.test_component_power_ratings import (
    requirement as component_power_requirement,
)
from tests.test_component_voltage_ratings import (
    native_netlist_xml as component_voltage_netlist_xml,
)
from tests.test_component_voltage_ratings import (
    requirement as component_voltage_requirement,
)
from tests.test_connector_contact_ratings import (
    native_netlist_xml as connector_contact_netlist_xml,
)
from tests.test_connector_contact_ratings import (
    requirement as connector_contact_requirement,
)
from tests.test_digital_peer_voltages import requirement as digital_peer_requirement
from tests.test_electrical import (
    ISLAND,
    NA,
    PROJECT,
    can_split_termination_requirement,
    i2c_pullup_window_requirement,
    install_fixture,
    power_connectivity_requirement,
    rs485_requirement,
    serial_peer_requirement,
    spi_requirement,
    usb_c_requirement,
)
from tests.test_mosfet_stress import native_netlist_xml as mosfet_stress_netlist_xml
from tests.test_mosfet_stress import requirement as mosfet_stress_requirement


def digital_peer_netlist_xml() -> str:
    return (
        "<export><components>"
        '<comp ref="U1"><value>Synthetic controller</value>'
        "<footprint>Package_QFP:LQFP-48</footprint>"
        '<libsource lib="Synthetic" part="Controller"/>'
        '<units><unit name="A"><pins><pin num="12"/></pins></unit></units></comp>'
        '<comp ref="U2"><value>Synthetic peripheral</value>'
        "<footprint>Package_SO:SOIC-8</footprint>"
        '<libsource lib="Synthetic" part="Peripheral"/>'
        '<units><unit name="A"><pins><pin num="3"/></pins></unit></units></comp>'
        "</components><libparts>"
        '<libpart lib="Synthetic" part="Controller"><pins>'
        '<pin num="12" name="MOSI" type="output"/></pins></libpart>'
        '<libpart lib="Synthetic" part="Peripheral"><pins>'
        '<pin num="3" name="SDI" type="input"/></pins></libpart>'
        "</libparts><nets>"
        '<net name="SPI_MOSI"><node ref="U1" pin="12"/>'
        '<node ref="U2" pin="3"/></net>'
        "</nets></export>"
    )


class ElectricalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = coaching.ContractCoachTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.native = reference(self.root, fixture.native / "summary.json")
        self.contract = install_fixture(self.root).model_copy(
            update={"grounding": NA, "high_frequency": NA}
        )
        write_model(self.root / ISLAND / "tests/electrical.json", self.contract)
        initialize_git(self.root)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic requirements",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        waveform = (
            "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
            "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
            "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
        )
        self.simulator = coaching.fake_executable(
            self.root.parent / "ngspice",
            (
                "from pathlib import Path\nimport sys\n"
                "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
                "else:\n"
                f"    Path('waveforms.raw').write_text({waveform!r})\n"
                "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
                "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
            ),
        )
        self.output = self.root / "build/electrical/release"
        result = analyze(self.root, PROJECT, self.output, ngspice=str(self.simulator))
        self.assertEqual(result.status, "PASS", result)
        self.path = self.output / "electrical.json"

    def verify(self) -> None:
        verify_electrical(
            self.root, reference(self.root, self.path), self.source, PROJECT, self.native
        )

    def test_exact_saved_requirements_logs_and_waveforms_pass_without_a_simulator(self) -> None:
        self.simulator.unlink()
        self.verify()
        result = json.loads(self.path.read_text())
        self.assertEqual(result["source"]["commit"], self.source.commit)
        candidate = ReleaseManifest(
            release_id="test",
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE,
            source_commit=self.source.commit or "",
            toolchain_id="kicad-10.0.0",
            projects=(PROJECT,),
            libraries=(),
            interfaces=(),
            artifacts=(),
            evidence=ReleaseEvidence(
                portable=self.native,
                native={},
                electrical={PROJECT: reference(self.root, self.path)},
            ),
        )
        retained = retained_paths(self.root, candidate)
        self.assertIn(self.path.relative_to(self.root).as_posix(), retained)
        self.assertIn(
            (self.output / "startup/waveforms.raw").relative_to(self.root).as_posix(), retained
        )

    def test_native_pcb_return_receipt_replays_exact_pad_zone_and_probe_evidence(self) -> None:
        config = selected_config(self.root, PROJECT)
        board_path = repo_path(self.root, config.project).with_suffix(".kicad_pcb")
        board_fixture = (
            Path(__file__).resolve().parents[1]
            / "kicad_tooling/hwrepo/fixtures/pcb-return-zone-connected.kicad_pcb"
        )
        board_path.write_bytes(board_fixture.read_bytes())
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic independently reviewed connector-return domain",
            domains=(
                PcbReturnDomainRequirement(
                    id="serial-returns",
                    basis="Synthetic DB9 pinout",
                    topology="direct",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J1.1", net="RETURN", footprint="Synthetic:TestPad"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J2.1", net="RETURN", footprint="Synthetic:TestPad"
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = self.contract.model_copy(
            update={
                "pcb_return_paths": requirement,
                "grounding": NA,
                "power": NA,
                "high_frequency": NA,
                "test_access": NA,
            }
        )
        write_model(contract_path, contract)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "add",
                board_path.relative_to(self.root).as_posix(),
                contract_path.relative_to(self.root).as_posix(),
            ),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic PCB return-path requirements",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        self.output = self.root / "build/electrical/pcb-return-paths"

        def capture(_root, selected, output):
            output.mkdir(parents=True)
            probe_copy = output / "native_pcb_probe.py"
            shutil.copyfile(native_probe_source(), probe_copy)
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
                    f"{_root}:/work:ro",
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
                    "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix(),
                    "/output/snapshot.json",
                ),
                started_utc=datetime.now(UTC).isoformat(),
                returncode=0,
            )
            write_model(output / "native.command.json", command)
            zone = PcbZoneIdentity(
                uuid="00000000-0000-0000-0000-000000000001",
                layer="F.Cu",
            )
            island = PcbZoneIslandIdentity(
                uuid=zone.uuid,
                layer=zone.layer,
                island_index=0,
            )
            return command, PcbConnectivitySnapshot(
                board_sha256=digest(board_path),
                kicad_version=selected.kicad_version,
                image=selected.image,
                probe_sha256=digest(probe_copy),
                zones_refilled=True,
                pads=(
                    PcbPadConnectivityObservation(
                        pad="J1.1",
                        net="RETURN",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=("J1.1", "J2.1"),
                        connected_zones=(zone,),
                        connected_islands=(island,),
                        connected_vias=(),
                    ),
                    PcbPadConnectivityObservation(
                        pad="J2.1",
                        net="RETURN",
                        footprint="Synthetic:TestPad",
                        dnp=False,
                        connected_pads=("J1.1", "J2.1"),
                        connected_zones=(zone,),
                        connected_islands=(island,),
                        connected_vias=(),
                    ),
                ),
                net_ties=(),
                zones=(
                    PcbZoneObservation(
                        uuid=zone.uuid,
                        layer=zone.layer,
                        name="",
                        net="RETURN",
                        filled_island_count=1,
                        unanchored_pad_island_indexes=(),
                    ),
                ),
                vias=(),
            )

        with patch(
            "kicad_tooling.hwrepo.electrical_runner.capture_native_pcb_connectivity",
            side_effect=capture,
        ):
            report = analyze(self.root, PROJECT, self.output, ngspice="missing-simulator")
        self.assertEqual(report.status, "PASS", report.checks)
        self.assertEqual(
            next(
                row.status
                for row in report.checks
                if row.id == "pcb-return-paths/serial-returns/connectivity"
            ),
            "PASS",
        )
        self.path = self.output / "electrical.json"
        self.verify()

        snapshot_path = self.output / "pcb-connectivity/snapshot.json"
        saved_snapshot = snapshot_path.read_bytes()
        saved_report = self.path.read_bytes()
        tampered_snapshot = json.loads(saved_snapshot)
        tampered_snapshot["pads"][0]["connected_pads"] = ["J1.1"]
        tampered_snapshot["pads"][1]["connected_pads"] = ["J2.1"]
        snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        self.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        try:
            with self.assertRaisesRegex(ValueError, "Retained electrical checks fail or omit"):
                self.verify()
        finally:
            snapshot_path.write_bytes(saved_snapshot)
            self.path.write_bytes(saved_report)
        self.verify()

        tampered_zone = json.loads(saved_snapshot)
        tampered_zone["zones"][0]["filled_island_count"] = 2
        tampered_zone["zones"][0]["unanchored_pad_island_indexes"] = [1]
        snapshot_path.write_text(json.dumps(tampered_zone), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        self.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        try:
            with self.assertRaisesRegex(ValueError, "Retained electrical checks fail or omit"):
                self.verify()
        finally:
            snapshot_path.write_bytes(saved_snapshot)
            self.path.write_bytes(saved_report)
        self.verify()

    def test_native_pcb_capture_rejects_source_drift_during_successful_runner_call(self) -> None:
        config = selected_config(self.root, PROJECT)
        board_path = repo_path(self.root, config.project).with_suffix(".kicad_pcb")
        board_fixture = (
            Path(__file__).resolve().parents[1]
            / "kicad_tooling/hwrepo/fixtures/pcb-return-alternate-layer-via.kicad_pcb"
        )
        board_path.write_bytes(board_fixture.read_bytes())
        original = board_path.read_bytes()
        original_digest = digest(board_path)
        output = self.root / "build/electrical/pcb-source-drift"

        def mutate_source_after_probe_started(root: Path, argv: tuple[str, ...], timeout: int):
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(timeout, 600)
            board_path.write_bytes(original + b"\n")
            (output / "snapshot.json").write_text(
                json.dumps({"board_sha256": original_digest}), encoding="utf-8"
            )
            command = CommandEvidence(
                argv=argv,
                started_utc=datetime.now(UTC).isoformat(),
                returncode=0,
            )
            self.assertTrue(native_pcb_command_matches(command, config))
            return command

        try:
            with (
                patch(
                    "kicad_tooling.hwrepo.pcb_return_paths.run_command",
                    side_effect=mutate_source_after_probe_started,
                ),
                self.assertRaisesRegex(
                    ValueError, "PCB source changed while native connectivity evidence was captured"
                ),
            ):
                capture_native_pcb_connectivity(self.root, config, output)
        finally:
            board_path.write_bytes(original)

    def test_saved_pcb_access_stages_replay_source_bound_pad_evidence(self) -> None:
        access = AccessAnalysis(
            basis="Synthetic service procedure requires a logic-rail measurement",
            pcb_accessibility=PcbAccessAnalysis(
                basis="Synthetic test pad must be placed and mask-open"
            ),
            decisions=(
                RequiredTestAccess(
                    mode="required",
                    id="logic-rail",
                    basis="Synthetic factory measurement point",
                    net="+3V3",
                    endpoints=(
                        AccessEndpointRequirement(
                            kind="test_point",
                            reference="TP1",
                            symbol="TestPoint:TestPoint",
                            footprint="TestPoint:TestPoint_Pad_D1.0mm",
                            pin="TP1.1",
                            electrical_type="passive",
                            approach_side="front",
                            probe_envelope=AccessProbeEnvelope(
                                tip_diameter_mm=0.8,
                                clearance_mm=0.1,
                            ),
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.root / ISLAND / "tests/electrical.json"
        write_model(
            contract_path,
            self.contract.model_copy(update={"test_access": access, "power": NA}),
        )
        config = selected_config(self.root, PROJECT)
        board_path = repo_path(self.root, config.project).with_suffix(".kicad_pcb")
        board_path.write_text(
            '(kicad_pcb (version 20250114) (net 0 "") (net 1 "+3V3") (net 2 "OTHER") '
            '(footprint "TestPoint:TestPoint_Pad_D1.0mm" (layer "F.Cu") '
            '(property "Reference" "TP1") '
            '(pad "1" smd circle (at 0 0) (size 1 1) '
            '(layers "F.Cu" "F.Mask") (net 1 "+3V3"))) '
            '(footprint "Synthetic:Obstacle" (layer "F.Cu") (at 1 0) '
            '(property "Reference" "TP2") '
            '(pad "1" smd circle (at 0 0) (size 1 1) '
            '(layers "F.Cu" "F.Mask") (net 2 "OTHER"))))',
            encoding="utf-8",
        )
        native_path = self.root / self.native.path
        netlist_path = native_path.parent / "netlist.xml"
        netlist_path.write_text(
            '<export><components><comp ref="TP1"><value>TestPoint</value>'
            "<footprint>TestPoint:TestPoint_Pad_D1.0mm</footprint>"
            '<libsource lib="TestPoint" part="TestPoint"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units>'
            '</comp></components><libparts><libpart lib="TestPoint" part="TestPoint">'
            '<pins><pin num="1" name="TestPoint" type="passive"/></pins>'
            '</libpart></libparts><nets><net name="+3V3"><node ref="TP1" pin="1"/>'
            "</net></nets></export>",
            encoding="utf-8",
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "add",
                board_path.relative_to(self.root).as_posix(),
                contract_path.relative_to(self.root).as_posix(),
            ),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic test fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic PCB test-access requirements",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        summary = read_model(native_path, ValidationSummary)
        current_hashes = hashes(self.root, config.source_roots)
        summary_checks = dict(summary.checks)
        for check_id in ("source_scope", "source_unchanged"):
            summary_checks[check_id] = summary_checks[check_id].model_copy(
                update={"source_hashes": current_hashes}
            )
        write_model(
            native_path,
            summary.model_copy(
                update={
                    "checked_commit": self.source.commit,
                    "source": self.source,
                    "checks": summary_checks,
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist_path),
                    },
                }
            ),
        )
        self.native = reference(self.root, native_path)
        self.output = self.root / "build/electrical/pcb-access-replay"
        connectivity_output = self.output / "pcb-connectivity"

        def fake_native_probe(root: Path, argv: tuple[str, ...], timeout: int):
            self.assertEqual(root, self.root.resolve())
            self.assertEqual(timeout, 600)
            request_path = connectivity_output / "access-probe-requests.json"
            requests = read_model(request_path, PcbAccessProbeRequestSet)
            self.assertEqual(len(requests.requests), 1)
            board_hash = digest(board_path)
            (connectivity_output / "snapshot.json").write_text(
                json.dumps(
                    {
                        "schema_version": "4",
                        "board_sha256": board_hash,
                        "kicad_version": config.kicad_version,
                        "zones_refilled": True,
                        "pads": [
                            {
                                "pad": "TP1.1",
                                "net": "+3V3",
                                "footprint": "TestPoint:TestPoint_Pad_D1.0mm",
                                "dnp": False,
                                "connected_pads": ["TP1.1"],
                                "connected_vias": [],
                                "connected_zones": [],
                                "connected_islands": [],
                            },
                            {
                                "pad": "TP2.1",
                                "net": "OTHER",
                                "footprint": "Synthetic:Obstacle",
                                "dnp": False,
                                "connected_pads": ["TP2.1"],
                                "connected_vias": [],
                                "connected_zones": [],
                                "connected_islands": [],
                            },
                        ],
                        "vias": [],
                        "net_ties": [],
                        "zones": [],
                        "access_probe_observations": [
                            {
                                "endpoint": "TP1.1",
                                "side": "front",
                                "target_net": "+3V3",
                                "target_exposed": True,
                                "obstacle": "TP2.1",
                                "obstacle_net": "OTHER",
                                "distance_nm": 500000,
                                "target_aperture_shape": "circle",
                                "target_aperture_diameter_nm": 1000000,
                            }
                        ],
                        "access_probe_requests_sha256": digest(request_path),
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            return CommandEvidence(
                argv=argv,
                started_utc=datetime.now(UTC).isoformat(),
                returncode=0,
            )

        with patch(
            "kicad_tooling.hwrepo.pcb_return_paths.run_command",
            side_effect=fake_native_probe,
        ):
            report = analyze(
                self.root,
                PROJECT,
                self.output,
                native_summary=native_path,
                ngspice=str(self.simulator),
            )
        self.assertEqual(report.status, "PASS", report)
        rows = {row.id: row for row in report.checks}
        self.assertEqual(rows["test-access/schematic/logic-rail"].status, "PASS")
        self.assertEqual(rows["test-access/pcb-accessibility/logic-rail"].status, "PASS")
        self.assertEqual(rows["test-access/pcb-probe-envelope/logic-rail"].status, "PASS")
        self.path = self.output / "electrical.json"
        self.verify()
        request_path = self.output / "pcb-connectivity/access-probe-requests.json"
        snapshot_path = self.output / "pcb-connectivity/snapshot.json"
        saved_request = request_path.read_bytes()
        saved_snapshot = snapshot_path.read_bytes()
        saved_report = self.path.read_bytes()
        tampered_request = json.loads(saved_request)
        tampered_request["requests"][0]["net"] = "OTHER"
        request_path.write_text(json.dumps(tampered_request), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/access-probe-requests.json"] = digest(
            request_path
        )
        self.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "requests differ from current requirements"):
            self.verify()
        request_path.write_bytes(saved_request)
        self.path.write_bytes(saved_report)

        tampered_snapshot = json.loads(saved_snapshot)
        tampered_snapshot["access_probe_observations"][0]["distance_nm"] = 499999
        snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        self.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Retained electrical checks fail or omit"):
            self.verify()
        snapshot_path.write_bytes(saved_snapshot)
        self.path.write_bytes(saved_report)
        self.verify()

        tampered_snapshot = json.loads(saved_snapshot)
        tampered_snapshot["access_probe_observations"][0]["target_aperture_diameter_nm"] = 999999
        snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        self.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Retained electrical checks fail or omit"):
            self.verify()
        snapshot_path.write_bytes(saved_snapshot)
        self.path.write_bytes(saved_report)
        self.verify()
        board_path.write_text(board_path.read_text().replace('"F.Mask"', '"F.Paste"'))
        with self.assertRaisesRegex(ValueError, "inputs differ"):
            self.verify()

    def test_saved_pin_bus_serial_rs485_and_power_maps_are_rechecked_and_cannot_be_omitted(
        self,
    ) -> None:
        requirement = PinConnectivityAnalysis(
            basis="Synthetic independently reviewed pin relationship",
            rules=(
                PinRelationshipRule(
                    id="shared-source",
                    basis="Two selected pins share the synthetic source net",
                    topology="common_net",
                    pins=("R1.1", "R3.1"),
                    net="PILOT_A",
                ),
            ),
        )
        write_model(
            self.root / ISLAND / "tests/electrical.json",
            self.contract.model_copy(
                update={
                    "pin_connectivity": requirement,
                    "i2c_pullups": i2c_pullup_window_requirement(
                        "R4",
                        "R5",
                        maximum_per_resistor_tolerance_percent=5.0,
                        resistor_tolerance_basis=(
                            "Synthetic maximum tolerance bound for each series pull-up resistor"
                        ),
                    ),
                    "can_termination": can_split_termination_requirement("R7", "R8"),
                    "usb_c": usb_c_requirement(
                        connector="J9",
                        board_component="U9",
                        protection_reference="D9",
                        resistor_references=("R9", "R10"),
                        vbus_path=True,
                    ),
                    "spi": spi_requirement(
                        device2_miso="not_present",
                        controller_reference="U10",
                        device_references=("U11", "U12"),
                        device2_symbol="Synthetic:SpiWriteOnly",
                    ),
                    "serial_peers": serial_peer_requirement(
                        endpoint_reference="U30", peer_reference="U31"
                    ),
                    "rs485": rs485_requirement(),
                    "control_inputs": ControlInputsAnalysis(
                        basis="Synthetic control-signal requirements",
                        signals=(
                            ControlSignalRequirement(
                                id="factory-reset",
                                basis="Synthetic controller reset input and one approved driver",
                                signal_net="RESET_TEST",
                                driver_policy="single",
                                endpoints=(
                                    ControlPinRequirement(
                                        role="controlled_input",
                                        reference="U50",
                                        symbol="Synthetic:ControlInput",
                                        footprint="Package_QFN:QFN-16",
                                        pin="U50.1",
                                        electrical_type="input",
                                    ),
                                    ControlPinRequirement(
                                        role="approved_driver",
                                        reference="U51",
                                        symbol="Synthetic:ControlOutput",
                                        footprint="Package_SO:SOIC-8",
                                        pin="U51.1",
                                        electrical_type="output",
                                    ),
                                    ControlPinRequirement(
                                        role="external_interface",
                                        reference="J50",
                                        symbol="Synthetic:ControlHeader",
                                        footprint="Connector:Dsub-9_Male",
                                        pin="J50.9",
                                        electrical_type="passive",
                                    ),
                                ),
                                bias=ControlLocalBiasRequirement(
                                    mode="local",
                                    basis="Synthetic 10 kΩ reset pull-up requirement",
                                    resistors=(
                                        ControlBiasResistorRequirement(
                                            reference="R50",
                                            symbol="Device:R",
                                            footprint="Resistor_SMD:R_0603_1608Metric",
                                            signal_net="RESET_TEST",
                                            bias_net="+3V3",
                                            direction="pull_up",
                                            minimum_ohms=9_000,
                                            maximum_ohms=11_000,
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    "power_connectivity": power_connectivity_requirement(),
                }
            ),
        )
        native_directory = self.root / "build/native/controller"
        netlist = native_directory / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="R1"><value>1k</value></comp>'
            '<comp ref="R3"><value>3k</value></comp>'
            '<comp ref="U1"><value>I2C target</value><footprint>Synthetic:SOIC8</footprint>'
            '<libsource lib="Synthetic" part="I2cTarget"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R4"><value>1k</value><footprint>Synthetic:R</footprint>'
            '<libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R5"><value>3.7k</value><footprint>Synthetic:R</footprint>'
            '<libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R6"><value>4.7k</value></comp>'
            '<comp ref="U2"><value>CAN transceiver</value>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R7"><value>60R</value></comp>'
            '<comp ref="R8"><value>60R</value></comp>'
            '<comp ref="C1"><value>100pF</value><footprint>Synthetic:CAP</footprint>'
            '<libsource lib="Synthetic" part="CanMidpointCapacitor"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="J9"><value>USB-C receptacle</value>'
            '<libsource lib="Synthetic" part="UsbCReceptacle"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/></pins></unit></units></comp>'
            '<comp ref="U9"><value>System connector</value>'
            '<libsource lib="Synthetic" part="SystemConnector"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="5"/></pins></unit></units>'
            "</comp>"
            '<comp ref="D9"><value>USB protection</value><footprint>Package_DFN:DFN-6</footprint>'
            '<libsource lib="Synthetic" part="UsbProtection"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R9"><value>56k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R10"><value>56k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="U10"><value>Synthetic SPI controller</value>'
            "<footprint>Package_QFP:LQFP-32</footprint>"
            '<libsource lib="Synthetic" part="SpiController"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/></pins></unit></units></comp>'
            '<comp ref="U11"><value>Synthetic SPI peripheral</value>'
            "<footprint>Package_SO:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="SpiPeripheral"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/></pins></unit></units></comp>'
            '<comp ref="U12"><value>Synthetic write-only peripheral</value>'
            "<footprint>Package_SO:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="SpiWriteOnly"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="4"/>'
            "</pins></unit></units></comp>"
            '<comp ref="U30"><value>Synthetic UART endpoint A</value>'
            "<footprint>Connector_Generic:Conn_01x03</footprint>"
            '<libsource lib="Synthetic" part="UartEndpoint"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            "</pins></unit></units></comp>"
            '<comp ref="U31"><value>Synthetic UART endpoint B</value>'
            "<footprint>Connector_Generic:Conn_01x03</footprint>"
            '<libsource lib="Synthetic" part="UartEndpoint"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            "</pins></unit></units></comp>"
            '<comp ref="U20"><value>Synthetic RS-485 transceiver</value>'
            "<footprint>Package_SO:SOIC-16</footprint>"
            '<libsource lib="Synthetic" part="Rs485Transceiver"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/><pin num="6"/><pin num="7"/><pin num="8"/>'
            '<pin num="9"/></pins></unit></units></comp>'
            '<comp ref="J20"><value>Synthetic RS-485 connector</value>'
            "<footprint>Connector_Generic:Conn_01x09</footprint>"
            '<libsource lib="Synthetic" part="Rs485Connector"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/><pin num="6"/><pin num="7"/><pin num="8"/>'
            '<pin num="9"/></pins></unit></units></comp>'
            '<comp ref="R20"><value>120R</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint>'
            '<libsource lib="Device" part="R"/><units><unit name="A"><pins><pin num="1"/>'
            '<pin num="2"/></pins></unit></units></comp>'
            '<comp ref="R21"><value>680R</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint>'
            '<libsource lib="Device" part="R"/><units><unit name="A"><pins><pin num="1"/>'
            '<pin num="2"/></pins></unit></units></comp>'
            '<comp ref="R22"><value>680R</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint>'
            '<libsource lib="Device" part="R"/><units><unit name="A"><pins><pin num="1"/>'
            '<pin num="2"/></pins></unit></units></comp>'
            '<comp ref="J40"><value>Synthetic barrel input</value>'
            "<footprint>Connector_BarrelJack:BarrelJack_Horizontal</footprint>"
            '<libsource lib="Synthetic" part="PowerInput"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="J41"><value>Synthetic terminal input</value>'
            "<footprint>Connector_Generic:Conn_01x02</footprint>"
            '<libsource lib="Synthetic" part="PowerInput"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="U40"><value>Synthetic regulator</value><footprint>Package_SO:SOIC-8</footprint>'
            '<libsource lib="Synthetic" part="PowerRegulator"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="U41"><value>Synthetic monitor</value><footprint>Package_SOT:SOT-23-5</footprint>'
            '<libsource lib="Synthetic" part="VoltageMonitor"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="U50"><value>Synthetic control input</value><footprint>Package_QFN:QFN-16</footprint>'
            '<libsource lib="Synthetic" part="ControlInput"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="U51"><value>Synthetic control output</value><footprint>Package_SO:SOIC-8</footprint>'
            '<libsource lib="Synthetic" part="ControlOutput"/>'
            '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
            '<comp ref="J50"><value>Synthetic control header</value><footprint>Connector:Dsub-9_Male</footprint>'
            '<libsource lib="Synthetic" part="ControlHeader"/>'
            '<units><unit name="A"><pins><pin num="9"/></pins></unit></units></comp>'
            '<comp ref="R50"><value>10k</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint>'
            '<libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="ControlInput"><pins>'
            '<pin num="1" name="RESET_N" type="input"/></pins></libpart>'
            '<libpart lib="Synthetic" part="ControlOutput"><pins>'
            '<pin num="1" name="RESET_N" type="output"/></pins></libpart>'
            '<libpart lib="Synthetic" part="ControlHeader"><pins>'
            '<pin num="9" name="RESET" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="CanMidpointCapacitor"><pins>'
            '<pin num="1" name="MIDPOINT" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/></pins></libpart>'
            '<libpart lib="Device" part="R"><pins>'
            '<pin num="1" name="1" type="passive"/><pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="PILOT_A"><node ref="R1" pin="1"/><node ref="R3" pin="1"/></net>'
            '<net name="PILOT_C"><node ref="R1" pin="2"/><node ref="R3" pin="2"/></net>'
            '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="R4" pin="1"/></net>'
            '<net name="I2C_SDA_CHAIN"><node ref="R4" pin="2"/><node ref="R5" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="R6" pin="1"/></net>'
            '<net name="+3V3"><node ref="R5" pin="2"/><node ref="R6" pin="2"/>'
            '<node ref="R50" pin="2"/></net>'
            '<net name="CAN_H"><node ref="U2" pin="1"/><node ref="R7" pin="1"/></net>'
            '<net name="CAN_L"><node ref="U2" pin="2"/><node ref="R8" pin="1"/></net>'
            '<net name="CAN_TERM_MID"><node ref="R7" pin="2"/><node ref="R8" pin="2"/>'
            '<node ref="C1" pin="1"/></net>'
            '<net name="CC1"><node ref="J9" pin="4"/><node ref="D9" pin="1"/>'
            '<node ref="R9" pin="1"/></net>'
            '<net name="CC2"><node ref="J9" pin="5"/><node ref="R10" pin="1"/></net>'
            '<net name="VBUS_PORT"><node ref="J9" pin="1"/></net>'
            '<net name="VBUS_SYSTEM"><node ref="U9" pin="1"/></net>'
            '<net name="GND"><node ref="J9" pin="2"/><node ref="J9" pin="3"/>'
            '<node ref="U9" pin="5"/><node ref="D9" pin="2"/>'
            '<node ref="U30" pin="3"/><node ref="U31" pin="3"/>'
            '<node ref="C1" pin="2"/></net>'
            '<net name="+5V"><node ref="R9" pin="2"/><node ref="R10" pin="2"/></net>'
            '<net name="SPI_SCK"><node ref="U10" pin="1"/><node ref="U11" pin="1"/>'
            '<node ref="U12" pin="1"/></net>'
            '<net name="SPI_MOSI"><node ref="U10" pin="2"/><node ref="U11" pin="2"/>'
            '<node ref="U12" pin="2"/></net>'
            '<net name="SPI_MISO"><node ref="U10" pin="3"/><node ref="U11" pin="3"/></net>'
            '<net name="SPI_CS0"><node ref="U10" pin="4"/><node ref="U11" pin="4"/></net>'
            '<net name="SPI_CS1"><node ref="U10" pin="5"/><node ref="U12" pin="4"/></net>'
            '<net name="UART_TX"><node ref="U30" pin="1"/><node ref="U31" pin="2"/>'
            '<node ref="U20" pin="5"/></net>'
            '<net name="UART_RX"><node ref="U30" pin="2"/><node ref="U31" pin="1"/>'
            '<node ref="U20" pin="6"/></net>'
            '<net name="485_LINE_1"><node ref="U20" pin="1"/><node ref="J20" pin="1"/>'
            '<node ref="R20" pin="1"/><node ref="R21" pin="1"/></net>'
            '<net name="485_LINE_2"><node ref="U20" pin="2"/><node ref="J20" pin="2"/>'
            '<node ref="R20" pin="2"/><node ref="R22" pin="1"/></net>'
            '<net name="BUS_DIR"><node ref="U20" pin="7"/><node ref="U20" pin="8"/></net>'
            '<net name="GND_BUS"><node ref="U20" pin="9"/><node ref="J20" pin="9"/>'
            '<node ref="R22" pin="2"/></net>'
            '<net name="+5V_BIAS"><node ref="R21" pin="2"/></net>'
            '<net name="VIN_IN"><node ref="J40" pin="1"/><node ref="J41" pin="1"/>'
            '<node ref="U40" pin="1"/><node ref="U41" pin="1"/></net>'
            '<net name="RESET_TEST"><node ref="U50" pin="1"/><node ref="U51" pin="1"/>'
            '<node ref="J50" pin="9"/><node ref="R50" pin="1"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        tree = ET.parse(netlist)
        root = tree.getroot()
        components = root.find("components")
        libparts = root.find("libparts")
        nets = root.find("nets")
        self.assertIsNotNone(components)
        self.assertIsNotNone(libparts)
        self.assertIsNotNone(nets)
        assert components is not None and libparts is not None and nets is not None

        def add_component(
            reference: str,
            value: str,
            footprint: str,
            library: str,
            part: str,
            pin_numbers: tuple[str, ...],
        ) -> None:
            entry = ET.SubElement(components, "comp", ref=reference)
            ET.SubElement(entry, "value").text = value
            ET.SubElement(entry, "footprint").text = footprint
            ET.SubElement(entry, "libsource", lib=library, part=part)
            units = ET.SubElement(entry, "units")
            unit = ET.SubElement(units, "unit", name="A")
            pins = ET.SubElement(unit, "pins")
            for number in pin_numbers:
                ET.SubElement(pins, "pin", num=number)

        def add_libpart(library: str, part: str, pins_by_number: dict[str, str]) -> None:
            libpart = ET.SubElement(libparts, "libpart", lib=library, part=part)
            pins = ET.SubElement(libpart, "pins")
            for number, name in pins_by_number.items():
                ET.SubElement(pins, "pin", num=number, name=name, type="passive")

        def append_net_nodes(name: str, assignments: tuple[tuple[str, str], ...]) -> None:
            net = next((item for item in nets.findall("net") if item.get("name") == name), None)
            if net is None:
                net = ET.SubElement(nets, "net", name=name)
            for component_ref, number in assignments:
                ET.SubElement(net, "node", ref=component_ref, pin=number)

        add_component(
            "F1",
            "PTC fuse",
            "Fuse:Fuse_1206_3216Metric",
            "Device",
            "Fuse",
            ("1", "2"),
        )
        add_component(
            "U3",
            "Synthetic load switch",
            "Package_DFN:DFN-6",
            "Synthetic",
            "LoadSwitch",
            ("1", "2", "3", "4", "5", "6"),
        )
        add_libpart("Device", "Fuse", {"1": "1", "2": "2"})
        add_libpart(
            "Synthetic",
            "LoadSwitch",
            {"1": "VIN", "2": "VIN_ALT", "3": "VOUT", "4": "EN", "5": "NC1", "6": "NC2"},
        )
        append_net_nodes("VBUS_PORT", (("F1", "1"),))
        append_net_nodes("VBUS_FUSED", (("F1", "2"), ("U3", "1"), ("U3", "2")))
        append_net_nodes("VBUS_SYSTEM", (("U3", "3"),))
        append_net_nodes("SWITCH_ENABLE", (("U3", "4"),))
        netlist.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
        summary_path = native_directory / "summary.json"
        summary = read_model(summary_path, ValidationSummary)
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, summary_path)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qam",
                "Synthetic pin relationship",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        self.output = self.root / "build/electrical/pin-relationship"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=summary_path,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        self.path = self.output / "electrical.json"
        self.verify()
        report = read_model(self.path, ElectricalAnalysisReport)
        checks = {item.id: item for item in report.checks}
        self.assertEqual(checks["can-termination/fieldbus/local"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local/midpoint-capacitor"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/vbus-path/input-path"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/series-bus/sda/voltage-compatibility"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/series-bus/scl/voltage-compatibility"].status, "PASS")
        self.assertEqual(
            checks["i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance"].status,
            "PASS",
        )
        self.assertEqual(
            checks["i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance"].status,
            "PASS",
        )
        for omitted in (
            "pin-connectivity/shared-source",
            "i2c-pullup/series-bus/sda/series/sda-chain",
            "i2c-pullup/series-bus/sda",
            "i2c-pullup/series-bus/sda/voltage-compatibility",
            "i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance",
            "i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance",
            "i2c-pullup/series-bus/scl/voltage-compatibility",
            "i2c-pullup/series-bus/scl/electrical-window/minimum-sink-resistance",
            "i2c-pullup/series-bus/scl/electrical-window/maximum-rise-resistance",
            "can-termination/fieldbus/local",
            "can-termination/fieldbus/local/midpoint-capacitor",
            "usb-c/host-port/connector-pins",
            "usb-c/host-port/cc1-attachment",
            "usb-c/host-port/vbus-path/input-path",
            "usb-c/host-port/protection/D9",
            "spi/control/device/sensor/route/sck",
            "spi/control/device/memory/route/miso",
            "serial/console-link/route/a_tx_to_b_rx",
            "rs485/fieldbus/pair/shared/membership",
            "rs485/fieldbus/pair/shared/termination/local-end",
            "rs485/fieldbus/pair/shared/bias",
            "control-inputs/factory-reset/endpoints",
            "control-inputs/factory-reset/drivers",
            "control-inputs/factory-reset/bias",
            "power-connectivity/supply/source/approved-inputs",
            "power-connectivity/supply/load/load",
        ):
            with self.subTest(omitted=omitted):
                write_model(
                    self.path,
                    report.model_copy(
                        update={"checks": tuple(row for row in report.checks if row.id != omitted)}
                    ),
                )
                with self.assertRaisesRegex(ValueError, "checks fail or omit"):
                    self.verify()

    def test_relabeling_and_rehashing_cannot_hide_missing_or_failed_measurements(self) -> None:
        original = self.path.read_bytes()
        for change in ("checks", "commands", "inventory", "source", "project", "inputs"):
            with self.subTest(change=change):
                value = json.loads(original)
                if change == "checks":
                    value["checks"] = []
                elif change == "commands":
                    value["commands"].pop("startup")
                elif change == "inventory":
                    value["artifacts_sha256"].pop("startup/waveforms.raw")
                elif change == "source":
                    value["source"] = None
                elif change == "project":
                    value["project_id"] = "another-board"
                else:
                    value["input_sha256"] = {}
                self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    self.verify()
        self.path.write_bytes(original)
        command = self.output / "startup/ngspice.command.json"
        value = json.loads(command.read_text())
        value["stdout"] = "check0 = 9000\n"
        command.write_text(json.dumps(value))
        report = json.loads(original)
        report["commands"]["startup"] = value
        report["artifacts_sha256"]["startup/ngspice.command.json"] = digest(command)
        self.path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "checks fail"):
            self.verify()

    def test_changed_model_waveform_or_case_deck_cannot_reuse_receipt(self) -> None:
        for name in ("startup/waveforms.raw", "startup/simulation.cir"):
            path = self.output / name
            original = path.read_bytes()
            path.write_bytes(original + b"\nchanged")
            with self.assertRaises(ValueError):
                self.verify()
            path.write_bytes(original)
        model = self.root / ISLAND / "tests/electrical/startup.cir"
        model.write_bytes(model.read_bytes() + b"\n* changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.verify()

    def test_declared_contracts_gate_review_and_build_releases_require_applicability(self) -> None:
        projects = tuple(p for p in load_registry(self.root).projects if p.id == PROJECT)
        self.assertEqual(
            required_projects(self.root, projects, ReleaseClass.ENGINEERING_REVIEW), (PROJECT,)
        )
        path = self.root / ISLAND / "tests/contract.json"
        value = json.loads(path.read_text())
        value.pop("electrical")
        path.write_text(json.dumps(value))
        self.assertEqual(
            required_projects(self.root, projects, ReleaseClass.ENGINEERING_REVIEW), ()
        )
        with self.assertRaisesRegex(ValueError, "build releases require"):
            required_projects(self.root, projects, ReleaseClass.PROTOTYPE)

    def test_all_not_applicable_still_requires_bound_evidence(self) -> None:
        path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(path, ElectricalAnalysisContract).model_copy(update={"power": NA})
        write_model(path, contract)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qam",
                "Synthetic applicability",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        self.output = self.root / "build/electrical/not-applicable"
        result = analyze(self.root, PROJECT, self.output, ngspice="missing-simulator")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.commands, {})
        self.path = self.output / "electrical.json"
        self.verify()

    def test_digital_peer_voltage_result_replays_from_bound_native_netlist(self) -> None:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"digital_peer_voltages": digital_peer_requirement()}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic direct digital peer requirements",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(digital_peer_netlist_xml(), encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical/digital-peer-replay"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        checks = {item.id: item for item in result.checks}
        self.assertEqual(checks["digital-peer-voltage/spi-mosi/compatibility"].status, "PASS")
        self.path = self.output / "electrical.json"
        self.verify()

    def test_component_voltage_rating_result_replays_from_bound_native_netlist(self) -> None:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"component_voltage_ratings": component_voltage_requirement()}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic component voltage-rating requirement",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(component_voltage_netlist_xml(), encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical/component-voltage-rating-replay"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        checks = {item.id: item for item in result.checks}
        self.assertEqual(
            checks["component-voltage-rating/input-capacitor/utilization"].status,
            "PASS",
        )
        self.path = self.output / "electrical.json"
        self.verify()
        saved_report = self.path.read_bytes()
        report = read_model(self.path, ElectricalAnalysisReport)
        for omitted in (
            "component-voltage-rating/input-capacitor/identity",
            "component-voltage-rating/input-capacitor/pin-1",
            "component-voltage-rating/input-capacitor/pin-2",
            "component-voltage-rating/input-capacitor/utilization",
        ):
            with self.subTest(omitted=omitted):
                write_model(
                    self.path,
                    report.model_copy(
                        update={
                            "checks": tuple(item for item in report.checks if item.id != omitted)
                        }
                    ),
                )
                with self.assertRaisesRegex(ValueError, "checks fail or omit"):
                    self.verify()
        self.path.write_bytes(saved_report)
        self.verify()

    def test_component_power_rating_result_replays_from_bound_native_netlist(self) -> None:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"component_power_ratings": component_power_requirement()}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic component power-rating requirement",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(component_power_netlist_xml(), encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical/component-power-rating-replay"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        checks = {item.id: item for item in result.checks}
        self.assertEqual(
            checks["component-power-rating/sense-resistor/utilization"].status,
            "PASS",
        )
        self.path = self.output / "electrical.json"
        self.verify()
        saved_report = self.path.read_bytes()
        report = read_model(self.path, ElectricalAnalysisReport)
        for omitted in (
            "component-power-rating/sense-resistor/identity",
            "component-power-rating/sense-resistor/pin-1",
            "component-power-rating/sense-resistor/pin-2",
            "component-power-rating/sense-resistor/utilization",
        ):
            with self.subTest(omitted=omitted):
                write_model(
                    self.path,
                    report.model_copy(
                        update={
                            "checks": tuple(item for item in report.checks if item.id != omitted)
                        }
                    ),
                )
                with self.assertRaisesRegex(ValueError, "checks fail or omit"):
                    self.verify()
        self.path.write_bytes(saved_report)
        self.verify()

    def test_connector_contact_rating_result_replays_from_bound_native_netlist(self) -> None:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"connector_contact_ratings": connector_contact_requirement()}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic connector contact-rating requirement",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(connector_contact_netlist_xml(), encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical/connector-contact-rating-replay"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        check_id = "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
        checks = {item.id: item for item in result.checks}
        self.assertEqual(checks[check_id].status, "PASS")
        self.path = self.output / "electrical.json"
        self.verify()
        saved_report = self.path.read_bytes()
        report = read_model(self.path, ElectricalAnalysisReport)
        for omitted in (
            "connector-contact-rating/host-connector/identity",
            "connector-contact-rating/host-connector/contact-vbus-contact/assignment",
            check_id,
        ):
            with self.subTest(omitted=omitted):
                write_model(
                    self.path,
                    report.model_copy(
                        update={
                            "checks": tuple(item for item in report.checks if item.id != omitted)
                        }
                    ),
                )
                with self.assertRaisesRegex(ValueError, "checks fail or omit"):
                    self.verify()
        self.path.write_bytes(saved_report)
        self.verify()

    def test_mosfet_stress_result_replays_and_rejects_omitted_state_checks(self) -> None:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"mosfet_stress": mosfet_stress_requirement()}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic MOSFET state-stress requirement",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)
        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(mosfet_stress_netlist_xml(), encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical/mosfet-stress-replay"
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        self.assertEqual(result.status, "PASS", result)
        checks = {item.id: item for item in result.checks}
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vds"].status, "PASS")
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vgs"].status, "PASS")
        self.path = self.output / "electrical.json"
        self.verify()

        saved_report = self.path.read_bytes()
        report = read_model(self.path, ElectricalAnalysisReport)
        for omitted in (
            "mosfet-stress/switch-q1/identity",
            "mosfet-stress/switch-q1/pin-drain",
            "mosfet-stress/switch-q1/state-on/coverage",
            "mosfet-stress/switch-q1/state-on/vds",
            "mosfet-stress/switch-q1/state-on/vgs",
        ):
            with self.subTest(omitted=omitted):
                write_model(
                    self.path,
                    report.model_copy(
                        update={
                            "checks": tuple(item for item in report.checks if item.id != omitted)
                        }
                    ),
                )
                with self.assertRaisesRegex(ValueError, "checks fail or omit"):
                    self.verify()
        self.path.write_bytes(saved_report)
        self.verify()


if __name__ == "__main__":
    unittest.main()
