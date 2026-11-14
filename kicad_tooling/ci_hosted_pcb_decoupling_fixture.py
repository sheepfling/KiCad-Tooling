"""Native geometry regression for mapped PCB decoupling placement."""

from __future__ import annotations

import shutil
from pathlib import Path

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .ci_hosted_support import HostedLog
from .hwrepo.evidence import digest
from .hwrepo.pcb_decoupling import pcb_decoupling_entries
from .hwrepo.pcb_decoupling_models import (
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
)


def decoupling_placement_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check exact pad distances, connected return vias, and a distant-via fault."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="PCB decoupling",
        scratch_prefix="pcb-decoupling",
    )
    root = context.root
    config = context.config
    source = context.fixture_root / "pcb-decoupling-placement.kicad_pcb"
    relative_project = context.scratch.relative_to(root) / "decoupling.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(source, board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    capacitors = (
        PcbDecouplingCapacitor(
            reference="C1",
            footprint="Synthetic:Cap_0603",
            supply_pad="C1.1",
            return_pad="C1.2",
        ),
        PcbDecouplingCapacitor(
            reference="C2",
            footprint="Synthetic:Cap_0603",
            supply_pad="C2.1",
            return_pad="C2.2",
        ),
    )
    requirement = PcbDecouplingRequirement(
        id="synthetic-vdd",
        basis=(
            "Native fault/control fixture; 1000 um is an exact test boundary, "
            "not a design recommendation"
        ),
        ic_reference="U1",
        ic_footprint="Synthetic:IC_QFN",
        supply_pad="U1.1",
        return_pad="U1.2",
        supply_net="VDD",
        return_net="GND",
        capacitors=capacitors,
        selection="any",
        max_distance_um=1000,
        max_return_via_distance_um=1000,
    )
    placement_map = PcbDecouplingMap(
        basis="Synthetic native PCB geometry and connectivity regression",
        requirements=(requirement,),
    )
    try:
        retained_snapshot = None
        for repeat in ("first", "repeat"):
            snapshot = capture_verified_pcb_snapshot(
                context,
                fixture_config,
                context.scratch / f"receipt-{repeat}",
                expected_board_sha256=source_hash,
                purpose="PCB decoupling fixture",
                require_outer_copper=True,
            )
            pads = {item.pad.casefold(): item for item in snapshot.pads}
            vias = {item.id: item for item in snapshot.vias}
            c1_return = pads["c1.2"]
            if len(c1_return.connected_vias) != 2:
                raise ValueError("Native decoupling fixture must connect C1 return to two vias")
            connected_return_via = vias[c1_return.connected_vias[0]]
            via_distance_squared = min(
                (x - connected_return_via.x_nm) ** 2 + (y - connected_return_via.y_nm) ** 2
                for x, y in c1_return.positions_nm
            )
            if via_distance_squared != 1_000_000**2:
                raise ValueError(
                    "Native C1 return-to-connected-via distance changed: "
                    f"squared distance {via_distance_squared} nm^2"
                )
            pads_by_capacitor = {"c1.1": 1_000_000, "c2.1": 15_000_000}
            for reference, expected_distance in pads_by_capacitor.items():
                first = pads["u1.1"].positions_nm
                second = pads[reference].positions_nm
                measured_squared = min(
                    (x1 - x2) ** 2 + (y1 - y2) ** 2 for x1, y1 in first for x2, y2 in second
                )
                if measured_squared != expected_distance**2:
                    raise ValueError(
                        f"Native pad-center distance to {reference} changed: "
                        f"squared distance {measured_squared} nm^2"
                    )
            rotated = pads["c3.1"].positions_nm[0]
            if rotated[0] != 40_000_000 or abs(rotated[1] - 20_000_000) != 1_000_000:
                raise ValueError(f"Rotated footprint pad position is incorrect: {rotated}")
            entries = pcb_decoupling_entries(placement_map, snapshot)
            if (
                len(entries) != 1
                or entries[0].status != "COMPLETE"
                or entries[0].selected_capacitors != ("C1",)
                or tuple(item.distance_nm for item in entries[0].candidates)
                != (1_000_000, 15_000_000)
                or entries[0].max_return_via_distance_um != 1000
                or entries[0].candidates[0].return_via_distance_nm != 1_000_000
                or entries[0].candidates[0].connected_return_via_count != 2
            ):
                raise ValueError(f"Native placement fault/control result changed: {entries}")
            all_entries = pcb_decoupling_entries(
                PcbDecouplingMap(
                    basis=placement_map.basis,
                    requirements=(requirement.model_copy(update={"selection": "all"}),),
                ),
                snapshot,
            )
            if all_entries[0].status != "INCOMPLETE":
                raise ValueError("Native all-candidate control missed the distant capacitor")
            if retained_snapshot is None:
                retained_snapshot = snapshot
            elif retained_snapshot != snapshot:
                raise ValueError("Repeated native pad centers changed for identical board inputs")

        if retained_snapshot is None:
            raise ValueError("Repeated native decoupling capture produced no snapshot")
        surface_map = PcbDecouplingMap(
            basis="Synthetic native outer-copper layer-distance regression",
            requirements=(
                PcbDecouplingRequirement(
                    id="backside-capacitor",
                    basis="Synthetic test-only 1500 um layer-aware center-distance limit",
                    ic_reference="U1",
                    ic_footprint="Synthetic:IC_QFN",
                    supply_pad="U1.1",
                    return_pad="U1.2",
                    supply_net="VDD",
                    return_net="GND",
                    capacitors=(
                        PcbDecouplingCapacitor(
                            reference="C4",
                            footprint="Synthetic:Cap_0603",
                            supply_pad="C4.1",
                            return_pad="C4.2",
                        ),
                    ),
                    selection="any",
                    max_distance_3d_um=1500,
                ),
            ),
        )
        surface_fault_entry = pcb_decoupling_entries(surface_map, retained_snapshot)[0]
        surface_fault_candidate = surface_fault_entry.candidates[0]
        if (
            surface_fault_entry.status != "INCOMPLETE"
            or surface_fault_candidate.distance_nm != 0
            or surface_fault_candidate.distance_3d_nm != 1_600_000
            or (
                surface_fault_candidate.distance_3d_ic_layer,
                surface_fault_candidate.distance_3d_capacitor_layer,
            )
            != ("F.Cu", "B.Cu")
            or retained_snapshot.board_thickness_nm != 1_600_000
        ):
            raise ValueError(
                "Native opposite-side same-XY capacitor did not exceed the 1500 um "
                f"layer-aware screen: {surface_fault_entry}"
            )

        fixture_text = source.read_text(encoding="utf-8")
        backside = '(footprint "Synthetic:Cap_0603" (layer "B.Cu") (at 10 10 0)'
        frontside = '(footprint "Synthetic:Cap_0603" (layer "F.Cu") (at 10 10 0)'
        if fixture_text.count(backside) != 1:
            raise ValueError("Native backside capacitor fixture identity changed")
        control_text = fixture_text.replace(backside, frontside, 1)
        if control_text.count('(layers "B.Cu" "B.Paste" "B.Mask")') != 2:
            raise ValueError("Native backside capacitor pad layer count changed")
        control_text = control_text.replace(
            '(pad "2" smd rect (at 0 -1)', '(pad "2" smd rect (at 0 1)', 1
        ).replace('(layers "B.Cu" "B.Paste" "B.Mask")', '(layers "F.Cu" "F.Paste" "F.Mask")')
        board.write_text(control_text, encoding="utf-8")
        surface_control_hash = digest(board)
        surface_control_snapshot = capture_verified_pcb_snapshot(
            context,
            fixture_config,
            context.scratch / "surface-control-receipt",
            expected_board_sha256=surface_control_hash,
            purpose="PCB decoupling same-side layer control",
            require_outer_copper=True,
        )
        surface_control_entry = pcb_decoupling_entries(surface_map, surface_control_snapshot)[0]
        if (
            surface_control_entry.status != "COMPLETE"
            or surface_control_entry.candidates[0].distance_3d_nm != 0
        ):
            raise ValueError(
                f"Native same-side capacitor control did not pass: {surface_control_entry}"
            )

        if fixture_text.count("(at 12 11)") != 1 or fixture_text.count("(at 10 11)") != 1:
            raise ValueError("Native return-via fixture no longer has its unique test coordinates")
        fault_text = fixture_text.replace("(at 12 11)", "(at 13 11)", 1).replace(
            "(at 10 11)", "(at 9 11)", 1
        )
        board.write_text(fault_text, encoding="utf-8")
        fault_hash = digest(board)
        retained_fault_snapshot = None
        for repeat in ("first", "repeat"):
            fault_snapshot = capture_verified_pcb_snapshot(
                context,
                fixture_config,
                context.scratch / f"return-via-fault-{repeat}",
                expected_board_sha256=fault_hash,
                purpose="PCB return-via fault fixture",
                require_outer_copper=True,
            )
            fault_entries = pcb_decoupling_entries(placement_map, fault_snapshot)
            if (
                len(fault_entries) != 1
                or fault_entries[0].status != "INCOMPLETE"
                or fault_entries[0].selected_capacitors
                or fault_entries[0].candidates[0].return_via_distance_nm != 2_000_000
            ):
                raise ValueError(
                    f"Native distant-return-via fault was not detected: {fault_entries}"
                )
            if retained_fault_snapshot is None:
                retained_fault_snapshot = fault_snapshot
            elif retained_fault_snapshot != fault_snapshot:
                raise ValueError("Repeated native return-via evidence changed for identical input")
        log.event(
            "pcb-decoupling-fixture/placement",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            near_distance_nm=1_000_000,
            distant_distance_nm=15_000_000,
            connected_return_via_distance_nm=1_000_000,
            connected_return_via_count=2,
            distant_return_via_fault_distance_nm=2_000_000,
            board_thickness_nm=retained_snapshot.board_thickness_nm,
            opposite_side_same_xy_distance_nm=surface_fault_candidate.distance_3d_nm,
            opposite_side_limit_um=1500,
            same_side_control_distance_nm=surface_control_entry.candidates[0].distance_3d_nm,
            same_side_control_status=surface_control_entry.status,
            return_via_fault_sha256=fault_hash,
            rotated_pad="40.000,19.000 or 40.000,21.000 mm",
            repeatable="true",
            receipt=(context.scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-decoupling-fixture/placement",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
