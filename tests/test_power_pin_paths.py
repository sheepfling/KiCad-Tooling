"""Synthetic regressions for conservative power-input source-path review."""

from __future__ import annotations

import hashlib
import unittest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
)
from kicad_tooling.hwrepo.power_pin_paths import power_inputs_without_supported_source_paths

RULE_ID = "power.input_without_supported_source_path"


def source_path_netlist(
    *,
    wrong_rail: bool = False,
    source_present: bool = True,
    capacitor_present: bool = True,
    capacitor_dnp: bool = False,
    series_symbol: str = "Device:FerriteBead",
    series_value: str = "Ferrite bead",
    series_dnp: bool = False,
    source_less_name_only: bool = False,
    capacitor_symbol: str = "Device:C",
) -> NetlistContract:
    supply_net = "+3V3" if source_less_name_only else "VLOAD"
    source_net = "VIN" if source_present else "LOCAL_SOURCE"
    components = {
        "FB1": ComponentContract(value=series_value, footprint="Synthetic:0603"),
        "U2": ComponentContract(value="Synthetic load", footprint="Synthetic:PowerLoad"),
    }
    symbols = {"FB1": series_symbol, "U2": "Synthetic:PowerLoad"}
    pin_numbers = {"FB1": ("1", "2"), "U2": ("1",)}
    dnp: list[str] = []
    nets: dict[str, tuple[str, ...]] = {
        source_net: ("FB1.1",),
        supply_net: ("FB1.2", "U2.1"),
        "GND": (),
    }
    if source_present:
        components["U1"] = ComponentContract(
            value="Synthetic source", footprint="Synthetic:PowerSource"
        )
        symbols["U1"] = "Synthetic:PowerSource"
        pin_numbers["U1"] = ("1",)
        nets[source_net] = ("U1.1", "FB1.1")
    if wrong_rail:
        nets[source_net] = ("U1.1",) if source_present else ()
        nets["GND"] = ("FB1.1",)
    if capacitor_present:
        components["C1"] = ComponentContract(value="100nF", footprint="Synthetic:0603")
        symbols["C1"] = capacitor_symbol
        pin_numbers["C1"] = ("1", "2")
        nets[supply_net] = (*nets[supply_net], "C1.1")
        nets["GND"] = (*nets["GND"], "C1.2")
        if capacitor_dnp:
            dnp.append("C1")
    if series_dnp:
        dnp.append("FB1")
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=tuple(dnp),
        component_symbols=symbols,
        pin_functions={"U1.1": "VOUT", "U2.1": "VIN"},
        pin_electrical_types={
            **({"U1.1": "power_out"} if source_present else {}),
            "U2.1": "power_in",
        },
        component_pin_numbers=pin_numbers,
    )


def series_diode_netlist(
    *,
    reverse: bool = False,
    dnp: bool = False,
    symbol: str = "Device:D",
    pin_functions: tuple[str, str] = ("K", "A"),
) -> NetlistContract:
    """Use the native Device:D pin functions: pin 1 K, pin 2 A."""
    source = source_path_netlist()
    if reverse:
        nets = dict(source.nets)
        nets["VIN"] = ("U1.1", "FB1.1")
        nets["VLOAD"] = ("FB1.2", "U2.1", "C1.1")
    else:
        nets = dict(source.nets)
        nets["VIN"] = ("U1.1", "FB1.2")
        nets["VLOAD"] = ("FB1.1", "U2.1", "C1.1")
    components = dict(source.components)
    components["D1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["D1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["D1"] = ("1", "2")
    nets = {net: tuple(pin.replace("FB1.", "D1.") for pin in pins) for net, pins in nets.items()}
    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map["D1.1"] = pin_functions[0]
    pin_function_map["D1.2"] = pin_functions[1]
    dnp_components = ("D1",) if dnp else ()
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": dnp_components,
            "pin_functions": pin_function_map,
        }
    )


