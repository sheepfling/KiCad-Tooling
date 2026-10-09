"""Source-bound RF module identity and placement-relative antenna checks."""

from __future__ import annotations

from hashlib import sha256

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbRfAntennaKeepout,
    PcbRfAntennaPolygon,
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
    PcbRfModuleAntennaRequirement,
    PcbRuleAreaObservation,
    PcbRuleAreaPolygonObservation,
)
from kicad_tooling.hwrepo.pcb_rf_antenna import (
    _transform_point,
    pcb_rf_module_antenna_entries,
)

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


def test_exact_module_identity_feed_and_local_keepout_transform_complete() -> None:
    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        netlist(),
        snapshot(),
    )

    assert len(result) == 1
    assert result[0].status == "COMPLETE"
    assert result[0].issues == ()
    assert result[0].expected_geometry_sha256 == result[0].observed_geometry_sha256
    assert result[0].observed_schematic_rf_feed_nets == ("RF_IN",)
    assert result[0].observed_board_rf_feed_net == "RF_IN"


@pytest.mark.parametrize(
    ("position_nm", "orientation_microdegrees", "side", "local", "expected"),
    (
        ((100, 200), 0, "F.Cu", (7, 9), (107, 209)),
        ((100, 200), 90_000_000, "F.Cu", (7, 9), (109, 193)),
        ((100, 200), 270_000_000, "B.Cu", (7, 9), (109, 207)),
        ((100, 200), 360_000_000 - 90_000_000, "F.Cu", (7, 9), (91, 207)),
    ),
)
def test_footprint_local_transform_uses_board_angle_and_side(
    position_nm: tuple[int, int],
    orientation_microdegrees: int,
    side: str,
    local: tuple[int, int],
    expected: tuple[int, int],
) -> None:
    assert (
        _transform_point(
            local,
            placement(
                position_nm=position_nm,
                orientation_microdegrees=orientation_microdegrees,
                side=side,
            ),
        )
        == expected
    )


def test_module_and_keepout_moving_together_preserves_exact_coverage() -> None:
    moved = placement(position_nm=(1_234_100, -4_900))
    moved_area = area(polygon=expected_board_polygon(offset_nm=(100, 100)))

    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        netlist(),
        snapshot(board_placement=moved, rule_areas=(moved_area,)),
    )[0]

    assert result.status == "COMPLETE"


def test_requirement_order_does_not_change_entry_order_or_results() -> None:
    first = requirement()
    second = requirement(disposition="dnp").model_copy(
        update={"id": "unused-module", "reference": "U2"}
    )
    authored = PcbRfModuleAntennaMap(
        basis="Synthetic RF layout review",
        requirements=(first, second),
    )
    reordered = authored.model_copy(update={"requirements": (second, first)})

    first_entries = pcb_rf_module_antenna_entries(authored, netlist(), snapshot())
    reordered_entries = pcb_rf_module_antenna_entries(reordered, netlist(), snapshot())

    assert first_entries == reordered_entries
    assert tuple(item.id for item in first_entries) == ("radio", "unused-module")


def test_moving_only_the_module_leaves_keepout_coverage_incomplete() -> None:
    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        netlist(),
        snapshot(board_placement=placement(position_nm=(1_234_100, -4_900))),
    )[0]

    assert result.status == "INCOMPLETE"
    assert any("geometry does not match" in issue for issue in result.issues)


@pytest.mark.parametrize(
    ("areas", "expected_issue"),
    (
        ((), "named native antenna keepout is missing"),
        (
            (
                area(),
                area(
                    name="radio-antenna-clearance",
                    polygon=expected_board_polygon(offset_nm=(1, 0)),
                    uuid="22345678-1234-5678-1234-567812345678",
                ),
            ),
            "named native antenna keepout is ambiguous",
        ),
        (
            (area(polygon=expected_board_polygon(offset_nm=(1, 0))),),
            "geometry does not match",
        ),
        (
            (
                PcbRuleAreaObservation(
                    **area().model_dump(exclude={"layers"}),
                    layers=("F.Cu",),
                ),
            ),
            "copper layers differ",
        ),
    ),
)
def test_missing_duplicate_and_mismatched_keepouts_are_incomplete(
    areas: tuple[PcbRuleAreaObservation, ...],
    expected_issue: str,
) -> None:
    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        netlist(),
        snapshot(rule_areas=areas),
    )[0]

    assert result.status == "INCOMPLETE"
    assert any(expected_issue in issue for issue in result.issues)


