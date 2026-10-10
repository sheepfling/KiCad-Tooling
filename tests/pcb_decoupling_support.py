"""Synthetic PCB decoupling maps and connectivity evidence builders."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.models import (
    PcbConnectivitySnapshot,
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
    PcbPadConnectivityObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_decoupling import pcb_decoupling_entries
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport

IC = "Synthetic:IC_QFN"
CAP = "Synthetic:Cap_0603"
RULE = "pcb.decoupling_proximity"


def requirement(
    *,
    capacitors: tuple[PcbDecouplingCapacitor, ...] | None = None,
    maximum_um: int | None = 100,
    maximum_return_via_um: int | None = None,
    selection: str = "any",
    supply_pad: str = "U1.1",
    return_pad: str = "U1.2",
    id: str = "core-rail",
) -> PcbDecouplingRequirement:
    return PcbDecouplingRequirement(
        id=id,
        basis="Synthetic device pin map and placement review limit",
        ic_reference="U1",
        ic_footprint=IC,
        supply_pad=supply_pad,
        return_pad=return_pad,
        supply_net="VDD",
        return_net="GND",
        capacitors=capacitors
        or (
            PcbDecouplingCapacitor(
                reference="C1",
                footprint=CAP,
                supply_pad="C1.1",
                return_pad="C1.2",
            ),
        ),
        selection=selection,  # type: ignore[arg-type]
        max_distance_um=maximum_um,
        max_return_via_distance_um=maximum_return_via_um,
    )


def mapping(*items: PcbDecouplingRequirement) -> PcbDecouplingMap:
    return PcbDecouplingMap(
        basis="Synthetic reviewed component pin assignments",
        requirements=items or (requirement(),),
    )


def snapshot(
    *,
    distances_nm: dict[str, int] | None = None,
    wrong_supply_nets: frozenset[str] = frozenset(),
    disconnected_supply: frozenset[str] = frozenset(),
    dnp_caps: frozenset[str] = frozenset(),
    footprints: dict[str, str] | None = None,
    extra_ic_supply: bool = False,
    return_vias_nm: dict[str, tuple[tuple[int, int], ...]] | None = None,
    unconnected_vias_nm: tuple[tuple[int, int], ...] = (),
) -> PcbConnectivitySnapshot:
    distances_nm = distances_nm or {"C1": 80_000}
    footprints = footprints or {}
    supply_refs = ["U1.1"]
    return_refs = ["U1.2"]
    cap_refs = [f"{reference}.{pin}" for reference in distances_nm for pin in ("1", "2")]
    return_vias_nm = return_vias_nm or {}
    via_ids_by_cap: dict[str, tuple[str, ...]] = {}
    vias: list[PcbViaObservation] = []
    for reference, locations in return_vias_nm.items():
        ids: list[str] = []
        for index, (x_nm, y_nm) in enumerate(locations):
            via_id = hashlib.sha256(f"{reference}-connected-via-{index}".encode()).hexdigest()
            ids.append(via_id)
            vias.append(
                PcbViaObservation(
                    id=via_id,
                    net="GND",
                    x_nm=x_nm,
                    y_nm=y_nm,
                    start_layer="F.Cu",
                    end_layer="In1.Cu",
                    diameter_nm=600_000,
                    drill_nm=300_000,
                    kind="through",
                    multiplicity=1,
                )
            )
        via_ids_by_cap[reference.casefold()] = tuple(ids)
    for index, (x_nm, y_nm) in enumerate(unconnected_vias_nm):
        via_id = hashlib.sha256(f"unconnected-via-{index}".encode()).hexdigest()
        vias.append(
            PcbViaObservation(
                id=via_id,
                net="GND",
                x_nm=x_nm,
                y_nm=y_nm,
                start_layer="F.Cu",
                end_layer="In1.Cu",
                diameter_nm=600_000,
                drill_nm=300_000,
                kind="through",
                multiplicity=1,
            )
        )
    if extra_ic_supply:
        supply_refs.append("U1.3")
        return_refs.append("U1.4")
    pads: list[PcbPadConnectivityObservation] = []
    for reference in (*supply_refs, *return_refs, *cap_refs):
        component = reference.rsplit(".", 1)[0]
        pin = reference.rsplit(".", 1)[1]
        is_supply = pin == "1" or reference in supply_refs
        net = "VDD" if is_supply else "GND"
        if reference in wrong_supply_nets and is_supply:
            net = "ALT_VDD"
        group = supply_refs if is_supply else return_refs
        if component.startswith("C"):
            group = [*group, reference]
        if reference in disconnected_supply:
            connected = (reference,)
        else:
            connected = tuple(dict.fromkeys((reference, *group)))
        if component.startswith("C"):
            x = distances_nm[component]
            y = 0 if pin == "1" else 20_000
            # These are native world coordinates after the footprint's rotation.
            position = (x, y)
        elif reference == "U1.1":
            position = (0, 0)
        elif reference == "U1.2":
            position = (0, 20_000)
        elif reference == "U1.3":
            position = (0, 40_000)
        else:
            position = (0, 60_000)
        pads.append(
            PcbPadConnectivityObservation(
                pad=reference,
                net=net,
                footprint=footprints.get(component, IC if component == "U1" else CAP),
                dnp=component in dnp_caps,
                connected_pads=connected,
                connected_zones=(),
                connected_islands=(),
                connected_vias=(
                    via_ids_by_cap.get(component.casefold(), ())
                    if component.startswith("C") and pin == "2"
                    else ()
                ),
                positions_nm=(position,),
            )
        )
    return PcbConnectivitySnapshot(
        schema_version="5",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=tuple(pads),
        net_ties=(),
        zones=(),
        vias=tuple(vias),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
    )


def coverage_report(
    mapped: PcbDecouplingMap, evidence: PcbConnectivitySnapshot
) -> PcbDecouplingCoverageReport:
    entries = pcb_decoupling_entries(mapped, evidence)
    return PcbDecouplingCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(mapped.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/project.kicad_pcb",
        board_sha256=evidence.board_sha256,
        snapshot_path="build/design-lint/pcb-decoupling/snapshot.json",
        snapshot_sha256=hashlib.sha256(evidence.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=evidence.probe_sha256,
        kicad_version=evidence.kicad_version,
        image=evidence.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )
