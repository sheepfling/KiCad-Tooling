"""The shipped lint catalog is tied to implementation and fault/control regressions."""

from __future__ import annotations

import hashlib
import importlib
import re
from importlib.resources import files
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from kicad_tooling.design_lint import catalog_text
from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    rule_catalog,
    text_report,
)
from kicad_tooling.hwrepo.external_protection import evaluate as evaluate_external_protection
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleCatalog,
    DesignLintRuleId,
    DesignLintRuleMetadata,
    NetlistContract,
    PcbRfModuleAntennaMap,
    Stm32PinMapCoverageReport,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from kicad_tooling.hwrepo.stm32_pin_map import parse_cubemx_ioc, stm32_pin_map_mismatches
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext
from tests.test_connector_coverage import (
    ConnectorCoverageTests,
)
from tests.test_connector_return_distribution import (
    distribution_map as connector_distribution_map,
)
from tests.test_connector_return_distribution import (
    lint_report as connector_distribution_report,
)
from tests.test_crystal_networks import (
    CrystalNetworkTests,
    crystal_map,
    crystal_netlist,
)
from tests.test_design_lint import (
    DesignLintTests,
    can_netlist,
    can_peer_netlist,
    coach,
    complementary_usb_netlist,
    connector_capacitor_only_netlist,
    control_input_pins,
    generic_component_power_input_netlist,
    generic_connector_power_input_netlist,
    i2c_netlist,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_pullup_rails,
    ic_power_decoupling_fixture,
    led_rail_bridge_netlist,
    multiconductor_connector,
    observed,
    peer_component_power_pins,
    peer_connector_pin_assignments,
    repeated_component_supply_pins,
    serial_peer_voltage_netlist,
    spi_active_low_select_netlist,
    spi_peer_voltage_netlist,
    unconnected_component_power_pins,
    unconnected_protocol_pins,
)
from tests.test_external_protection import (
    ExternalProtectionTests,
    protection_map,
)
from tests.test_external_protection import (
    connector_coverage as protection_connector_coverage,
)
from tests.test_external_protection import (
    observed_netlist as protection_netlist,
)
from tests.test_i2c_addressing import (
    I2cAddressingTests,
    address_map,
    address_netlist,
    responder,
)
from tests.test_led_output_heuristics import (
    output_led_netlist,
)
from tests.test_open_drain_heuristics import (
    signal_netlist as open_drain_signal_netlist,
)
from tests.test_pcb_decoupling import (
    PcbDecouplingTests,
)
from tests.test_pcb_decoupling import (
    coverage_report as pcb_decoupling_coverage,
)
from tests.test_pcb_decoupling import (
    mapping as pcb_decoupling_map,
)
from tests.test_pcb_decoupling import (
    requirement as pcb_decoupling_requirement,
)
from tests.test_pcb_decoupling import (
    snapshot as pcb_decoupling_snapshot,
)
from tests.test_pcb_drc_coverage import incomplete_report, pair_map
from tests.test_pcb_keepouts import (
    incomplete_report as incomplete_keepout_report,
)
from tests.test_pcb_keepouts import (
    mapping_for as keepout_mapping_for,
)
from tests.test_pcb_protection_path import (
    coverage_report as pcb_protection_path_coverage,
)
from tests.test_pcb_protection_path import mapping as pcb_protection_path_map
from tests.test_pcb_protection_path import snapshot as pcb_protection_path_snapshot
from tests.test_pcb_reference_planes import (
    PcbReferencePlaneTests,
)
from tests.test_pcb_reference_planes import mapping as pcb_reference_plane_map
from tests.test_pcb_reference_planes import report as pcb_reference_plane_report
from tests.test_pcb_reference_planes import snapshot as pcb_reference_plane_snapshot
from tests.test_pcb_reference_planes import track as pcb_reference_plane_track
from tests.test_pcb_reference_planes import zone as pcb_reference_plane_zone
from tests.test_pcb_rf_antenna import (
    lint_report as pcb_rf_antenna_lint_report,
)
from tests.test_pcb_rf_antenna import (
    netlist as pcb_rf_antenna_netlist,
)
from tests.test_pcb_rf_antenna import (
    requirement as pcb_rf_antenna_requirement,
)
from tests.test_pcb_rf_antenna import (
    snapshot as pcb_rf_antenna_snapshot,
)
from tests.test_pcb_switching_loops import (
    PcbSwitchingLoopTests,
)
from tests.test_pcb_switching_loops import (
    coverage as pcb_switching_loop_coverage,
)
from tests.test_pcb_switching_loops import (
    mapping as pcb_switching_loop_map,
)
from tests.test_pcb_switching_loops import (
    snapshot as pcb_switching_loop_snapshot,
)
from tests.test_pcb_track_width import coverage as pcb_track_width_coverage
from tests.test_pcb_track_width import mapping as pcb_track_width_map
from tests.test_pcb_track_width import requirement as pcb_track_width_requirement
from tests.test_pcb_track_width import snapshot as pcb_track_width_snapshot
from tests.test_pcb_track_width import track as pcb_track_width_track
from tests.test_peer_power_output import (
    lint_report as peer_power_output_lint_report,
)
from tests.test_peer_power_output import (
    peer_power_output_netlist,
)
from tests.test_power_path_fixture_lane import (
    PowerPathFixtureLaneTests,
)
from tests.test_power_paths import (
    PowerPathTests,
    power_path_map,
    power_path_netlist,
)
from tests.test_power_pin_paths import (
    PowerSourcePathLintTests,
    source_path_netlist,
)
from tests.test_power_sequences import (
    PowerSequenceTests,
    power_sequence_map,
    power_sequence_netlist,
)
from tests.test_rc_filters import (
    RcFilterTests,
    rc_filter_map,
    rc_filter_netlist,
)
from tests.test_regulator_feedback import (
    RegulatorFeedbackTests,
    regulator_feedback_map,
    regulator_netlist,
)
from tests.test_regulator_feedback import (
    report as regulator_report,
)
from tests.test_schematic_geometry import (
    SchematicGeometryTests,
    free_text_anchor_fixture,
    free_text_objects_fixture,
    free_text_symbol_body_fixture,
    free_text_wire_fixture,
    symbol_body_wire_fixture,
)
from tests.test_serial_participants import serial_netlist as serial_participant_netlist
from tests.test_serial_peer_reference_review import (
    SerialPeerReferenceReviewTests,
    serial_reference_netlist,
)
from tests.test_spi_participants import spi_netlist as spi_participant_netlist
from tests.test_stm32_pin_map import (
    Stm32PinMapTests,
)
from tests.test_stm32_pin_map import (
    sample_map as stm32_sample_map,
)
from tests.test_stm32_pin_map import (
    sample_netlist as stm32_sample_netlist,
)
from tests.test_two_pin_crystals import (
    crystal_netlist as two_pin_crystal_netlist,
)
from tests.test_two_pin_crystals import (
    lint_report as two_pin_crystal_lint_report,
)
from tests.test_two_pin_diodes import diode_netlist
from tests.test_two_pin_diodes import (
    lint_report as two_pin_diode_lint_report,
)
from tests.test_two_pin_ferrites import (
    ferrite_netlist,
)
from tests.test_two_pin_ferrites import (
    lint_report as two_pin_ferrite_lint_report,
)
from tests.test_two_pin_fuses import (
    fuse_netlist,
)
from tests.test_two_pin_fuses import (
    lint_report as two_pin_fuse_lint_report,
)
from tests.test_two_pin_passives import (
    lint_report as two_pin_passive_lint_report,
)
from tests.test_two_pin_passives import (
    passive_netlist,
)
from tests.test_two_pin_switches import switch_netlist as two_pin_switch_netlist
from tests.test_usb_c_ports import (
    UsbCPortLintTests,
    usb_c_netlist,
)
from tests.test_usb_data_paths import (
    usb_data_map,
    usb_netlist,
)
from tests.test_usb_peer_reference_review import (
    UsbPeerReferenceReviewTests,
    usb_peer_netlist,
)