def series_jumper_netlist(
    *,
    symbol: str = "Jumper:SolderJumper_2_Bridged",
    dnp: bool = False,
    pin_functions: tuple[str, str] = ("A", "B"),
    pin_numbers: tuple[str, str] = ("1", "2"),
) -> NetlistContract:
    """Use the native two-pole bridged solder-jumper identity and pin roles."""
    source = source_path_netlist()
    components = dict(source.components)
    components["JP1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["JP1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["JP1"] = pin_numbers
    nets = {
        net: tuple(pin.replace("FB1.", "JP1.") for pin in pins) for net, pins in source.nets.items()
    }
    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map["JP1.1"] = pin_functions[0]
    pin_function_map["JP1.2"] = pin_functions[1]
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": ("JP1",) if dnp else (),
            "nets": nets,
            "pin_functions": pin_function_map,
        }
    )


def series_three_pin_jumper_netlist(
    *,
    symbol: str = "Jumper:SolderJumper_3_Bridged12",
    dnp: bool = False,
    pin_functions: tuple[str, ...] = ("A", "C", "B"),
    pin_numbers: tuple[str, ...] = ("1", "2", "3"),
    source_pin: str = "1",
    load_pin: str = "2",
    unassigned_pins: frozenset[str] = frozenset(),
) -> NetlistContract:
    """Use the native three-terminal jumper roles and selected bridge topology."""
    source = source_path_netlist()
    components = dict(source.components)
    components["JP1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["JP1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["JP1"] = pin_numbers

    jumper_nets = {number: f"JP_UNUSED_{number}" for number in pin_numbers}
    jumper_nets[source_pin] = "VIN"
    jumper_nets[load_pin] = "VLOAD"
    nets = {
        net: tuple(pin for pin in pins if not pin.startswith("FB1."))
        for net, pins in source.nets.items()
    }
    for number, net in jumper_nets.items():
        if number not in unassigned_pins:
            nets[net] = (*nets.get(net, ()), f"JP1.{number}")
    nets = {net: pins for net, pins in nets.items() if pins}

    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map.update(
        {f"JP1.{number}": function for number, function in zip(pin_numbers, pin_functions)}
    )
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": ("JP1",) if dnp else (),
            "nets": nets,
            "pin_functions": pin_function_map,
        }
    )


def power_path_map() -> PowerPathMap:
    return PowerPathMap(
        basis="Synthetic source-to-load path requirement",
        paths=(
            PowerPathRequirement(
                id="source-to-load",
                basis="Synthetic load is powered through the fitted ferrite bead",
                start=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:PowerSource",
                    footprint="Synthetic:PowerSource",
                    net="VIN",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:PowerLoad",
                    footprint="Synthetic:PowerLoad",
                    net="VLOAD",
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="FB1",
                        symbol="Device:FerriteBead",
                        footprint="Synthetic:0603",
                        side_a_pin="FB1.1",
                        side_b_pin="FB1.2",
                        side_a_net="VIN",
                        side_b_net="VLOAD",
                    ),
                ),
            ),
        ),
    )


def external_source_netlist(
    *, power_out: bool, source_dnp: bool = False, isolated_return: bool = False
) -> NetlistContract:
    """Return a fitted connector-fed rail with an unrecognized custom net name."""
    source = source_path_netlist()
    components = dict(source.components)
    components.pop("U1")
    components["J1"] = ComponentContract(value="External supply", footprint="Synthetic:2Pin")
    symbols = dict(source.component_symbols)
    symbols.pop("U1")
    symbols["J1"] = "Connector_Generic:Conn_01x02"
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers.pop("U1")
    pin_numbers["J1"] = ("1", "2")
    pin_types = {"U2.1": "power_in"}
    if power_out:
        pin_types["J1.1"] = "power_out"
    nets = {
        "AUX_INPUT": ("J1.1", "FB1.1"),
        "VLOAD": ("FB1.2", "U2.1", "C1.1"),
        "GND": ("C1.2",),
    }
    pin_functions = {"J1.1": "PWR", "U2.1": "VIN"}
    if isolated_return:
        nets = {
            "AUX_INPUT": ("J1.1", "FB1.1"),
            "ISO_SUPPLY": ("FB1.2", "U2.1", "C1.1"),
            "ISO_RETURN": ("C1.2", "J1.2"),
        }
        pin_functions["J1.2"] = "RTN"
    dnp_components = source.dnp_components + (("J1",) if source_dnp else ())
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "dnp_components": dnp_components,
            "nets": nets,
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_types,
        }
    )


