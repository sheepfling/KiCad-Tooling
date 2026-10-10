"""Hosted native test-point probe-envelope fixture lane."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def pcb_access_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise native pad exposure and probe-envelope evidence on a synthetic PCB."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        PcbAccessAnalysis,
        PcbAccessProbeObservation,
        RequiredTestAccess,
        TestAccessAnalysis,
        TestAccessEndpointRequirement,
        TestAccessProbeEnvelope,
    )
    from .hwrepo.pcb_return_path_capture import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )
    from .hwrepo.test_access import (
        pcb_access_probe_request_set,
        pcb_probe_envelope_checks,
    )

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB probe-envelope native fixtures do not cover KiCad {config.kicad_version}"
        )

    def endpoint(
        reference: str,
        net: str,
        *,
        approach_side: Literal["front", "back", "either"],
        tip_diameter_mm: float,
        clearance_mm: float,
    ) -> TestAccessEndpointRequirement:
        return TestAccessEndpointRequirement(
            kind="test_point",
            reference=reference,
            symbol="Synthetic:AccessTarget",
            footprint="Synthetic:AccessTarget",
            pin=f"{reference}.1",
            electrical_type="passive",
            approach_side=approach_side,
            probe_envelope=TestAccessProbeEnvelope(
                tip_diameter_mm=tip_diameter_mm,
                clearance_mm=clearance_mm,
            ),
        )

    spec = TestAccessAnalysis(
        basis="Synthetic native PCB probe-envelope regression fixture",
        pcb_accessibility=PcbAccessAnalysis(
            basis="Synthetic native API fixture checks pad surface geometry only"
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="front-back-boundary",
                basis="Synthetic either-side envelope uses one passing surface",
                net="TARGET_ACCESS",
                endpoints=(
                    endpoint(
                        "J1",
                        "TARGET_ACCESS",
                        approach_side="either",
                        tip_diameter_mm=0.8,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="unconnected-obstacle",
                basis="Synthetic no-net pad remains an observed obstacle",
                net="TARGET_NO_NET_NEIGHBOR",
                endpoints=(
                    endpoint(
                        "J7",
                        "TARGET_NO_NET_NEIGHBOR",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="front-only-clearance-fault",
                basis="Synthetic one-sided access cannot pass using an unavailable side",
                net="TARGET_FRONT_ONLY",
                endpoints=(
                    endpoint(
                        "J9",
                        "TARGET_FRONT_ONLY",
                        approach_side="either",
                        tip_diameter_mm=0.8,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="undersize-aperture-fault",
                basis="Synthetic circular aperture is smaller than the declared probe tip envelope",
                net="TARGET_APERTURE_SMALL",
                endpoints=(
                    endpoint(
                        "J11",
                        "TARGET_APERTURE_SMALL",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="aperture-fit-boundary-control",
                basis="Synthetic aperture exactly matches the declared tip-plus-clearance diameter",
                net="TARGET_APERTURE_BOUNDARY",
                endpoints=(
                    endpoint(
                        "J12",
                        "TARGET_APERTURE_BOUNDARY",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="rectangular-aperture-unsupported",
                basis="Synthetic rectangular target stays outside the circular fit predicate",
                net="TARGET_APERTURE_RECT",
                endpoints=(
                    endpoint(
                        "J13",
                        "TARGET_APERTURE_RECT",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
            RequiredTestAccess(
                mode="required",
                id="drilled-aperture-unsupported",
                basis="Synthetic drilled target stays outside the circular fit predicate",
                net="TARGET_APERTURE_DRILLED",
                endpoints=(
                    endpoint(
                        "J14",
                        "TARGET_APERTURE_DRILLED",
                        approach_side="front",
                        tip_diameter_mm=0.6,
                        clearance_mm=0.1,
                    ),
                ),
            ),
        ),
    )
    requests = pcb_access_probe_request_set(spec)
    if requests is None:
        raise ValueError("Synthetic PCB access fixture produced no native probe requests")

    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(tempfile.mkdtemp(prefix=f"pcb-access-{project}-", dir=log.directory.resolve()))
    relative_project = scratch.relative_to(root) / "probe-envelope.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-access-probe-envelope.kicad_pcb", board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    expected_statuses = {
        "test-access/pcb-probe-envelope/front-back-boundary": "PASS",
        "test-access/pcb-probe-envelope/unconnected-obstacle": "PASS",
        "test-access/pcb-probe-envelope/front-only-clearance-fault": "FAIL",
        "test-access/pcb-probe-envelope/undersize-aperture-fault": "FAIL",
        "test-access/pcb-probe-envelope/aperture-fit-boundary-control": "PASS",
        "test-access/pcb-probe-envelope/rectangular-aperture-unsupported": "FAIL",
        "test-access/pcb-probe-envelope/drilled-aperture-unsupported": "FAIL",
    }
    expected_observations = {
        ("j1.1", "front"): ("J4.1", "FOREIGN_FRONT", 400_000, True, "circle", 1_200_000),
        ("j1.1", "back"): ("J5.1", "FOREIGN_BACK", 800_000, True, "circle", 1_200_000),
        ("j7.1", "front"): ("J8.1", None, 400_000, True, "circle", 800_000),
        ("j9.1", "front"): (
            "J10.1",
            "FOREIGN_FRONT_ONLY",
            400_000,
            True,
            "circle",
            300_000,
        ),
        ("j9.1", "back"): (None, None, None, False, None, None),
        ("j11.1", "front"): (
            "J12.1",
            "TARGET_APERTURE_BOUNDARY",
            9_500_001,
            True,
            "circle",
            400_000,
        ),
        ("j12.1", "front"): (
            "J13.1",
            "TARGET_APERTURE_RECT",
            9_500_000,
            True,
            "circle",
            800_000,
        ),
        ("j13.1", "front"): (
            "J12.1",
            "TARGET_APERTURE_BOUNDARY",
            9_500_001,
            True,
            "unsupported",
            None,
        ),
        ("j14.1", "front"): (
            "J13.1",
            "TARGET_APERTURE_RECT",
            9_500_000,
            True,
            "unsupported",
            None,
        ),
    }
    try:
        retained_observations: tuple[PcbAccessProbeObservation, ...] | None = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"receipt-{repeat}"
            command, snapshot = capture_native_pcb_connectivity(
                root, fixture_config, receipt, requests
            )
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB access fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config, access_probes=True):
                raise ValueError(
                    "Native access fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB access fixture returned no connectivity snapshot")
            request_path = receipt / "access-probe-requests.json"
            if (
                snapshot.board_sha256 != source_hash
                or snapshot.kicad_version != config.kicad_version
                or snapshot.image != config.image
                or snapshot.probe_sha256 != expected_probe_sha256()
                or snapshot.access_probe_requests_sha256 != digest(request_path)
                or not snapshot.zones_refilled
            ):
                raise ValueError("Native access fixture evidence is not bound to its exact inputs")

            observations = {
                (item.endpoint.casefold(), item.side): item
                for item in snapshot.access_probe_observations
            }
            if len(observations) != len(snapshot.access_probe_observations):
                raise ValueError("Native access fixture returned duplicate endpoint surfaces")
            if set(observations) != set(expected_observations):
                raise ValueError(
                    "Native access fixture surfaces differ from the synthetic request inventory"
                )
            for key, expected in expected_observations.items():
                item = observations[key]
                observed = (
                    item.obstacle,
                    item.obstacle_net,
                    item.distance_nm,
                    item.target_exposed,
                    item.target_aperture_shape,
                    item.target_aperture_diameter_nm,
                )
                if observed != expected:
                    raise ValueError(
                        f"Native probe geometry for {key[0]} {key[1]} differs from its fixture: "
                        f"expected {expected}, found {observed}"
                    )

            checks = {item.id: item.status for item in pcb_probe_envelope_checks(spec, snapshot)}
            if checks != expected_statuses:
                raise ValueError(
                    "Probe-envelope fault/control results differ from the synthetic expectations: "
                    f"expected {expected_statuses}, found {checks}"
                )
            if retained_observations is None:
                retained_observations = snapshot.access_probe_observations
            elif retained_observations != snapshot.access_probe_observations:
                raise ValueError(
                    "Repeated native probe geometry changed for identical board inputs"
                )

        log.event(
            "pcb-access-fixture/probe-envelope",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            checks="3 PASS, 4 expected FAIL",
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-access-fixture/probe-envelope",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            error=str(exc),
        )
        raise