def test_catalog_ids_match_the_closed_policy_rule_type() -> None:
    catalog = rule_catalog()
    catalog_ids = tuple(item.rule_id for item in catalog.rules)
    assert sorted(catalog_ids) == sorted(get_args(DesignLintRuleId))
    assert len(catalog_ids) == len(set(catalog_ids))
    assert all(item.status == "active" for item in catalog.rules)
    assert all(
        item.default_mode == "off"
        for item in catalog.rules
        if item.rule_id
        in {
            "schematic.wire_end_on_pin_line",
            "schematic.pin_tip_on_wire_interior",
            "schematic.wire_endpoint_near_pin_tip",
            "schematic.label_near_wire_endpoint",
            "schematic.unmarked_wire_crossing",
            "schematic.unmarked_t_junction",
            "schematic.coincident_text_anchors",
            "schematic.free_text_overlap",
            "schematic.free_text_over_wire",
            "schematic.free_text_over_symbol_body",
            "schematic.wire_through_symbol_body",
        }
    )
    assert all(
        item.default_mode == "review"
        for item in catalog.rules
        if item.rule_id
        not in {
            "schematic.wire_end_on_pin_line",
            "schematic.pin_tip_on_wire_interior",
            "schematic.wire_endpoint_near_pin_tip",
            "schematic.label_near_wire_endpoint",
            "schematic.unmarked_wire_crossing",
            "schematic.unmarked_t_junction",
            "schematic.coincident_text_anchors",
            "schematic.free_text_overlap",
            "schematic.free_text_over_wire",
            "schematic.free_text_over_symbol_body",
            "schematic.wire_through_symbol_body",
        }
    )
    assert all(item.maturity == "synthetic_validated" for item in catalog.rules)


