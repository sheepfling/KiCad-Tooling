"""Verify native source and fault/control behavior for mapped supply ranges."""

from __future__ import annotations

import hashlib
import json

from .ci_hosted_component_rating_context import ComponentRatingFixtureContext
from .ci_hosted_support import HostedLog
from .hwrepo.component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    ComponentSupplyVoltageRangeRequirement,
)
from .hwrepo.contracts import read_kicad_erc_report
from .hwrepo.design_lint_power_supply_range import component_supply_voltage_range_candidates
from .hwrepo.design_lint_power_supply_range_coverage import (
    component_supply_range_pin_coverage_candidates,
)
from .hwrepo.design_lint_power_supply_range_map_coverage import (
    component_supply_range_map_coverage_candidates,
)
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract
from .hwrepo.power_component_supply_range import RULE_ID
from .hwrepo.power_component_supply_range_coverage import (
    component_supply_range_pin_coverage_issues,
)


def verify_component_supply_range_fixture(
    context: ComponentRatingFixtureContext,
    log: HostedLog,
) -> None:
    """Check both exact-version exports and the mapped out-of-range prompt."""
    fixture_hashes = {
        "fault": context.supply_range_fault_sha256,
        "control": context.supply_range_control_sha256,
    }
    if fixture_hashes["fault"] != fixture_hashes["control"]:
        # The fixtures differ only in the two native voltage-label strings.
        source_texts = {
            "fault": context.supply_range_fault_fixture.read_text(encoding="utf-8"),
            "control": context.supply_range_control_fixture.read_text(encoding="utf-8"),
        }
        if source_texts["fault"].replace('"24V"', '"5V"') != source_texts["control"]:
            raise ValueError("Supply-range native fault and control differ beyond rail labels")

    parsed: dict[str, NetlistContract] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    erc_signatures: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
    for case in ("fault", "control"):
        for run in ("first", "repeat"):
            netlist_path = context.output / f"supply-range.{case}.{run}.netlist.xml"
            erc_path = context.output / f"supply-range.{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Supply-range native export omitted the {case} {run} evidence")
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes[case, run] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != context.config.kicad_version:
                raise ValueError("Supply-range ERC evidence has the wrong KiCad version")
            signature = tuple(sorted((item.type, item.severity) for item in erc.violations))
            if any(severity == "error" for _, severity in signature):
                raise ValueError(f"Supply-range synthetic schematic has ERC errors: {signature}")
            erc_signatures[case, run] = signature
            parsed[f"{case}:{run}"] = observed

        if netlist_hashes[case, "first"] != netlist_hashes[case, "repeat"]:
            raise ValueError(f"Supply-range {case} netlist export was not repeatable")
        if erc_signatures[case, "first"] != erc_signatures[case, "repeat"]:
            raise ValueError(f"Supply-range {case} ERC signature was not repeatable")

    map_entry = ComponentSupplyVoltageRangeRequirement(
        id="synthetic-input-range",
        reference="U1",
        expected_symbol="Synthetic:SupplyRangeIC",
        expected_footprint="Synthetic:SOT23-3",
        expected_part_id="SYNTHETIC-SUPPLY-RANGE-IC",
        pin="U1.1",
        expected_pin_function="VIN",
        minimum_voltage_v=5.0,
        maximum_voltage_v=12.0,
        range_source="Synthetic test basis only",
        range_conditions="Synthetic native fault/control boundary; not a device specification",
    )
    requirements = ComponentSupplyVoltageRangeMap(
        basis="Synthetic native fixture only",
        requirements=(map_entry,),
    )
    fault = parsed["fault:first"]
    control = parsed["control:first"]
    for observed in (fault, control):
        component = observed.components.get("U1")
        if (
            component is None
            or component.footprint != map_entry.expected_footprint
            or component.part_id != map_entry.expected_part_id
            or observed.component_symbols.get("U1") != map_entry.expected_symbol
            or "1" not in observed.component_pin_numbers.get("U1", ())
            or "2" not in observed.component_pin_numbers.get("U1", ())
            or observed.pin_functions.get("U1.1") != "VIN"
            or observed.pin_electrical_types.get("U1.1") != "power_in"
            or observed.pin_functions.get("U1.2") != "VDD"
            or observed.pin_electrical_types.get("U1.2") != "power_in"
        ):
            raise ValueError("Native supply-range fixture lost exact component or pin evidence")
        second_component = observed.components.get("U3")
        if (
            second_component is None
            or second_component.footprint != "Synthetic:SOT23-3"
            or second_component.part_id != "SYNTHETIC-UNCOVERED-SUPPLY-IC"
            or observed.component_symbols.get("U3") != "Synthetic:SupplyRangeIC"
            or observed.component_pin_numbers.get("U3") != ("1", "2")
            or observed.pin_functions.get("U3.1") != "VIN"
            or observed.pin_functions.get("U3.2") != "VDD"
            or observed.pin_electrical_types.get("U3.1") != "power_in"
            or observed.pin_electrical_types.get("U3.2") != "power_in"
        ):
            raise ValueError("Native supply-range fixture lost unmapped U3 pin evidence")

    fault_findings = component_supply_voltage_range_candidates(fault, requirements)
    control_findings = component_supply_voltage_range_candidates(control, requirements)
    if (
        len(fault_findings) != 1
        or fault_findings[0].rule_id != RULE_ID
        or fault_findings[0].evidence.get("assigned_net") != ("24V",)
        or fault_findings[0].evidence.get("net_label_voltage_v") != ("24",)
        or control_findings
        or "U1.1" not in control.nets.get("5V", ())
    ):
        raise ValueError("Native component supply-range fault/control did not match expectations")

    second_map_entry = ComponentSupplyVoltageRangeRequirement(
        id="synthetic-second-input-range",
        reference="U1",
        expected_symbol=map_entry.expected_symbol,
        expected_footprint=map_entry.expected_footprint,
        expected_part_id=map_entry.expected_part_id,
        pin="U1.2",
        expected_pin_function="VDD",
        minimum_voltage_v=0.0,
        maximum_voltage_v=5.0,
        range_source="Synthetic test basis only",
        range_conditions="Synthetic native coverage control; not a device specification",
    )
    complete_map = ComponentSupplyVoltageRangeMap(
        basis="Synthetic native fixture only",
        requirements=(map_entry, second_map_entry),
    )
    coverage_faults = component_supply_range_pin_coverage_candidates(fault, requirements)
    coverage_controls = component_supply_range_pin_coverage_candidates(fault, complete_map)
    coverage_issues = component_supply_range_pin_coverage_issues(fault, requirements)
    if (
        len(coverage_faults) != 1
        or coverage_faults[0].rule_id != "power.component_supply_range_pin_coverage"
        or coverage_faults[0].evidence.get("unmapped_power_input_pins") != ("U1.2",)
        or coverage_controls
        or len(coverage_issues) != 1
        or coverage_issues[0].native_power_input_pins != ("U1.1", "U1.2")
    ):
        raise ValueError(
            "Native supply-range pin-coverage fault/control did not match expectations"
        )

    u3_input_map_entry = ComponentSupplyVoltageRangeRequirement(
        id="synthetic-u3-input-range",
        reference="U3",
        expected_symbol="Synthetic:SupplyRangeIC",
        expected_footprint="Synthetic:SOT23-3",
        expected_part_id="SYNTHETIC-UNCOVERED-SUPPLY-IC",
        pin="U3.1",
        expected_pin_function="VIN",
        minimum_voltage_v=0.0,
        maximum_voltage_v=5.0,
        range_source="Synthetic test basis only",
        range_conditions="Synthetic native coverage control; not a device specification",
    )
    u3_secondary_input_map_entry = ComponentSupplyVoltageRangeRequirement(
        id="synthetic-u3-secondary-input-range",
        reference="U3",
        expected_symbol=u3_input_map_entry.expected_symbol,
        expected_footprint=u3_input_map_entry.expected_footprint,
        expected_part_id=u3_input_map_entry.expected_part_id,
        pin="U3.2",
        expected_pin_function="VDD",
        minimum_voltage_v=0.0,
        maximum_voltage_v=5.0,
        range_source="Synthetic test basis only",
        range_conditions="Synthetic native coverage control; not a device specification",
    )
    full_project_map = ComponentSupplyVoltageRangeMap(
        basis="Synthetic native fixture only",
        requirements=(
            map_entry,
            second_map_entry,
            u3_input_map_entry,
            u3_secondary_input_map_entry,
        ),
    )
    map_coverage_faults = component_supply_range_map_coverage_candidates(fault, requirements)
    map_coverage_controls = component_supply_range_map_coverage_candidates(
        control, full_project_map
    )
    if (
        len(map_coverage_faults) != 1
        or map_coverage_faults[0].rule_id != "power.component_supply_range_map_coverage"
        or map_coverage_faults[0].evidence.get("component") != ("U3",)
        or map_coverage_faults[0].evidence.get("native_power_input_pins") != ("U3.1", "U3.2")
        or map_coverage_controls
    ):
        raise ValueError("Native supply-range map-coverage fault/control did not match")

    log.event(
        "component-supply-range-fixture/native-export",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        fault_sha256=digest(context.supply_range_fault_fixture),
        control_sha256=digest(context.supply_range_control_fixture),
        normalized_netlist_sha256=netlist_hashes["fault", "first"],
        repeat_normalized_netlist_sha256=netlist_hashes["fault", "repeat"],
        erc_error_types="none",
        erc_signature=repr(erc_signatures["fault", "first"]),
        repeatable="true",
    )
    log.event(
        "component-supply-range-fixture/out-of-range-fault",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        net="24V",
        finding_rule=RULE_ID,
        repeatable="true",
    )
    log.event(
        "component-supply-range-fixture/in-range-control",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        net="5V",
        finding_rule="none",
        repeatable="true",
    )
    log.event(
        "component-supply-range-coverage-fixture/missing-map-entry",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        unmapped_power_input_pin="U1.2",
        finding_rule="power.component_supply_range_pin_coverage",
        repeatable="true",
    )
    log.event(
        "component-supply-range-coverage-fixture/complete-map-control",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        mapped_power_input_pins="U1.1,U1.2",
        finding_rule="none",
        repeatable="true",
    )
    log.event(
        "component-supply-range-fixture/unmapped-component-fault",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        component="U3",
        finding_rule="power.component_supply_range_map_coverage",
        repeatable="true",
    )
    log.event(
        "component-supply-range-fixture/complete-project-map-control",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        mapped_components="U1,U3",
        finding_rule="none",
        repeatable="true",
    )
