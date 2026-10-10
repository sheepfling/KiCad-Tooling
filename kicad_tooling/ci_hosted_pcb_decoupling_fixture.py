"""Native geometry regression for mapped PCB decoupling placement."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .hwrepo.evidence import digest
from .hwrepo.models import (
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
)
from .hwrepo.pcb_decoupling import pcb_decoupling_entries

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


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
            if len(c1_return.connected_vias) != 1:
                raise ValueError("Native decoupling fixture must connect C1 return to one via")
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
                or entries[0].candidates[0].connected_return_via_count != 1
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

        fixture_text = source.read_text(encoding="utf-8")
        if fixture_text.count("(at 12 11)") != 1:
            raise ValueError("Native return-via fixture no longer has its unique test coordinate")
        board.write_text(fixture_text.replace("(at 12 11)", "(at 13 11)", 1), encoding="utf-8")
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
            distant_return_via_fault_distance_nm=2_000_000,
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
