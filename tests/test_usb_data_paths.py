"""Synthetic PHY-specific USB data-path lint regressions."""

from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    ReferenceBondRequirement,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
    UsbReferencePinRequirement,
)
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches


def usb_data_map(
    topology: Literal["direct", "series_resistor"] = "series_resistor",
) -> UsbDataPathMap:
    if topology == "direct":
        positive = UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP",
            topology="direct",
        )
        negative = UsbDataPathLineRequirement(
            line="D-",
            connector_pin="J1.2",
            phy_pin="U1.2",
            connector_net="USB_DM",
            phy_net="USB_DM",
            topology="direct",
        )
        phy_symbol = "Synthetic:STM32F103"
        basis = (
            "STMicroelectronics AN4879 Rev 12, FAQ: the internal FS PHY includes output "
            "matching impedance; this project selects a direct schematic path."
        )
    else:
        positive = UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP_PORT",
            phy_net="USB_DP_PHY",
            topology="series_resistor",
            series_resistor=UsbDataSeriesResistorRequirement(
                reference="R1",
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                minimum_ohms=27,
                maximum_ohms=27,
            ),
        )
        negative = UsbDataPathLineRequirement(
            line="D-",
            connector_pin="J1.2",
            phy_pin="U1.2",
            connector_net="USB_DM_PORT",
            phy_net="USB_DM_PHY",
            topology="series_resistor",
            series_resistor=UsbDataSeriesResistorRequirement(
                reference="R2",
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                minimum_ohms=27,
                maximum_ohms=27,
            ),
        )
        phy_symbol = "Synthetic:TUSB2036"
        basis = (
            "TI TUSB2036 datasheet Rev I, Section 9.2: approximately 27 ohm series "
            "resistors are required on USB DP/DM pairs; this project selects 27R."
        )
    return UsbDataPathMap(
        basis="Synthetic project-approved USB data interface disposition",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-port-1",
                basis=basis,
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbA",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol=phy_symbol,
                expected_phy_footprint="Synthetic:QFN",
                positive=positive,
                negative=negative,
            ),
        ),
    )


def usb_bonded_reference_map() -> UsbDataPathMap:
    base = usb_data_map()
    interface = base.interfaces[0].model_copy(
        update={
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.3", net="USB_GND"),),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
            "reference_policy": "bonded",
            "reference_bond": ReferenceBondRequirement(
                reference="R3",
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                expected_value="0R",
                side_a_pin="R3.1",
                side_b_pin="R3.2",
                side_a_net="USB_GND",
                side_b_net="BOARD_GND",
            ),
        }
    )
    return base.model_copy(update={"interfaces": (interface,)})


def usb_netlist(
    topology: Literal["direct", "series_resistor"] = "series_resistor",
    *,
    fault: str | None = None,
) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(
            value="STM32F103C8T6" if topology == "direct" else "TUSB2036",
            footprint="Synthetic:QFN",
        ),
    }
    symbols = {
        "J1": "Synthetic:UsbA",
        "U1": "Synthetic:STM32F103" if topology == "direct" else "Synthetic:TUSB2036",
    }
    pin_numbers = {"J1": ("1", "2"), "U1": ("1", "2")}
    if topology == "direct":
        nets: dict[str, tuple[str, ...]] = {
            "USB_DP": ("J1.1", "U1.1"),
            "USB_DM": ("J1.2", "U1.2"),
        }
    else:
        components.update(
            {
                "R1": ComponentContract(value="27R", footprint="Synthetic:0603"),
                "R2": ComponentContract(value="27R", footprint="Synthetic:0603"),
            }
        )
        symbols.update({"R1": "Device:R", "R2": "Device:R"})
        pin_numbers.update({"R1": ("1", "2"), "R2": ("1", "2")})
        nets = {
            "USB_DP_PORT": ("J1.1", "R1.1"),
            "USB_DP_PHY": ("R1.2", "U1.1"),
            "USB_DM_PORT": ("J1.2", "R2.1"),
            "USB_DM_PHY": ("R2.2", "U1.2"),
        }
        if fault == "missing-dp-resistor":
            components.pop("R1")
            symbols.pop("R1")
            pin_numbers.pop("R1")
            nets["USB_DP_PORT"] = ("J1.1",)
            nets["USB_DP_PHY"] = ("U1.1",)
        elif fault == "wrong-dp-resistor-value":
            components["R1"] = ComponentContract(value="22R", footprint="Synthetic:0603")
        elif fault == "dnp-dp-resistor":
            return NetlistContract(
                components=components,
                nets=nets,
                dnp_components=("R1",),
                component_symbols=symbols,
                component_pin_numbers=pin_numbers,
                pin_functions={"J1.1": "D+", "J1.2": "D-"},
            )
        elif fault == "wrong-dp-resistor-net":
            nets["USB_DP_PHY"] = ("U1.1",)
            nets["OTHER"] = ("R1.2",)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "U1.1": "DP1" if topology == "series_resistor" else "USB_DP",
            "U1.2": "DM1" if topology == "series_resistor" else "USB_DM",
        },
    )