def test_catalog_digest_binds_the_shipped_metadata_bytes() -> None:
    content = files("kicad_tooling.hwrepo").joinpath("design-lint-rules.json").read_bytes()
    assert rule_catalog().sha256 == hashlib.sha256(content).hexdigest()
    assert rule_catalog().schema_version == "2"


def test_standalone_catalog_text_includes_default_and_evidence_limits() -> None:
    catalog = rule_catalog()
    rendered = catalog_text(catalog)
    assert f"{len(catalog.rules)} active rules" in rendered
    assert catalog.sha256 in rendered
    assert "connector.repeated_pin_function" in rendered
    assert "default review" in rendered
    assert "Evidence:" in rendered
    assert "Limits:" in rendered


def test_legacy_catalog_report_defaults_new_metamorphic_fields_to_unreviewed() -> None:
    metadata = rule_catalog().rules[0].model_dump(mode="python")
    metadata.pop("metamorphic_fixtures")
    metadata.pop("metamorphic_status")
    metadata.pop("metamorphic_not_applicable_basis")
    legacy_rule = DesignLintRuleMetadata.model_validate(metadata)
    assert legacy_rule.metamorphic_status == "unreviewed"
    legacy_catalog = DesignLintRuleCatalog(
        schema_version="1",
        sha256="a" * 64,
        rules=(legacy_rule,),
    )
    assert legacy_catalog.schema_version == "1"


def test_backlog_baseline_ids_match_the_active_catalog() -> None:
    backlog = (Path(__file__).parents[1] / "docs/DESIGN_LINT_BACKLOG.md").read_text(
        encoding="utf-8"
    )
    count_match = re.search(r"The following (\d+) rules are implemented", backlog)
    if count_match is None:
        pytest.fail("Backlog must state the active rule count")
    expected_count = int(count_match.group(1))
    baseline = backlog[count_match.end() :].split("This baseline catches", 1)[0]
    documented_ids = re.findall(r"^- `([^`]+)`$", baseline, flags=re.MULTILINE)
    active_ids = [item.rule_id for item in rule_catalog().rules if item.status == "active"]

    assert expected_count == len(active_ids)
    assert len(documented_ids) == expected_count
    assert sorted(documented_ids) == sorted(active_ids)