def regulator_source_netlist(*, regulator_dnp: bool) -> NetlistContract:
    """Return an explicit regulator input/output anchor with selectable DNP state."""
    source = source_path_netlist()
    components = dict(source.components)
    components.pop("FB1")
    components["U3"] = ComponentContract(value="Synthetic regulator", footprint="Synthetic:SOT23")
    symbols = dict(source.component_symbols)
    symbols.pop("FB1")
    symbols["U3"] = "Synthetic:Regulator"
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers.pop("FB1")
    pin_numbers["U3"] = ("1", "2", "3")
    dnp = (*source.dnp_components, *(("U3",) if regulator_dnp else ()))
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "dnp_components": dnp,
            "nets": {
                "VIN": ("U1.1", "U3.1"),
                "VLOAD": ("U3.2", "U2.1", "C1.1"),
                "GND": ("U3.3", "C1.2"),
            },
            "pin_functions": {
                "U1.1": "VOUT",
                "U2.1": "VIN",
                "U3.1": "VIN",
                "U3.2": "VOUT",
                "U3.3": "GND",
            },
            "pin_electrical_types": {
                "U1.1": "power_out",
                "U2.1": "power_in",
                "U3.1": "power_in",
                "U3.2": "power_out",
            },
        }
    )


def lint_report(netlist: NetlistContract, policy: DesignLintPolicy | None = None):
    netlist_sha256 = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-input-path",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate("synthetic-power-input-path", coach, policy or DesignLintPolicy())