def usb_bonded_reference_netlist(*, fault: str | None = None) -> NetlistContract:
    base = usb_netlist()
    components = dict(base.components)
    symbols = dict(base.component_symbols)
    pins = dict(base.component_pin_numbers)
    functions = dict(base.pin_functions)
    electrical_types = dict(base.pin_electrical_types)
    nets = dict(base.nets)
    dnp: tuple[str, ...] = ()
    if fault != "missing":
        components["R3"] = ComponentContract(value="0R", footprint="Synthetic:0603")
        symbols["R3"] = "Device:R"
        pins["R3"] = ("1", "2")
        functions.update({"R3.1": "~", "R3.2": "~"})
        electrical_types.update({"R3.1": "passive", "R3.2": "passive"})
        if fault == "wrong-value":
            components["R3"] = ComponentContract(value="10R", footprint="Synthetic:0603")
        elif fault == "wrong-symbol":
            symbols["R3"] = "Synthetic:Bond"
        elif fault == "wrong-footprint":
            components["R3"] = ComponentContract(value="0R", footprint="Synthetic:0805")
        elif fault == "active-pin":
            electrical_types["R3.2"] = "input"
        elif fault == "DNP":
            dnp = ("R3",)
    nets["USB_GND"] = ("J1.3", "R3.1") if fault != "missing" else ("J1.3",)
    nets["BOARD_GND"] = ("U1.3",)
    if fault == "wrong-net":
        nets["USB_GND"] = ("J1.3", "R3.1")
        nets["BOARD_GND"] = ("U1.3",)
        nets["FLOATING_GND"] = ("R3.2",)
    elif fault != "missing":
        nets["BOARD_GND"] = ("U1.3", "R3.2")
    return base.model_copy(
        update={
            "components": components,
            "nets": nets,
            "dnp_components": dnp,
            "component_symbols": symbols,
            "component_pin_numbers": {
                **pins,
                "J1": ("1", "2", "3"),
                "U1": ("1", "2", "3"),
            },
            "pin_functions": {
                **functions,
                "J1.3": "GND",
                "U1.3": "AGND",
            },
            "pin_electrical_types": {
                **electrical_types,
                "J1.1": "passive",
                "J1.2": "passive",
                "J1.3": "passive",
                "U1.1": "input",
                "U1.2": "input",
                "U1.3": "power_in",
            },
        }
    )


