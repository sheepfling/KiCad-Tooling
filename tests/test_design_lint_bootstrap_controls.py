"""Synthetic controls for separating power bootstrap pins from boot straps."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach, control_input_pins

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]


def _bootstrap_capacitor_netlist(
    control_function: str,
    *,
    switch_function: str = "SW",
    switch_reference: str = "U1",
    capacitor_symbol: str = "Device:C",
    capacitor_pin_numbers: tuple[str, ...] = ("1", "2"),
    capacitor_dnp: bool = False,
) -> NetlistContract:
    source = control_input_pins(connected=True, visible_bias=False)
    components = {
        **source.components,
        "C1": ComponentContract(value="100nF", footprint=capacitor_symbol),
    }
    switch_pin = "U1.4" if switch_reference == "U1" else f"{switch_reference}.1"
    if switch_reference != "U1":
        components[switch_reference] = ComponentContract(value="Synthetic switch", footprint="")
    pin_functions = {pin: "GPIO" for pin in source.pin_functions}
    pin_functions.update(
        {
            "U1.3": control_function,
            switch_pin: switch_function,
            "C1.1": "~",
            "C1.2": "~",
        }
    )
    pin_types = {
        **source.pin_electrical_types,
        switch_pin: "output",
        "C1.1": "passive",
        "C1.2": "passive",
    }
    component_symbols = {**source.component_symbols, "C1": capacitor_symbol}
    component_pin_numbers = {
        **source.component_pin_numbers,
        "C1": capacitor_pin_numbers,
    }
    if switch_reference != "U1":
        component_symbols[switch_reference] = "Synthetic:PowerSwitch"
        component_pin_numbers[switch_reference] = ("1",)
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": ("C1",) if capacitor_dnp else (),
            "nets": {
                "BOOTSTRAP_NODE": ("U1.3", "C1.1"),
                "SW_NODE": (switch_pin, "C1.2"),
            },
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_types,
        }
    )


def _relabel_and_reorder_netlist(netlist: NetlistContract) -> NetlistContract:
    updates = {
        field: dict(reversed(tuple(getattr(netlist, field).items())))
        for field in (
            "components",
            "component_symbols",
            "component_pin_numbers",
            "pin_functions",
            "pin_electrical_types",
        )
    }
    updates["nets"] = {
        f"RENAMED_NET_{index}": tuple(reversed(pins))
        for index, (_name, pins) in enumerate(reversed(tuple(netlist.nets.items())), start=1)
    }
    updates["component_pin_numbers"] = {
        reference: tuple(reversed(pin_numbers))
        for reference, pin_numbers in updates["component_pin_numbers"].items()
    }
    return netlist.model_copy(update=updates)


def _connected_bias_signature(
    netlist: NetlistContract,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    report = evaluate("synthetic-bootstrap-pin", coach(netlist), DesignLintPolicy())
    return tuple(
        sorted(
            (finding.rule_id, tuple(finding.evidence["control_inputs"]))
            for finding in report.findings
            if finding.rule_id == "control.connected_control_input_without_visible_bias"
        )
    )


def test_unconnected_bootstrap_pin_is_not_a_boot_mode_control() -> None:
    source = control_input_pins()
    bootstrap = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.3": "BOOTSTRAP"}}
    )

    report = evaluate("synthetic-bootstrap-pin", coach(bootstrap), DesignLintPolicy())

    assert not any(
        item.rule_id == "control.unconnected_control_input" and item.subject == "U1.3: BOOTSTRAP"
        for item in report.findings
    )


def test_unconnected_bare_boot_remains_reviewable() -> None:
    source = control_input_pins()
    boot = source.model_copy(update={"pin_functions": {**source.pin_functions, "U1.3": "BOOT"}})

    report = evaluate("synthetic-bootstrap-pin", coach(boot), DesignLintPolicy())

    assert any(
        item.rule_id == "control.unconnected_control_input" and item.subject == "U1.3: BOOT"
        for item in report.findings
    )


def test_bootstrap_capacitor_node_is_not_a_biased_control_input() -> None:
    report = evaluate(
        "synthetic-bootstrap-pin",
        coach(_bootstrap_capacitor_netlist("BOOTSTRAP")),
        DesignLintPolicy(),
    )

    assert not any(
        item.rule_id == "control.connected_control_input_without_visible_bias"
        and item.evidence["net"] == ("BOOTSTRAP_NODE",)
        for item in report.findings
    )


@pytest.mark.parametrize("switch_function", ("SW", "SW1", "LX2", "PH"))
@pytest.mark.parametrize("capacitor_symbol", ("Device:C", "Device:C_Small"))
def test_bare_boot_with_bootstrap_capacitor_is_not_a_bias_gap(
    switch_function: str,
    capacitor_symbol: str,
) -> None:
    report = evaluate(
        "synthetic-bootstrap-pin",
        coach(
            _bootstrap_capacitor_netlist(
                "BOOT",
                switch_function=switch_function,
                capacitor_symbol=capacitor_symbol,
            )
        ),
        DesignLintPolicy(),
    )

    assert not any(
        item.rule_id == "control.connected_control_input_without_visible_bias"
        and item.evidence["net"] == ("BOOTSTRAP_NODE",)
        for item in report.findings
    )


@pytest.mark.parametrize(
    ("switch_function", "expected"),
    (
        ("SW", ()),
        (
            "GPIO",
            (
                (
                    "control.connected_control_input_without_visible_bias",
                    ("U1.3: BOOT (boot/strap, input_low)",),
                ),
            ),
        ),
    ),
    ids=("proved-bootstrap-topology", "unproven-topology"),
)
def test_bootstrap_classification_is_stable_under_net_relabeling_and_map_order(
    switch_function: str,
    expected: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    source = _bootstrap_capacitor_netlist("BOOT", switch_function=switch_function)
    transformed = _relabel_and_reorder_netlist(source)

    assert _connected_bias_signature(source) == expected
    assert _connected_bias_signature(transformed) == expected


@pytest.mark.parametrize(
    (
        "control_function",
        "switch_function",
        "switch_reference",
        "capacitor_symbol",
        "capacitor_pin_numbers",
        "dnp",
    ),
    (
        ("BOOT", "GPIO", "U1", "Device:C", ("1", "2"), False),
        ("BOOT0", "SW", "U1", "Device:C", ("1", "2"), False),
        ("BOOT", "SW", "U1", "Device:R", ("1", "2"), False),
        ("BOOT", "SW", "U1", "Device:C", ("1", "2"), True),
        ("BOOT", "SW", "U1", "Device:C", ("1", "2", "3"), False),
        ("BOOT", "SW", "U2", "Device:C", ("1", "2"), False),
    ),
    ids=(
        "no-switch-pin",
        "boot-mode-alias",
        "wrong-symbol",
        "dnp-capacitor",
        "extra-pin",
        "different-device",
    ),
)
def test_unproven_bootstrap_topology_keeps_boot_candidate_reviewable(
    control_function: str,
    switch_function: str,
    switch_reference: str,
    capacitor_symbol: str,
    capacitor_pin_numbers: tuple[str, ...],
    dnp: bool,
) -> None:
    report = evaluate(
        "synthetic-bootstrap-pin",
        coach(
            _bootstrap_capacitor_netlist(
                control_function,
                switch_function=switch_function,
                switch_reference=switch_reference,
                capacitor_symbol=capacitor_symbol,
                capacitor_pin_numbers=capacitor_pin_numbers,
                capacitor_dnp=dnp,
            )
        ),
        DesignLintPolicy(),
    )

    assert any(
        item.rule_id == "control.connected_control_input_without_visible_bias"
        and item.evidence["net"] == ("BOOTSTRAP_NODE",)
        for item in report.findings
    )