@pytest.mark.parametrize(
    ("observed_netlist", "observed_snapshot", "expected_issue"),
    (
        (netlist(symbol="RF_Module:Other"), snapshot(), "symbol differs"),
        (netlist(footprint="RF_Module:Other"), snapshot(), "schematic footprint differs"),
        (netlist(part_id="RADIO-2"), snapshot(), "part ID differs"),
        (netlist(feed_net="RF_OUT"), snapshot(), "schematic RF feed pad"),
        (netlist(), snapshot(pad_net="RF_OUT"), "PCB RF feed pad"),
        (
            netlist(),
            snapshot(pad_footprint="RF_Module:Other"),
            "native PCB RF feed pad footprint",
        ),
    ),
)
def test_source_identity_and_feed_mismatches_are_incomplete(
    observed_netlist: NetlistContract,
    observed_snapshot: PcbConnectivitySnapshot,
    expected_issue: str,
) -> None:
    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        observed_netlist,
        observed_snapshot,
    )[0]

    assert result.status == "INCOMPLETE"
    assert any(expected_issue in issue for issue in result.issues)


def test_explicit_external_antenna_and_dnp_dispositions_are_supported() -> None:
    external_requirement = requirement(disposition="external_antenna")
    external = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(
            basis="Synthetic RF layout review", requirements=(external_requirement,)
        ),
        netlist(),
        snapshot(rule_areas=()),
    )[0]
    dnp_requirement = requirement(disposition="dnp")
    dnp = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(dnp_requirement,)),
        netlist(feed_net=None, dnp=True),
        snapshot(
            board_placement=placement(dnp=True),
            rule_areas=(),
            pad_net=None,
            pad_dnp=True,
        ),
    )[0]

    assert external.status == "COMPLETE"
    assert dnp.status == "COMPLETE"
    assert external.expected_keepout_name is None
    assert dnp.expected_dnp is True


def test_schema_without_explicit_footprint_inventory_is_incomplete() -> None:
    result = pcb_rf_module_antenna_entries(
        PcbRfModuleAntennaMap(basis="Synthetic RF layout review", requirements=(requirement(),)),
        netlist(),
        snapshot(schema_version="11"),
    )[0]

    assert result.status == "INCOMPLETE"
    assert any("requires PCB snapshot schema 12" in issue for issue in result.issues)


def test_requirement_rejects_ambiguous_disposition_and_feed_combinations() -> None:
    raw = requirement().model_dump()
    raw["disposition"] = "external_antenna"
    with pytest.raises(ValueError, match="external-antenna"):
        PcbRfModuleAntennaRequirement.model_validate(raw)

    raw = requirement(disposition="dnp").model_dump()
    raw["rf_feed_pad"] = "U1.1"
    raw["rf_feed_net"] = "RF_IN"
    with pytest.raises(ValueError, match="DNP"):
        PcbRfModuleAntennaRequirement.model_validate(raw)


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


def test_rf_antenna_lint_finding_supports_review_block_off_and_exact_ignore() -> None:
    antenna_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module review",
        requirements=(requirement(),),
    )
    source_netlist = netlist()
    fault_board = snapshot(pad_net="RF_OUT")
    base_policy = DesignLintPolicy(pcb_rf_module_antenna_map=antenna_map)
    reviewed = lint_report(
        policy=base_policy,
        source_netlist=source_netlist,
        observed_board=fault_board,
    )
    (finding,) = tuple(
        item
        for item in reviewed.findings
        if item.rule_id == "pcb.rf_module_antenna_keepout_coverage"
    )
    assert reviewed.status == "REVIEW"
    assert finding.disposition == "OPEN"

    blocked = lint_report(
        policy=base_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="pcb.rf_module_antenna_keepout_coverage",
                        mode="block",
                        reason="Synthetic RF coverage gate",
                    ),
                )
            }
        ),
        source_netlist=source_netlist,
        observed_board=fault_board,
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        policy=base_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="pcb.rf_module_antenna_keepout_coverage",
                        mode="off",
                        reason="Synthetic RF coverage gate",
                    ),
                )
            }
        ),
        source_netlist=source_netlist,
        observed_board=fault_board,
    )
    assert disabled.pcb_rf_module_antenna_coverage.status == "DISABLED"
    assert not any(item.rule_id == finding.rule_id for item in disabled.findings)

    ignored = lint_report(
        policy=base_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic exact RF review disposition",
                    ),
                )
            }
        ),
        source_netlist=source_netlist,
        observed_board=fault_board,
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == finding.rule_id)
    assert ignored_finding.disposition == "IGNORED"