def lint_report(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-data-path",
        observed=observed,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        "synthetic-usb-data-path",
        coach,
        DesignLintPolicy(
            usb_data_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def test_documented_integrated_phy_direct_path_is_a_valid_control() -> None:
    mismatches = usb_data_path_mismatches(usb_data_map("direct"), usb_netlist("direct"))
    assert mismatches == ()
    report = lint_report(usb_netlist("direct"), usb_data_map("direct"))
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)
    run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert run.status == "EVALUATED"
    assert (
        run.map_sha256
        == hashlib.sha256(usb_data_map("direct").model_dump_json().encode("utf-8")).hexdigest()
    )
    assert run.requirement_count == 1
    assert run.finding_count == 0


def test_documented_external_phy_and_27r_pair_is_a_valid_control() -> None:
    report = lint_report(usb_netlist(), usb_data_map())
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


def test_exact_bonded_reference_path_is_a_valid_control() -> None:
    path_map = usb_bonded_reference_map()
    report = lint_report(usb_bonded_reference_netlist(), path_map)
    mismatches = usb_data_path_mismatches(path_map, usb_bonded_reference_netlist())

    assert mismatches == ()
    assert not any(
        item.rule_id in {"bus.usb_data_path_mismatch", "bus.usb_peer_reference_review"}
        for item in report.findings
    )
    run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (run.status, run.requirement_count, run.finding_count) == ("EVALUATED", 1, 0)


@pytest.mark.parametrize(
    ("fault", "expected"),
    (
        ("missing", "R3 is absent"),
        ("wrong-value", "R3 value is 10R"),
        ("wrong-symbol", "R3 symbol is Synthetic:Bond"),
        ("wrong-footprint", "R3 footprint is Synthetic:0805"),
        ("active-pin", "R3.2 is not exported as a passive bond pin"),
        ("DNP", "R3 is marked DNP"),
        ("wrong-net", "R3.2 is on FLOATING_GND"),
    ),
    ids=("missing", "value", "symbol", "footprint", "active-pin", "dnp", "net"),
)
def test_bonded_reference_faults_report_exact_component_and_pin_evidence(
    fault: str, expected: str
) -> None:
    report = lint_report(usb_bonded_reference_netlist(fault=fault), usb_bonded_reference_map())
    findings = [item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "usb-port-1: USB reference path"
    assert any(expected in issue for issue in finding.evidence["issues"]), finding.evidence[
        "issues"
    ]
    assert finding.evidence["reference_policy"] == ("bonded",)
    assert finding.evidence["reference_bond"] == ("R3",)
    assert finding.evidence["reference_bond_identity"] == ("Device:R; Synthetic:0603; 0R",)
    assert finding.evidence["reference_bond_side_a"] == ("R3.1 on USB_GND",)
    assert finding.evidence["reference_bond_side_b"] == ("R3.2 on BOARD_GND",)


def test_bonded_reference_fault_evidence_is_order_stable() -> None:
    observed = usb_bonded_reference_netlist(fault="wrong-net")
    reordered = observed.model_copy(
        update={
            field: dict(reversed(tuple(getattr(observed, field).items())))
            for field in (
                "components",
                "nets",
                "component_symbols",
                "component_pin_numbers",
                "pin_functions",
                "pin_electrical_types",
            )
        }
    )
    path_map = usb_bonded_reference_map()
    original = next(
        item
        for item in lint_report(observed, path_map).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    reversed_input = next(
        item
        for item in lint_report(reordered, path_map).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (reversed_input.fingerprint, reversed_input.evidence) == (
        original.fingerprint,
        original.evidence,
    )


def test_bonded_reference_policy_requires_two_distinct_mapped_nets_and_component() -> None:
    interface = usb_bonded_reference_map().interfaces[0]

    def rebuild(**updates: object) -> UsbDataInterfaceRequirement:
        values = interface.model_dump(mode="python")
        values.update(updates)
        return UsbDataInterfaceRequirement.model_validate(values)

    with pytest.raises(ValidationError, match="needs one exact bond component"):
        rebuild(reference_bond=None)
    with pytest.raises(ValidationError, match="needs distinct endpoint nets"):
        rebuild(
            phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="USB_GND"),),
        )
    with pytest.raises(ValidationError, match="must join the mapped connector and PHY nets"):
        bond = interface.reference_bond.model_dump(mode="python")
        bond["side_b_net"] = "UNRELATED_GND"
        rebuild(reference_bond=bond)
    with pytest.raises(ValidationError, match="cannot reuse a data-line series resistor"):
        bond = interface.reference_bond.model_dump(mode="python")
        bond.update(
            {
                "reference": "R1",
                "side_a_pin": "R1.1",
                "side_b_pin": "R1.2",
            }
        )
        rebuild(reference_bond=bond)


def test_missing_required_resistor_is_new_coverage_beyond_named_pair_prompt() -> None:
    missing = usb_netlist(fault="missing-dp-resistor")
    report = lint_report(missing, usb_data_map())
    path_findings = [
        item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    ]
    assert len(path_findings) == 1
    assert path_findings[0].subject == "usb-port-1: USB D+ path"
    assert "R1 is absent" in path_findings[0].evidence["issues"][0]
    assert report.netlist_sha256 == "a" * 64
    assert not any(
        item.rule_id == "bus.usb_data_path_mismatch" for item in lint_report(missing, None).findings
    )
    unconfigured = next(
        item
        for item in lint_report(missing, None).mapped_check_runs
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert unconfigured.status == "NOT_CONFIGURED"
    assert unconfigured.requirement_count == 0
    fault_run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert fault_run.status == "EVALUATED"
    assert fault_run.finding_count == 1


def test_missing_path_evidence_is_order_stable_and_repair_clears_it() -> None:
    path_map = usb_data_map()
    missing = usb_netlist(fault="missing-dp-resistor")
    reordered = missing.model_copy(
        update={
            "components": dict(reversed(tuple(missing.components.items()))),
            "nets": dict(reversed(tuple(missing.nets.items()))),
            "component_symbols": dict(reversed(tuple(missing.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(missing.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(missing.pin_functions.items()))),
        }
    )
    original_report = lint_report(missing, path_map)
    reordered_report = lint_report(reordered, path_map)
    original_finding = next(
        item for item in original_report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    reordered_finding = next(
        item for item in reordered_report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )

    repaired_report = lint_report(usb_netlist(), path_map)
    assert "bus.usb_data_path_mismatch" not in {item.rule_id for item in repaired_report.findings}


@pytest.mark.parametrize(
    ("fault", "expected"),
    (
        ("wrong-dp-resistor-value", "R1 is 22 Ω"),
        ("dnp-dp-resistor", "R1 is marked DNP"),
        ("wrong-dp-resistor-net", "R1 spans"),
    ),
    ids=("wrong-value", "dnp", "wrong-net"),
)
def test_value_dnp_and_wrong_net_mutations_are_detected(fault: str, expected: str) -> None:
    mismatches = usb_data_path_mismatches(usb_data_map(), usb_netlist(fault=fault))
    assert len(mismatches) == 1
    assert any(expected in item for item in mismatches[0].issues)


def test_rule_uses_project_review_block_off_and_exact_ignore_lifecycle() -> None:
    fault = usb_netlist(fault="missing-dp-resistor")
    blocked = lint_report(
        fault,
        usb_data_map(),
        override=DesignLintRuleOverride(
            rule_id="bus.usb_data_path_mismatch",
            mode="block",
            reason="The approved external PHY topology is a release requirement",
        ),
    )
    assert blocked.status == "FAIL"

    finding = next(
        item
        for item in lint_report(fault, usb_data_map()).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    ignored = lint_report(
        fault,
        usb_data_map(),
        ignore=DesignLintIgnore(
            rule_id=finding.rule_id,
            fingerprint=finding.fingerprint,
            reason="Reviewed against the approved assembly option",
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert ignored_finding.disposition == "IGNORED"

    disabled = lint_report(
        fault,
        usb_data_map(),
        override=DesignLintRuleOverride(
            rule_id="bus.usb_data_path_mismatch",
            mode="off",
            reason="The documented PHY disposition is not used in this configuration",
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert disabled_finding.disposition == "RULE_OFF"
    disabled_run = next(
        item for item in disabled.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (disabled_run.status, disabled_run.mode) == ("EVALUATED", "off")
    assert disabled_run.finding_count == 1


def test_contract_rejects_ambiguous_or_unjustified_topologies() -> None:
    with pytest.raises(ValidationError, match="Direct USB data paths"):
        UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP_PHY",
            topology="direct",
        )
    with pytest.raises(ValidationError, match="series-resistor paths"):
        UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP",
            topology="series_resistor",
        )
    with pytest.raises(ValidationError, match="range is reversed"):
        UsbDataSeriesResistorRequirement(
            reference="R1",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            minimum_ohms=28,
            maximum_ohms=27,
        )
