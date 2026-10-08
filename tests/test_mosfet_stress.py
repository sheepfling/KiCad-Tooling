"""Authored MOSFET state intervals are checked against exact native identity."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    MosfetOperatingState,
    MosfetStressAnalysis,
    MosfetStressRequirement,
    MosfetVoltageInterval,
    NetlistContract,
)
from kicad_tooling.hwrepo.mosfet_stress import mosfet_stress_checks
from kicad_tooling.validate import read_netlist


def requirement() -> MosfetStressAnalysis:
    return MosfetStressAnalysis(
        basis="Synthetic MOSFET absolute-rating stress review",
        required_states=("off", "on"),
        states=(
            MosfetOperatingState(
                id="off",
                net_potentials={
                    "D_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                    "G_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                    "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                },
            ),
            MosfetOperatingState(
                id="on",
                net_potentials={
                    "D_NET": MosfetVoltageInterval(minimum_v=49.0, maximum_v=51.0),
                    "G_NET": MosfetVoltageInterval(minimum_v=9.0, maximum_v=11.0),
                    "S_NET": MosfetVoltageInterval(minimum_v=-1.0, maximum_v=1.0),
                },
            ),
        ),
        requirements=(
            MosfetStressRequirement(
                id="switch-q1",
                reference="Q1",
                expected_symbol="Synthetic:Q_NMOS_GDS",
                expected_footprint="Synthetic:TO-220",
                expected_part_id="SYN-NMOS-001",
                drain_pin="Q1.1",
                drain_function="D",
                drain_net="D_NET",
                gate_pin="Q1.2",
                gate_function="G",
                gate_net="G_NET",
                source_pin="Q1.3",
                source_function="S",
                source_net="S_NET",
                rated_maximum_vds_v=60.0,
                rated_maximum_vgs_v=20.0,
                maximum_utilization_fraction=0.9,
                rating_source="Synthetic datasheet rev A, absolute maximum ratings",
                rating_conditions="Synthetic reviewed operating conditions",
                stress_basis="Synthetic steady-state terminal-potential envelope",
            ),
        ),
    )


def netlist(*, fault: str | None = None) -> NetlistContract:
    symbol = "Synthetic:Q_NMOS_GDS"
    footprint = "Synthetic:TO-220"
    part_id = "SYN-NMOS-001"
    numbers = ("1", "2", "3")
    functions = {"Q1.1": "D", "Q1.2": "G", "Q1.3": "S"}
    assignments = {"D_NET": ("Q1.1",), "G_NET": ("Q1.2",), "S_NET": ("Q1.3",)}
    dnp: tuple[str, ...] = ()
    if fault == "wrong-symbol":
        symbol = "Synthetic:Q_PMOS_GDS"
    elif fault == "wrong-footprint":
        footprint = "Synthetic:SOT-23"
    elif fault == "wrong-part-id":
        part_id = "SYN-NMOS-002"
    elif fault == "wrong-inventory":
        numbers = ("1", "2", "3", "4")
    elif fault == "wrong-drain-function":
        functions["Q1.1"] = "S"
    elif fault == "wrong-gate-net":
        assignments = {"D_NET": ("Q1.1",), "G_NET": (), "S_NET": ("Q1.3",), "BIAS": ("Q1.2",)}
    elif fault == "open-source":
        assignments = {"D_NET": ("Q1.1",), "G_NET": ("Q1.2",)}
    elif fault == "dnp":
        dnp = ("Q1",)
    return NetlistContract(
        components={
            "Q1": ComponentContract(
                value="Synthetic N-MOSFET", footprint=footprint, part_id=part_id
            )
        },
        nets={name: pins for name, pins in assignments.items() if pins},
        dnp_components=dnp,
        component_symbols={"Q1": symbol},
        pin_functions=functions,
        component_pin_numbers={"Q1": numbers},
    )


def multi_device_requirement(
    *, q2_drain_on: MosfetVoltageInterval | None = None
) -> MosfetStressAnalysis:
    single = requirement()
    q1 = single.requirements[0]
    q2 = q1.model_copy(
        update={
            "id": "switch-q2",
            "reference": "Q2",
            "drain_pin": "Q2.1",
            "drain_net": "D2_NET",
            "gate_pin": "Q2.2",
            "gate_net": "G2_NET",
            "source_pin": "Q2.3",
            "source_net": "S2_NET",
        }
    )
    states: list[MosfetOperatingState] = []
    for state in single.states:
        potentials = {
            **state.net_potentials,
            "D2_NET": state.net_potentials["D_NET"],
            "G2_NET": state.net_potentials["G_NET"],
            "S2_NET": state.net_potentials["S_NET"],
        }
        if state.id == "on" and q2_drain_on is not None:
            potentials["D2_NET"] = q2_drain_on
        states.append(state.model_copy(update={"net_potentials": potentials}))
    return single.model_copy(update={"states": tuple(states), "requirements": (q1, q2)})


def multi_device_netlist() -> NetlistContract:
    first = netlist()
    return first.model_copy(
        update={
            "components": {**first.components, "Q2": first.components["Q1"].model_copy()},
            "nets": {
                **first.nets,
                "D2_NET": ("Q2.1",),
                "G2_NET": ("Q2.2",),
                "S2_NET": ("Q2.3",),
            },
            "component_symbols": {
                **first.component_symbols,
                "Q2": first.component_symbols["Q1"],
            },
            "pin_functions": {
                **first.pin_functions,
                "Q2.1": "D",
                "Q2.2": "G",
                "Q2.3": "S",
            },
            "component_pin_numbers": {
                **first.component_pin_numbers,
                "Q2": first.component_pin_numbers["Q1"],
            },
        }
    )


def native_netlist_xml(*, fault: str | None = None) -> str:
    expected = netlist(fault=fault)
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    component = ET.SubElement(components, "comp", ref="Q1")
    ET.SubElement(component, "value").text = "Synthetic N-MOSFET"
    ET.SubElement(component, "footprint").text = expected.components["Q1"].footprint
    fields = ET.SubElement(component, "fields")
    ET.SubElement(fields, "field", name="PART_ID").text = expected.components["Q1"].part_id
    if "Q1" in expected.dnp_components:
        ET.SubElement(component, "property", name="dnp", value="true")
    library, part = expected.component_symbols["Q1"].split(":", maxsplit=1)
    ET.SubElement(component, "libsource", lib=library, part=part)
    units = ET.SubElement(component, "units")
    unit = ET.SubElement(units, "unit", name="A")
    pins = ET.SubElement(unit, "pins")
    for number in expected.component_pin_numbers["Q1"]:
        ET.SubElement(pins, "pin", num=number)
    libparts = ET.SubElement(root, "libparts")
    libpart = ET.SubElement(libparts, "libpart", lib=library, part=part)
    pin_table = ET.SubElement(libpart, "pins")
    for pin, function in sorted(expected.pin_functions.items()):
        number = pin.rsplit(".", maxsplit=1)[1]
        ET.SubElement(pin_table, "pin", num=number, name=function, type="passive")
    nets = ET.SubElement(root, "nets")
    for name, assigned in sorted(expected.nets.items()):
        net = ET.SubElement(nets, "net", name=name)
        for pin in assigned:
            _, number = pin.rsplit(".", maxsplit=1)
            ET.SubElement(net, "node", ref="Q1", pin=number)
    return ET.tostring(root, encoding="unicode")


class MosfetStressTests(unittest.TestCase):
    def test_native_pin_functions_and_state_intervals_produce_conservative_stress(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mosfet-netlist-") as directory:
            path = Path(directory) / "netlist.xml"
            path.write_text(native_netlist_xml(), encoding="utf-8")
            observed = read_netlist(path)
        checks = {row.id: row for row in mosfet_stress_checks(requirement(), observed)}
        self.assertEqual(checks["mosfet-stress/switch-q1/identity"].status, "PASS")
        for role in ("drain", "gate", "source"):
            self.assertEqual(checks[f"mosfet-stress/switch-q1/pin-{role}"].status, "PASS")
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/coverage"].status, "PASS")
        self.assertAlmostEqual(
            checks["mosfet-stress/switch-q1/state-on/vds"].observed or 0.0, 52.0 / 60.0
        )
        self.assertAlmostEqual(
            checks["mosfet-stress/switch-q1/state-on/vgs"].observed or 0.0, 12.0 / 20.0
        )
        self.assertIn(
            "combined conservatively", checks["mosfet-stress/switch-q1/state-on/vds"].detail
        )

    def test_interval_bounds_match_exhaustive_endpoint_oracle(self) -> None:
        def exhaustive_bound(first: MosfetVoltageInterval, second: MosfetVoltageInterval) -> float:
            return max(
                abs(first_value - second_value)
                for first_value in (first.minimum_v, first.maximum_v)
                for second_value in (second.minimum_v, second.maximum_v)
            )

        cases = (
            (
                "positive-and-zero-crossing",
                MosfetVoltageInterval(minimum_v=49.0, maximum_v=51.0),
                MosfetVoltageInterval(minimum_v=9.0, maximum_v=11.0),
                MosfetVoltageInterval(minimum_v=-1.0, maximum_v=1.0),
            ),
            (
                "opposite-polarity",
                MosfetVoltageInterval(minimum_v=-12.0, maximum_v=-8.0),
                MosfetVoltageInterval(minimum_v=-1.0, maximum_v=2.0),
                MosfetVoltageInterval(minimum_v=2.0, maximum_v=4.0),
            ),
            (
                "both-ranges-cross-zero",
                MosfetVoltageInterval(minimum_v=-3.0, maximum_v=7.0),
                MosfetVoltageInterval(minimum_v=-9.0, maximum_v=-7.0),
                MosfetVoltageInterval(minimum_v=-5.0, maximum_v=1.0),
            ),
        )
        authored = requirement().requirements[0]
        for state_id, drain, gate, source in cases:
            with self.subTest(state=state_id):
                state = MosfetOperatingState(
                    id=state_id,
                    net_potentials={"D_NET": drain, "G_NET": gate, "S_NET": source},
                )
                spec = requirement().model_copy(
                    update={"required_states": (state_id,), "states": (state,)}
                )
                checks = {row.id: row for row in mosfet_stress_checks(spec, netlist())}
                expected_vds = exhaustive_bound(drain, source)
                expected_vgs = exhaustive_bound(gate, source)
                self.assertAlmostEqual(
                    (checks[f"mosfet-stress/switch-q1/state-{state_id}/vds"].observed or 0.0)
                    * authored.rated_maximum_vds_v,
                    expected_vds,
                )
                self.assertAlmostEqual(
                    (checks[f"mosfet-stress/switch-q1/state-{state_id}/vgs"].observed or 0.0)
                    * authored.rated_maximum_vgs_v,
                    expected_vgs,
                )

    def test_exact_rating_limits_pass_and_overstress_fails(self) -> None:
        authored = requirement()
        exact_requirement = authored.requirements[0].model_copy(
            update={"maximum_utilization_fraction": 1.0}
        )
        spec = requirement().model_copy(
            update={
                "requirements": (exact_requirement,),
                "states": (
                    MosfetOperatingState(
                        id="off",
                        net_potentials={
                            "D_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                            "G_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                            "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                        },
                    ),
                    MosfetOperatingState(
                        id="on",
                        net_potentials={
                            "D_NET": MosfetVoltageInterval(minimum_v=60.0, maximum_v=60.0),
                            "G_NET": MosfetVoltageInterval(minimum_v=20.0, maximum_v=20.0),
                            "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                        },
                    ),
                ),
            }
        )
        equality = {row.id: row for row in mosfet_stress_checks(spec, netlist())}
        self.assertEqual(equality["mosfet-stress/switch-q1/state-on/vds"].status, "PASS")
        self.assertEqual(equality["mosfet-stress/switch-q1/state-on/vgs"].status, "PASS")

        over = spec.model_copy(
            update={
                "states": (
                    spec.states[0],
                    MosfetOperatingState(
                        id="on",
                        net_potentials={
                            "D_NET": MosfetVoltageInterval(minimum_v=60.1, maximum_v=60.1),
                            "G_NET": MosfetVoltageInterval(minimum_v=20.1, maximum_v=20.1),
                            "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                        },
                    ),
                )
            }
        )
        failed = {row.id: row for row in mosfet_stress_checks(over, netlist())}
        self.assertEqual(failed["mosfet-stress/switch-q1/state-on/vds"].status, "FAIL")
        self.assertEqual(failed["mosfet-stress/switch-q1/state-on/vgs"].status, "FAIL")

    def test_identity_and_topology_faults_fail_closed(self) -> None:
        for fault in (
            "wrong-symbol",
            "wrong-footprint",
            "wrong-part-id",
            "wrong-inventory",
            "wrong-drain-function",
            "wrong-gate-net",
            "open-source",
            "dnp",
        ):
            with self.subTest(fault=fault):
                checks = {
                    row.id: row for row in mosfet_stress_checks(requirement(), netlist(fault=fault))
                }
                expected_failure = (
                    "identity"
                    if fault
                    in {
                        "wrong-symbol",
                        "wrong-footprint",
                        "wrong-part-id",
                        "wrong-inventory",
                        "dnp",
                    }
                    else {
                        "wrong-drain-function": "pin-drain",
                        "wrong-gate-net": "pin-gate",
                        "open-source": "pin-source",
                    }[fault]
                )
                self.assertEqual(
                    checks[f"mosfet-stress/switch-q1/{expected_failure}"].status, "FAIL"
                )
                self.assertEqual(
                    checks["mosfet-stress/switch-q1/state-on/vds"].status, "NOT_APPLICABLE"
                )

    def test_missing_state_and_potential_are_explicit_coverage_failures(self) -> None:
        missing_state = requirement().model_copy(update={"states": requirement().states[:1]})
        checks = {row.id: row for row in mosfet_stress_checks(missing_state, netlist())}
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/coverage"].status, "FAIL")
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vds"].status, "NOT_APPLICABLE")

        on_state = requirement().states[1]
        on = on_state.model_copy(
            update={
                "net_potentials": {
                    "G_NET": on_state.net_potentials["G_NET"],
                    "S_NET": on_state.net_potentials["S_NET"],
                }
            }
        )
        missing_potential = requirement().model_copy(
            update={"states": (requirement().states[0], on)}
        )
        checks = {row.id: row for row in mosfet_stress_checks(missing_potential, netlist())}
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/coverage"].status, "FAIL")
        self.assertIn("D_NET", checks["mosfet-stress/switch-q1/state-on/coverage"].detail)
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vds"].status, "NOT_APPLICABLE")
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vgs"].status, "PASS")

    def test_results_are_stable_when_input_mappings_and_records_are_reordered(self) -> None:
        spec = requirement()
        reversed_states = tuple(
            state.model_copy(
                update={"net_potentials": dict(reversed(tuple(state.net_potentials.items())))}
            )
            for state in reversed(spec.states)
        )
        reversed_spec = spec.model_copy(
            update={
                "states": reversed_states,
                "required_states": tuple(reversed(spec.required_states)),
            }
        )
        observed = netlist()
        reversed_netlist = observed.model_copy(
            update={
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "components": dict(reversed(tuple(observed.components.items()))),
            }
        )
        self.assertEqual(
            mosfet_stress_checks(spec, observed),
            mosfet_stress_checks(reversed_spec, reversed_netlist),
        )

    def test_multiple_devices_keep_results_isolated_under_reordering_and_mutation(self) -> None:
        spec = multi_device_requirement()
        observed = multi_device_netlist()
        baseline = {
            row.id: (row.status, row.detail, row.observed, row.unit)
            for row in mosfet_stress_checks(spec, observed)
        }
        reversed_states = tuple(
            state.model_copy(
                update={"net_potentials": dict(reversed(tuple(state.net_potentials.items())))}
            )
            for state in reversed(spec.states)
        )
        reversed_spec = spec.model_copy(
            update={
                "requirements": tuple(reversed(spec.requirements)),
                "states": reversed_states,
                "required_states": tuple(reversed(spec.required_states)),
            }
        )
        reversed_netlist = observed.model_copy(
            update={
                "components": dict(reversed(tuple(observed.components.items()))),
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
            }
        )
        self.assertEqual(
            mosfet_stress_checks(spec, observed),
            mosfet_stress_checks(reversed_spec, reversed_netlist),
        )
        self.assertEqual(baseline["mosfet-stress/switch-q1/state-on/vds"][0], "PASS")
        self.assertEqual(baseline["mosfet-stress/switch-q2/state-on/vds"][0], "PASS")

        fault = multi_device_requirement(
            q2_drain_on=MosfetVoltageInterval(minimum_v=59.0, maximum_v=61.0)
        )
        fault_rows = {
            row.id: (row.status, row.detail, row.observed, row.unit)
            for row in mosfet_stress_checks(fault, observed)
        }
        changed = {row_id for row_id in baseline if baseline[row_id] != fault_rows[row_id]}
        expected_change = "mosfet-stress/switch-q2/state-on/vds"
        self.assertEqual(changed, {expected_change})
        self.assertEqual(fault_rows[expected_change][0], "FAIL")
        self.assertEqual(fault_rows["mosfet-stress/switch-q2/state-on/vgs"][0], "PASS")
        self.assertEqual(fault_rows["mosfet-stress/switch-q1/state-on/vds"][0], "PASS")

    def test_models_reject_invalid_interval_and_non_three_terminal_map(self) -> None:
        with self.assertRaises(ValidationError):
            MosfetVoltageInterval(minimum_v=2.0, maximum_v=1.0)
        original = requirement().requirements[0]
        with self.assertRaises(ValidationError):
            MosfetStressRequirement.model_validate(
                {
                    **original.model_dump(),
                    "source_pin": original.gate_pin,
                    "source_function": original.source_function,
                    "source_net": original.source_net,
                }
            )
        with self.assertRaises(ValidationError):
            MosfetStressRequirement.model_validate({**original.model_dump(), "drain_function": "G"})


if __name__ == "__main__":
    unittest.main()
