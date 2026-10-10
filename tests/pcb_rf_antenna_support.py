"""Synthetic RF antenna requirements and source-bound evidence builders."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbRfAntennaKeepout,
    PcbRfAntennaPolygon,
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaRequirement,
    PcbRuleAreaObservation,
    PcbRuleAreaPolygonObservation,
)
from kicad_tooling.hwrepo.pcb_rf_antenna import pcb_rf_module_antenna_entries

UUID = "12345678-1234-5678-1234-567812345678"

HASH = sha256(b"synthetic source").hexdigest()

FOOTPRINT = "RF_Module:Module_Antenna"

SYMBOL = "RF_Module:Radio"


def requirement(*, disposition: str = "onboard_antenna") -> PcbRfModuleAntennaRequirement:
    return PcbRfModuleAntennaRequirement(
        id="radio",
        basis="Synthetic approved module layout requirement",
        reference="U1",
        expected_symbol=SYMBOL,
        expected_footprint=FOOTPRINT,
        expected_part_id="RADIO-1",
        disposition=disposition,
        rf_feed_pad=None if disposition == "dnp" else "U1.1",
        rf_feed_net=None if disposition == "dnp" else "RF_IN",
        keepout=(
            PcbRfAntennaKeepout(
                name="radio-antenna-clearance",
                local_polygons=(
                    PcbRfAntennaPolygon(
                        outline_nm=((0, 0), (10, 0), (10, 8), (0, 8)),
                        holes_nm=(((2, 2), (2, 4), (4, 4), (4, 2)),),
                    ),
                ),
                layers=("F.Cu", "B.Cu"),
                forbids_tracks=True,
                forbids_vias=True,
                forbids_pads=True,
                forbids_zone_fills=True,
                forbids_footprints=False,
            )
            if disposition == "onboard_antenna"
            else None
        ),
    )


def placement(
    *,
    position_nm: tuple[int, int] = (1_234_000, -5_000),
    orientation_microdegrees: int = 90_000_000,
    side: str = "F.Cu",
    footprint: str = FOOTPRINT,
    dnp: bool = False,
) -> PcbFootprintPlacementObservation:
    return PcbFootprintPlacementObservation(
        reference="U1",
        footprint=footprint,
        dnp=dnp,
        position_nm=position_nm,
        orientation_microdegrees=orientation_microdegrees,
        side=side,
    )


def expected_board_polygon(
    *,
    offset_nm: tuple[int, int] = (0, 0),
) -> PcbRuleAreaPolygonObservation:
    x, y = 1_234_000 + offset_nm[0], -5_000 + offset_nm[1]
    return PcbRuleAreaPolygonObservation(
        outline_nm=((x, y - 10), (x + 8, y - 10), (x + 8, y), (x, y)),
        holes_nm=(((x + 2, y - 2), (x + 2, y - 4), (x + 4, y - 4), (x + 4, y - 2)),),
    )


def area(
    *,
    name: str = "radio-antenna-clearance",
    polygon: PcbRuleAreaPolygonObservation | None = None,
    uuid: str = UUID,
) -> PcbRuleAreaObservation:
    return PcbRuleAreaObservation(
        uuid=uuid,
        name=name,
        layers=("B.Cu", "F.Cu"),
        net=None,
        polygons=(polygon or expected_board_polygon(),),
        forbids_tracks=True,
        forbids_vias=True,
        forbids_pads=True,
        forbids_zone_fills=True,
        forbids_footprints=False,
    )


def netlist(
    *,
    symbol: str = SYMBOL,
    footprint: str = FOOTPRINT,
    part_id: str | None = "RADIO-1",
    feed_net: str | None = "RF_IN",
    dnp: bool = False,
) -> NetlistContract:
    return NetlistContract(
        components={"U1": ComponentContract(value="Radio", footprint=footprint, part_id=part_id)},
        nets={} if feed_net is None else {feed_net: ("U1.1",)},
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        component_pin_numbers={"U1": ("1",)},
    )


def snapshot(
    *,
    board_placement: PcbFootprintPlacementObservation | None = None,
    rule_areas: tuple[PcbRuleAreaObservation, ...] | None = None,
    pad_net: str | None = "RF_IN",
    pad_footprint: str = FOOTPRINT,
    pad_dnp: bool = False,
    schema_version: str = "12",
) -> PcbConnectivitySnapshot:
    module_placement = board_placement or placement(dnp=pad_dnp, footprint=pad_footprint)
    return PcbConnectivitySnapshot(
        schema_version=schema_version,
        board_sha256=HASH,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5",
        probe_sha256=HASH,
        zones_refilled=True,
        pads=(
            PcbPadConnectivityObservation(
                pad="U1.1",
                net=pad_net,
                footprint=pad_footprint,
                dnp=pad_dnp,
                connected_pads=("U1.1",),
                connected_zones=(),
                connected_islands=(),
                connected_vias=(),
                positions_nm=((1_234_000, -5_000),),
            ),
        )
        if schema_version == "12" or pad_net is not None
        else (),
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
        rule_areas=(area(),) if rule_areas is None else rule_areas,
        footprints=(module_placement,) if schema_version == "12" else (),
    )


def lint_report(
    *,
    policy: DesignLintPolicy,
    source_netlist: NetlistContract,
    observed_board: PcbConnectivitySnapshot,
) -> DesignLintReport:
    antenna_map = policy.pcb_rf_module_antenna_map
    assert antenna_map is not None
    entries = pcb_rf_module_antenna_entries(antenna_map, source_netlist, observed_board)
    coverage = PcbRfModuleAntennaCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=sha256(antenna_map.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/synthetic.kicad_pcb",
        board_sha256=HASH,
        snapshot_path="build/design-lint/synthetic-pcb.json",
        snapshot_sha256=HASH,
        probe_sha256=HASH,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5",
        netlist_sha256=HASH,
        entries=entries,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-rf",
        source_hashes={},
        netlist_sha256=HASH,
        observed=source_netlist,
    )
    return evaluate(
        "synthetic-rf",
        coach,
        policy,
        pcb_rf_module_antenna_coverage=coverage,
    )