def test_documented_catalog_counts_match_the_active_catalog() -> None:
    repository = Path(__file__).parents[1]
    active_count = sum(item.status == "active" for item in rule_catalog().rules)
    count_pattern = re.compile(r"catalog\s+currently\s+contains\s+(\d+)\s+active\s+rules")

    for relative_path in ("docs/DESIGN_LINT.md", "docs/DESIGN_LINT_BACKLOG.md"):
        content = (repository / relative_path).read_text(encoding="utf-8")
        matches = count_pattern.findall(content)
        assert matches == [str(active_count)], relative_path


def test_active_catalog_entries_require_fault_and_control_coverage() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["fault_fixtures"] = ()
    with pytest.raises(ValidationError):
        DesignLintRuleMetadata.model_validate(entry)

    catalog = rule_catalog()
    with pytest.raises(ValidationError, match="rule IDs must be unique"):
        DesignLintRuleCatalog(
            schema_version=catalog.schema_version,
            sha256=catalog.sha256,
            rules=(catalog.rules[0], catalog.rules[0]),
        )


def test_metamorphic_status_requires_fixture_or_reasoned_not_applicability() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["metamorphic_fixtures"] = ()
    entry["metamorphic_status"] = "covered"
    with pytest.raises(ValidationError, match="needs a registered fixture"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["metamorphic_status"] = "not_applicable"
    with pytest.raises(ValidationError, match="needs a reason"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["metamorphic_not_applicable_basis"] = (
        "This rule evaluates a fixed scalar threshold without reordered source collections."
    )
    validated = DesignLintRuleMetadata.model_validate(entry)
    assert validated.metamorphic_status == "not_applicable"


def test_metamorphic_coverage_inventory_matches_the_backlog() -> None:
    catalog = rule_catalog()
    active = [item for item in catalog.rules if item.status == "active"]
    counts = {
        status: sum(item.metamorphic_status == status for item in active)
        for status in ("covered", "not_applicable", "unreviewed")
    }
    backlog = (Path(__file__).parents[1] / "docs/DESIGN_LINT_BACKLOG.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"Current catalog\s+audit:\s*(\d+) covered,\s*(\d+) not applicable,\s*"
        r"(\d+) unreviewed\.",
        backlog,
    )
    if match is None:
        pytest.fail("Backlog must publish the metamorphic coverage inventory")
    assert tuple(int(value) for value in match.groups()) == (
        counts["covered"],
        counts["not_applicable"],
        counts["unreviewed"],
    )
    assert counts["unreviewed"] == 0, (
        "classify every active rule with metamorphic fixtures or a reasoned not-applicable basis"
    )


def test_active_rules_reference_existing_regression_fixtures() -> None:
    instances = {
        DesignLintTests: DesignLintTests(),
        ConnectorCoverageTests: ConnectorCoverageTests(),
        I2cAddressingTests: I2cAddressingTests(),
        SchematicGeometryTests: SchematicGeometryTests(),
        ExternalProtectionTests: ExternalProtectionTests(),
        CrystalNetworkTests: CrystalNetworkTests(),
        RegulatorFeedbackTests: RegulatorFeedbackTests(),
        RcFilterTests: RcFilterTests(),
        PcbDecouplingTests: PcbDecouplingTests(),
        PcbReferencePlaneTests: PcbReferencePlaneTests(),
        PcbSwitchingLoopTests: PcbSwitchingLoopTests(),
        Stm32PinMapTests: Stm32PinMapTests(),
        SerialPeerReferenceReviewTests: SerialPeerReferenceReviewTests(),
        UsbPeerReferenceReviewTests: UsbPeerReferenceReviewTests(),
        PowerPathTests: PowerPathTests(),
        PowerSequenceTests: PowerSequenceTests(),
        PowerPathFixtureLaneTests: PowerPathFixtureLaneTests(),
        PowerSourcePathLintTests: PowerSourcePathLintTests(),
        UsbCPortLintTests: UsbCPortLintTests(),
    }
    fixtures: set[tuple[type, str]] = set()
    pytest_fixtures: set[str] = set()
    metamorphic_rules: set[str] = set()
    for entry in rule_catalog().rules:
        assert entry.fault_fixtures
        assert entry.valid_control_fixtures
        if entry.metamorphic_fixtures:
            metamorphic_rules.add(entry.rule_id)
        for name in (
            *entry.fault_fixtures,
            *entry.valid_control_fixtures,
            *entry.metamorphic_fixtures,
        ):
            parts = name.split(".")
            module = None
            module_length = 0
            for length in range(len(parts) - 1, 0, -1):
                try:
                    module = importlib.import_module(".".join(parts[:length]))
                except ModuleNotFoundError:
                    continue
                module_length = length
                break
            assert module is not None, name
            attributes = parts[module_length:]
            owner = module
            for attribute in attributes[:-1]:
                owner = getattr(owner, attribute)
            target = getattr(owner, attributes[-1])
            assert callable(target), name
            if isinstance(owner, type) and owner in instances:
                assert owner in instances, name
                fixtures.add((owner, attributes[-1]))
            else:
                assert len(attributes) == 1, name
                assert target.__name__.startswith("test_"), name
                pytest_fixtures.add(name)

    assert len(metamorphic_rules) >= 2
    assert pytest_fixtures, "catalog should support pytest function fixtures"

    for test_case, method_name in sorted(
        fixtures, key=lambda fixture: (fixture[0].__name__, fixture[1])
    ):
        getattr(instances[test_case], method_name)()


def test_every_active_rule_is_reachable_from_synthetic_cases() -> None:
    component_pins = NetlistContract(
        components={},
        nets={"DATA": ("J1.2",)},
        component_symbols={"J1": "Synthetic:Port"},
        pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
    )
    unroled_return_labels = NetlistContract(
        components={},
        nets={"USB_GND": ("J1.7",), "SERIAL_RETURN": ("J2.7",)},
        component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
        pin_functions={"J1.7": "7", "J2.7": "7"},
    )
    numbered_power_rails = NetlistContract(
        components={},
        nets={"+5V_1": ("J1.1",), "5V-2": ("J2.1",)},
        component_symbols={"J1": "Synthetic:PowerIn", "J2": "Synthetic:PowerOut"},
        pin_functions={"J1.1": "1", "J2.1": "1"},
    )
    no_can_assignments = can_netlist().model_copy(update={"nets": {}})
    cases = (
        observed(),
        generic_connector_power_input_netlist(),
        connector_capacitor_only_netlist(),
        source_path_netlist(wrong_rail=True),
        peer_connector_pin_assignments(),
        peer_connector_pin_assignments(("PORT_A", "PORT_B")),
        unroled_return_labels,
        numbered_power_rails,
        multiconductor_connector(return_named=False),
        component_pins,
        unconnected_component_power_pins(),
        ic_power_decoupling_fixture(),
        led_rail_bridge_netlist(),
        output_led_netlist(),
        repeated_component_supply_pins(),
        peer_component_power_pins(),
        control_input_pins(),
        control_input_pins(connected=True, visible_bias=False),
        unconnected_protocol_pins(),
        spi_participant_netlist(),
        spi_peer_voltage_netlist(),
        serial_peer_voltage_netlist(),
        serial_reference_netlist(),
        usb_peer_netlist(),
        i2c_netlist(),
        i2c_netlist_with_parallel_sda(),
        i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)),
        spi_active_low_select_netlist(),
        can_netlist(),
        can_peer_netlist(divergent_peer=True),
        no_can_assignments,
        complementary_usb_netlist(negative_net=None),
        complementary_usb_netlist(),
    )
    emitted = {item.rule_id for source in cases for item in candidates(source)}
    emitted.update(
        item.rule_id
        for item in candidates(
            usb_netlist(fault="missing-dp-resistor"),
            usb_data_path_map=usb_data_map(),
        )
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            power_path_netlist(fault="open-element"),
            power_path_map=power_path_map(),
        )
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            power_sequence_netlist(fault="open-enable"),
            power_sequence_map=power_sequence_map(),
        )
    )
    stm32_ioc = (
        (Path(__file__).parent / "fixtures/design_lint/stm32-pin-map/valid.ioc")
        .read_bytes()
        .replace(b"PB6.Signal=I2C1_SCL", b"PB6.Signal=I2C1_SDA")
    )
    stm32_map = stm32_sample_map()
    stm32_netlist = stm32_sample_netlist()
    stm32_ioc_sha256 = hashlib.sha256(stm32_ioc).hexdigest()
    stm32_coverage = Stm32PinMapCoverageReport(
        status="COMPLETE",
        mode="review",
        map_sha256="b" * 64,
        netlist_sha256="a" * 64,
        ioc_source_hashes={"firmware/controller.ioc": stm32_ioc_sha256},
        mapped_pin_count=len(stm32_map.pins),
        excluded_pin_count=len(stm32_map.exclusions),
        mismatches=stm32_pin_map_mismatches(
            stm32_map,
            stm32_netlist,
            parse_cubemx_ioc(stm32_ioc),
            ioc_sha256=stm32_ioc_sha256,
            map_sha256="b" * 64,
            netlist_sha256="a" * 64,
        ),
    )
    emitted.update(
        item.rule_id for item in candidates(stm32_netlist, stm32_pin_map_coverage=stm32_coverage)
    )
    i2c_specification = address_map(
        responder("U1", address=0x50),
        responder("U2", address=0x51, strap=False),
    )
    i2c_observed = address_netlist(i2c_specification, strap_values={"U1": 1})
    i2c_coverage = scan_i2c_address_map(i2c_specification, i2c_observed, "b" * 64)
    emitted.update(
        item.rule_id for item in candidates(i2c_observed, i2c_address_coverage=i2c_coverage)
    )
    geometry = scan_wire_ends_on_pin_lines(
        (Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch").read_bytes(),
        source_path="tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    emitted.update(item.rule_id for item in candidates(observed(), schematic_geometry=geometry))
    wire_interior_geometry = scan_wire_ends_on_pin_lines(
        (
            Path(__file__).parent / "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch"
        ).read_bytes(),
        source_path="tests/fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=wire_interior_geometry)
    )
    near_tip_geometry = scan_wire_ends_on_pin_lines(
        (
            Path(__file__).parent / "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch"
        ).read_bytes(),
        source_path="tests/fixtures/design_lint/wire-end-near-pin-tip.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=near_tip_geometry)
    )
    label_geometry = scan_wire_ends_on_pin_lines(
        (
            Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
        ).read_bytes(),
        source_path="tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=label_geometry)
    )
    crossing_geometry = scan_wire_ends_on_pin_lines(
        (
            Path(__file__).parent / "fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch"
        ).read_bytes(),
        source_path="tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=crossing_geometry)
    )
    t_junction_geometry = scan_wire_ends_on_pin_lines(
        (
            Path(__file__).parent / "fixtures/design_lint/t-junction/fault-no-junction.kicad_sch"
        ).read_bytes(),
        source_path="tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.2"}),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=t_junction_geometry)
    )
    text_anchor_geometry = scan_wire_ends_on_pin_lines(
        free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)),
        source_path="synthetic/free-text-anchor.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=text_anchor_geometry)
    )
    text_overlap_geometry = scan_wire_ends_on_pin_lines(
        free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        ),
        source_path="synthetic/free-text-overlap.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=text_overlap_geometry)
    )
    text_wire_geometry = scan_wire_ends_on_pin_lines(
        free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)),
        source_path="synthetic/free-text-wire.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=text_wire_geometry)
    )
    text_body_geometry = scan_wire_ends_on_pin_lines(
        free_text_symbol_body_fixture(),
        source_path="synthetic/free-text-symbol-body.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=text_body_geometry)
    )
    symbol_body_geometry = scan_wire_ends_on_pin_lines(
        symbol_body_wire_fixture(),
        source_path="synthetic/symbol-body-wire.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    emitted.update(
        item.rule_id for item in candidates(observed(), schematic_geometry=symbol_body_geometry)
    )
    unreviewed_protection = evaluate_external_protection(
        None,
        protection_netlist(),
        protection_connector_coverage(),
        "a" * 64,
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            protection_netlist(),
            external_protection_coverage=unreviewed_protection,
        )
    )
    mismatched_protection = evaluate_external_protection(
        protection_map(),
        protection_netlist(fault="protector-wrong-net"),
        protection_connector_coverage(),
        "b" * 64,
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            protection_netlist(fault="protector-wrong-net"),
            external_protection_coverage=mismatched_protection,
        )
    )
    crystal_fault = crystal_netlist(c1_value="47pF", c2_value="47pF")
    crystal_report = evaluate(
        "synthetic-crystal",
        coach(crystal_fault),
        DesignLintPolicy(crystal_network_map=crystal_map()),
    )
    emitted.update(item.rule_id for item in crystal_report.findings)
    feedback_result = regulator_report(
        regulator_netlist(fault="upper-resistor-outside-range"), regulator_feedback_map()
    )
    emitted.update(item.rule_id for item in feedback_result.findings)
    rc_filter_result = evaluate(
        "synthetic-rc-filter",
        coach(rc_filter_netlist(capacitor_value="220nF")),
        DesignLintPolicy(rc_filter_map=rc_filter_map()),
    )
    emitted.update(item.rule_id for item in rc_filter_result.findings)
    connector_distribution_result = connector_distribution_report(
        ("signal",) * 6 + ("return", "supply", "shield"),
        policy=DesignLintPolicy(connector_return_distribution_map=connector_distribution_map()),
    )
    emitted.update(item.rule_id for item in connector_distribution_result.findings)
    decoupling_map = pcb_decoupling_map(pcb_decoupling_requirement(maximum_um=None))
    decoupling_result = evaluate(
        "synthetic-decoupling",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_decoupling_map=decoupling_map),
        pcb_decoupling_coverage=pcb_decoupling_coverage(decoupling_map, pcb_decoupling_snapshot()),
    )
    emitted.update(item.rule_id for item in decoupling_result.findings)
    protection_path_map = pcb_protection_path_map()
    protection_path_result = evaluate(
        "synthetic-protection-path",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_protection_path_map=protection_path_map),
        pcb_protection_path_coverage=pcb_protection_path_coverage(
            protection_path_map,
            pcb_protection_path_snapshot(
                entry_distance_nm=100_001,
                via_offsets_nm=(2_900_000,),
            ),
        ),
    )
    emitted.update(item.rule_id for item in protection_path_result.findings)
    track_width_map = pcb_track_width_map(pcb_track_width_requirement(minimum_um=251))
    track_width_result = evaluate(
        "synthetic-track-width",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_track_width_map=track_width_map),
        pcb_track_width_coverage=pcb_track_width_coverage(
            track_width_map,
            pcb_track_width_snapshot(pcb_track_width_track("001", "VDD", 250_000)),
        ),
    )
    emitted.update(item.rule_id for item in track_width_result.findings)
    reference_hole = (
        (4_000_000, 4_000_000),
        (6_000_000, 4_000_000),
        (6_000_000, 6_000_000),
        (4_000_000, 6_000_000),
    )
    reference_map = pcb_reference_plane_map()
    reference_result = evaluate(
        "synthetic-reference-plane",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_reference_plane_map=reference_map),
        pcb_reference_plane_coverage=pcb_reference_plane_report(
            reference_map,
            pcb_reference_plane_snapshot(
                pcb_reference_plane_track(),
                zones=(
                    pcb_reference_plane_zone(
                        "00000000-0000-0000-0000-000000000001", holes=(reference_hole,)
                    ),
                ),
            ),
        ),
    )
    emitted.update(item.rule_id for item in reference_result.findings)
    switching_loop_map = pcb_switching_loop_map()
    switching_loop_result = evaluate(
        "synthetic-switching-loop",
        coach(observed()),
        DesignLintPolicy(pcb_switching_loop_map=switching_loop_map),
        pcb_switching_loop_coverage=pcb_switching_loop_coverage(
            switching_loop_map, pcb_switching_loop_snapshot(expanded=True)
        ),
    )
    emitted.update(item.rule_id for item in switching_loop_result.findings)
    pair_result = evaluate(
        "synthetic-differential-pair",
        coach(observed()),
        DesignLintPolicy(pcb_differential_pair_rule_map=pair_map()),
        pcb_differential_pair_coverage=incomplete_report(),
    )
    emitted.update(item.rule_id for item in pair_result.findings)
    from tests.test_pcb_signal_path_coverage import incomplete_signal_report, path_map

    emitted.update(
        item.rule_id
        for item in candidates(
            observed(),
            pcb_signal_path_coverage=incomplete_signal_report(path_map()),
        )
    )
    keepout_map = keepout_mapping_for()
    keepout_result = evaluate(
        "synthetic-keepout",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_keepout_map=keepout_map),
        pcb_keepout_coverage=incomplete_keepout_report(keepout_map),
    )
    emitted.update(item.rule_id for item in keepout_result.findings)
    rf_antenna_map = PcbRfModuleAntennaMap(
        basis="Synthetic catalog reachability requirement",
        requirements=(pcb_rf_antenna_requirement(),),
    )
    rf_antenna_result = pcb_rf_antenna_lint_report(
        policy=DesignLintPolicy(pcb_rf_module_antenna_map=rf_antenna_map),
        source_netlist=pcb_rf_antenna_netlist(symbol="RF_Module:Other"),
        observed_board=pcb_rf_antenna_snapshot(),
    )
    emitted.update(item.rule_id for item in rf_antenna_result.findings)
    passive_result = two_pin_passive_lint_report(passive_netlist())
    emitted.update(item.rule_id for item in passive_result.findings)
    diode_result = two_pin_diode_lint_report(diode_netlist())
    emitted.update(item.rule_id for item in diode_result.findings)
    crystal_result = two_pin_crystal_lint_report(two_pin_crystal_netlist())
    emitted.update(item.rule_id for item in crystal_result.findings)
    fuse_result = two_pin_fuse_lint_report(fuse_netlist())
    emitted.update(item.rule_id for item in fuse_result.findings)
    peer_power_output_result = peer_power_output_lint_report(peer_power_output_netlist())
    emitted.update(item.rule_id for item in peer_power_output_result.findings)
    ferrite_result = two_pin_ferrite_lint_report(ferrite_netlist())
    emitted.update(item.rule_id for item in ferrite_result.findings)
    emitted.update(item.rule_id for item in candidates(two_pin_switch_netlist()))
    emitted.update(item.rule_id for item in candidates(generic_component_power_input_netlist()))
    emitted.update(
        item.rule_id
        for item in candidates(
            usb_c_netlist(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
    )
    emitted.update(item.rule_id for item in candidates(open_drain_signal_netlist()))
    emitted.update(
        item.rule_id for item in candidates(open_drain_signal_netlist(output_type="open_emitter"))
    )
    emitted.update(
        item.rule_id
        for item in candidates(
            serial_participant_netlist(),
            serial_peer_roster=SerialPeerRosterContext(state="not_configured"),
        )
    )
    active = {item.rule_id for item in rule_catalog().rules if item.status == "active"}
    assert emitted == active


def test_reports_include_catalog_and_reject_uncatalogued_finding_ids() -> None:
    report = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
    assert report.rule_catalog is not None
    assert report.rule_catalog.sha256 == rule_catalog().sha256
    assert f"{len(rule_catalog().rules)} active rules" in text_report(report)
    assert "Schematic geometry coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB decoupling coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB protection-path coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB track-width coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB reference-plane coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB switching-loop coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB differential-pair DRC rule coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB keepout intent coverage: NOT_REQUESTED" in text_report(report)
    assert "I2C address-map coverage: NOT_REQUESTED" in text_report(report)
    assert "Regulator feedback coverage: NOT_REQUESTED" in text_report(report)
    assert "RC filter coverage: NOT_REQUESTED" in text_report(report)
    assert "Connector return-distribution coverage: NOT_REQUESTED" in text_report(report)

    without_return_rule = report.rule_catalog.model_copy(
        update={
            "rules": tuple(
                item for item in report.rule_catalog.rules if item.rule_id != "net.numbered_returns"
            )
        }
    )
    malformed = report.model_dump(mode="python")
    malformed["rule_catalog"] = without_return_rule.model_dump(mode="python")
    with pytest.raises(ValueError, match="absent from the active catalog"):
        DesignLintReport.model_validate(malformed)
