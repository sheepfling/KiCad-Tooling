"""Focused hosted CI orchestration and PCB fixture schedule regressions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
)
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PcbAccessProbeRequest,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    ProjectConfig,
)
from tests.hosted_ci_support import HostedRepoTestCase

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


class HostedPcbFixtureScheduleTests(HostedRepoTestCase):
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
        from kicad_tooling.hwrepo.pcb_return_path_capture import expected_probe_sha256

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
            "kicad_tooling.hwrepo.pcb_return_path_capture.capture_native_pcb_connectivity",
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
        from kicad_tooling.hwrepo import electrical
        from kicad_tooling.hwrepo import pcb_return_path_capture as pcb_capture

        config = electrical.selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-fixture-version")
        with (
            patch.object(electrical, "selected_config", return_value=unsupported),
            patch.object(pcb_capture, "capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_return_fixture_lane(self.root, project="controller", image=config.image, log=log)
        probe.assert_not_called()

    def test_pcb_access_fixture_rejects_an_untested_kicad_minor_before_native_execution(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_access_fixture_lane
        from kicad_tooling.hwrepo import electrical
        from kicad_tooling.hwrepo import pcb_return_path_capture as pcb_capture

        config = electrical.selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-access-fixture-version")
        with (
            patch.object(electrical, "selected_config", return_value=unsupported),
            patch.object(pcb_capture, "capture_native_pcb_connectivity") as probe,
            self.assertRaisesRegex(ValueError, "do not cover KiCad 10.0.6"),
        ):
            pcb_access_fixture_lane(self.root, project="controller", image=config.image, log=log)
        probe.assert_not_called()

    def test_pcb_switching_loop_fixture_rejects_an_untested_kicad_minor(
        self,
    ) -> None:
        from kicad_tooling.ci_hosted import pcb_switching_loop_fixture_lane
        from kicad_tooling.hwrepo import electrical
        from kicad_tooling.hwrepo import pcb_return_path_capture as pcb_capture

        config = electrical.selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-switching-loop-fixture-version")
        with (
            patch.object(electrical, "selected_config", return_value=unsupported),
            patch.object(pcb_capture, "capture_native_pcb_connectivity") as probe,
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
        from kicad_tooling.hwrepo import electrical
        from kicad_tooling.hwrepo import pcb_return_path_capture as pcb_capture

        config = electrical.selected_config(self.root, "controller")
        unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
        log = HostedLog(self.root, "native-pcb-reference-via-fixture-version")
        with (
            patch.object(electrical, "selected_config", return_value=unsupported),
            patch.object(pcb_capture, "capture_native_pcb_connectivity") as probe,
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