class PowerSourcePathLintTests(unittest.TestCase):
    def test_wrong_rail_with_fitted_decoupling_is_reviewed_without_authored_map(self) -> None:
        report = lint_report(source_path_netlist(wrong_rail=True))
        findings = [item for item in report.findings if item.rule_id == RULE_ID]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject, "VLOAD: power-input source-path review")
        self.assertEqual(
            findings[0].evidence,
            {
                "net": ("VLOAD",),
                "power_input_pins": ("U2.1",),
                "fitted_capacitors_to_return": ("C1",),
                "recognized_source_nets": ("VIN",),
                "source_anchor_state": ("recognized",),
            },
        )
        self.assertIn("does not prove that a connection is required", findings[0].message)

    def test_valid_ferrite_low_resistance_and_named_rail_paths_are_controls(self) -> None:
        cases = (
            source_path_netlist(),
            source_path_netlist(series_symbol="Device:R", series_value="0R"),
            source_path_netlist(series_symbol="Device:R", series_value="1R"),
            source_path_netlist(source_less_name_only=True),
        )
        for netlist in cases:
            with self.subTest(symbol=netlist.component_symbols["FB1"], nets=netlist.nets):
                self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_forward_series_diodes_with_exact_native_identity_and_pin_roles_are_controls(
        self,
    ) -> None:
        for symbol in ("Device:D", "Device:D_Schottky"):
            with self.subTest(symbol=symbol):
                netlist = series_diode_netlist(symbol=symbol)
                self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_exact_fitted_bridged_solder_jumper_is_a_bidirectional_control(self) -> None:
        netlist = series_jumper_netlist()
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_exact_three_terminal_bridge_topologies_are_recognized(self) -> None:
        cases = (
            series_three_pin_jumper_netlist(
                symbol="Jumper:SolderJumper_3_Bridged12", source_pin="1", load_pin="2"
            ),
            series_three_pin_jumper_netlist(
                symbol="Jumper:SolderJumper_3_Bridged123", source_pin="1", load_pin="3"
            ),
        )
        for netlist in cases:
            with self.subTest(symbol=netlist.component_symbols["JP1"], nets=netlist.nets):
                self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_bridged12_does_not_infer_a_path_to_terminal_three(self) -> None:
        netlist = series_three_pin_jumper_netlist(
            symbol="Jumper:SolderJumper_3_Bridged12", source_pin="1", load_pin="3"
        )
        self.assertTrue(power_inputs_without_supported_source_paths(netlist))

    def test_open_dnp_or_incompletely_mapped_solder_jumpers_remain_review_candidates(
        self,
    ) -> None:
        cases = (
            ("open-symbol", series_jumper_netlist(symbol="Jumper:SolderJumper_2_Open")),
            (
                "open-three-pin-symbol",
                series_three_pin_jumper_netlist(symbol="Jumper:SolderJumper_3_Open"),
            ),
            (
                "dnp-three-pin-bridge",
                series_three_pin_jumper_netlist(dnp=True),
            ),
            (
                "wrong-three-pin-inventory",
                series_three_pin_jumper_netlist(pin_numbers=("1", "2", "4")),
            ),
            (
                "wrong-three-pin-role",
                series_three_pin_jumper_netlist(pin_functions=("A", "B", "C")),
            ),
            (
                "unassigned-three-pin-terminal",
                series_three_pin_jumper_netlist(unassigned_pins=frozenset({"3"})),
            ),
            ("dnp-bridged", series_jumper_netlist(dnp=True)),
            ("wrong-inventory", series_jumper_netlist(pin_numbers=("1", "3"))),
            ("unsupported-role", series_jumper_netlist(pin_functions=("A", "X"))),
            ("duplicate-role", series_jumper_netlist(pin_functions=("A", "A"))),
        )
        for name, netlist in cases:
            with self.subTest(case=name):
                self.assertTrue(power_inputs_without_supported_source_paths(netlist))

    def test_reverse_dnp_unsupported_and_unmapped_diodes_do_not_count_as_source_paths(
        self,
    ) -> None:
        cases = (
            ("reverse", series_diode_netlist(reverse=True), True),
            ("dnp", series_diode_netlist(dnp=True), True),
            ("unsupported-symbol", series_diode_netlist(symbol="Device:D_Zener"), True),
            ("unsupported-pin-roles", series_diode_netlist(pin_functions=("K", "X")), True),
            ("duplicate-pin-role", series_diode_netlist(pin_functions=("K", "K")), True),
            ("forward", series_diode_netlist(), False),
        )
        for name, netlist, expected in cases:
            with self.subTest(case=name):
                self.assertEqual(
                    bool(power_inputs_without_supported_source_paths(netlist)), expected
                )

    def test_only_recognized_fitted_paths_and_supported_metadata_count(self) -> None:
        cases = (
            (source_path_netlist(series_symbol="Device:R", series_value="1.1R"), True),
            (source_path_netlist(series_dnp=True), True),
            (source_path_netlist(series_symbol="Synthetic:Link"), True),
            (source_path_netlist(wrong_rail=True, capacitor_dnp=True), False),
            (source_path_netlist(wrong_rail=True, capacitor_present=False), False),
            (source_path_netlist(wrong_rail=True, source_present=False), True),
        )
        for netlist, expected in cases:
            with self.subTest(dnp=netlist.dnp_components, symbols=netlist.component_symbols):
                self.assertEqual(
                    bool(power_inputs_without_supported_source_paths(netlist)), expected
                )

    def test_unrecognized_external_connector_source_becomes_a_coverage_review(self) -> None:
        netlist = external_source_netlist(power_out=False)
        report = lint_report(netlist)
        finding = next(item for item in report.findings if item.rule_id == RULE_ID)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(finding.evidence["recognized_source_nets"], ())
        self.assertEqual(finding.evidence["source_anchor_state"], ("not_recognized",))
        self.assertIn("custom rail names, external connector supplies", finding.message)

    def test_external_connector_power_out_is_a_source_anchor_control(self) -> None:
        netlist = external_source_netlist(power_out=True)
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_dnp_external_power_out_does_not_anchor_the_assembly(self) -> None:
        netlist = external_source_netlist(power_out=True, source_dnp=True)
        finding = next(item for item in candidates(netlist) if item.rule_id == RULE_ID)
        self.assertEqual(finding.evidence["recognized_source_nets"], ())
        self.assertEqual(finding.evidence["source_anchor_state"], ("not_recognized",))

    def test_isolated_external_supply_keeps_its_return_separate_and_reviewable(self) -> None:
        untyped_external = external_source_netlist(power_out=False, isolated_return=True)
        report = lint_report(untyped_external)
        finding = next(item for item in report.findings if item.rule_id == RULE_ID)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(untyped_external.nets["ISO_RETURN"], ("C1.2", "J1.2"))
        self.assertNotIn("GND", untyped_external.nets)
        ignored = lint_report(
            untyped_external,
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic project records an intentionally isolated external supply",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition,
            "IGNORED",
        )

        typed_external = external_source_netlist(power_out=True, isolated_return=True)
        self.assertEqual(typed_external.nets["ISO_RETURN"], ("C1.2", "J1.2"))
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(typed_external)})

    def test_recognized_custom_capacitor_name_counts_but_arbitrary_symbol_does_not(self) -> None:
        named_custom = source_path_netlist(
            wrong_rail=True, capacitor_symbol="Vendor:Power_Capacitor"
        )
        arbitrary_custom = source_path_netlist(wrong_rail=True, capacitor_symbol="Vendor:CAP123")
        self.assertIn(RULE_ID, {item.rule_id for item in candidates(named_custom)})
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(arbitrary_custom)})

    def test_fitted_regulator_output_is_an_anchor_but_dnp_output_is_not(self) -> None:
        fitted = regulator_source_netlist(regulator_dnp=False)
        dnp = regulator_source_netlist(regulator_dnp=True)
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(fitted)})
        finding = next(item for item in candidates(dnp) if item.rule_id == RULE_ID)
        self.assertEqual(finding.evidence["recognized_source_nets"], ("VIN",))

    def test_unmapped_diode_generic_jumper_and_custom_library_paths_remain_review_candidates(
        self,
    ) -> None:
        cases = (
            source_path_netlist(series_symbol="Device:D", series_value="Schottky"),
            source_path_netlist(series_symbol="Device:Jumper", series_value="Link"),
            source_path_netlist(series_symbol="Custom:Ferrite_Bead", series_value="600R@100M"),
        )
        for netlist in cases:
            with self.subTest(symbol=netlist.component_symbols["FB1"]):
                self.assertIn(RULE_ID, {item.rule_id for item in candidates(netlist)})

    def test_connector_power_inputs_are_outside_this_review(self) -> None:
        source = source_path_netlist(wrong_rail=True)
        components = dict(source.components)
        components.pop("U2")
        components["J2"] = ComponentContract(value="Synthetic connector", footprint="")
        symbols = dict(source.component_symbols)
        symbols.pop("U2")
        symbols["J2"] = "Connector_Generic:Conn_01x02"
        pin_numbers = dict(source.component_pin_numbers)
        pin_numbers.pop("U2")
        pin_numbers["J2"] = ("1", "2")
        nets = {
            net: tuple("J2.1" if pin == "U2.1" else pin for pin in pins)
            for net, pins in source.nets.items()
        }
        connector = source.model_copy(
            update={
                "components": components,
                "component_symbols": symbols,
                "component_pin_numbers": pin_numbers,
                "nets": nets,
                "pin_electrical_types": {"U1.1": "power_out", "J2.1": "power_in"},
            }
        )
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(connector)})

    def test_standard_connector_identity_under_nonstandard_reference_is_excluded(self) -> None:
        source = source_path_netlist(wrong_rail=True)
        components = dict(source.components)
        components["U7"] = components.pop("U2")
        symbols = dict(source.component_symbols)
        symbols["U7"] = "Connector_Generic:Conn_01x02"
        symbols.pop("U2")
        pin_numbers = dict(source.component_pin_numbers)
        pin_numbers["U7"] = pin_numbers.pop("U2")
        nets = {
            net: tuple("U7.1" if pin == "U2.1" else pin for pin in pins)
            for net, pins in source.nets.items()
        }
        standard_connector = source.model_copy(
            update={
                "components": components,
                "component_symbols": symbols,
                "component_pin_numbers": pin_numbers,
                "nets": nets,
                "pin_electrical_types": {"U1.1": "power_out", "U7.1": "power_in"},
            }
        )
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(standard_connector)})

        custom_connector = standard_connector.model_copy(
            update={"component_symbols": {**symbols, "U7": "Custom:Interface"}}
        )
        self.assertIn(
            RULE_ID,
            {item.rule_id for item in candidates(custom_connector)},
        )
        self.assertEqual(
            power_inputs_without_supported_source_paths(
                custom_connector, declared_connector_references=("U7",)
            ),
            (),
        )

    def test_project_map_covers_its_endpoint_without_duplicate_heuristic(self) -> None:
        report = lint_report(
            source_path_netlist(wrong_rail=True),
            DesignLintPolicy(power_path_map=power_path_map()),
        )
        ids = {item.rule_id for item in report.findings}
        self.assertIn("power.mapped_series_path_mismatch", ids)
        self.assertNotIn(RULE_ID, ids)

    def test_review_block_off_and_exact_ignore_lifecycle(self) -> None:
        source = source_path_netlist(wrong_rail=True)
        initial = lint_report(source)
        finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
        for mode, expected_status, disposition in (
            ("block", "FAIL", "OPEN"),
            ("off", "PASS", "RULE_OFF"),
        ):
            report = lint_report(
                source,
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=RULE_ID,
                            mode=mode,
                            reason="Synthetic policy exercises the power-path review mode",
                        ),
                    )
                ),
            )
            self.assertEqual(report.status, expected_status)
            self.assertEqual(
                next(item for item in report.findings if item.rule_id == RULE_ID).disposition,
                disposition,
            )
        ignored = lint_report(
            source,
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic reviewer accepts this exact isolated supply domain",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition,
            "IGNORED",
        )

    def test_finding_is_order_stable_and_valid_path_clears_it(self) -> None:
        source = source_path_netlist(wrong_rail=True)
        original = lint_report(source)
        original_candidate = next(item for item in candidates(source) if item.rule_id == RULE_ID)
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_candidate = next(
            item for item in candidates(reordered) if item.rule_id == RULE_ID
        )
        self.assertEqual(original_candidate, reordered_candidate)
        self.assertNotEqual(original.netlist_sha256, lint_report(reordered).netlist_sha256)
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(source_path_netlist())})

        reverse_diode = series_diode_netlist(reverse=True)
        reverse_finding = next(
            item for item in candidates(reverse_diode) if item.rule_id == RULE_ID
        )
        reordered_reverse_diode = reverse_diode.model_copy(
            update={
                "components": dict(reversed(tuple(reverse_diode.components.items()))),
                "nets": dict(reversed(tuple(reverse_diode.nets.items()))),
                "component_symbols": dict(reversed(tuple(reverse_diode.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(reverse_diode.pin_functions.items()))),
                "pin_electrical_types": dict(
                    reversed(tuple(reverse_diode.pin_electrical_types.items()))
                ),
                "component_pin_numbers": dict(
                    reversed(tuple(reverse_diode.component_pin_numbers.items()))
                ),
            }
        )
        reordered_reverse_finding = next(
            item for item in candidates(reordered_reverse_diode) if item.rule_id == RULE_ID
        )
        forward_diode = series_diode_netlist()
        self.assertNotIn(RULE_ID, {item.rule_id for item in candidates(forward_diode)})
        self.assertEqual(reverse_finding, reordered_reverse_finding)


if __name__ == "__main__":
    unittest.main()
