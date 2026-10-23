"""Typed contracts for hosted connector fixtures added after the core peer lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract
from tests.connector_footprint_peer_support import (
    native_peer_missing_metadata_netlist,
    peer_netlist,
)
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_signal_netlist,
)
from tests.design_lint_fixtures.connector_peer_missing_metadata_open import (
    missing_metadata_open_peer_netlist,
)


def _named_peer(
    assignments: tuple[str | None, str | None],
    *,
    function: str,
    electrical_type: str,
    value: str = "Synthetic named connector peer",
) -> NetlistContract:
    """Build two similar connector symbols with an explicit shared pin-2 anchor."""
    base = peer_netlist(
        assignments=(assignments, ("COMMON_ANCHOR", "COMMON_ANCHOR")),
        functions=(function, "2"),
        electrical_types=(electrical_type, "passive"),
    )
    components = {
        reference: component.model_copy(update={"value": value, "footprint": "Synthetic:Package"})
        for reference, component in base.components.items()
    }
    open_pins = tuple(
        f"{reference}.1"
        for reference, net in zip(("J1", "J2"), assignments, strict=True)
        if net is None
    )
    return base.model_copy(
        update={
            "components": components,
            "unconnected_nets": {"unconnected": open_pins} if open_pins else {},
        }
    )


def _metadata_peer(
    target_assignments: tuple[str | None, str | None],
    *,
    anchor_assignments: tuple[str | None, str | None] = (
        "COMMON_REFERENCE",
        "COMMON_REFERENCE",
    ),
    target_function: str = "UART_TX",
) -> NetlistContract:
    """Model native metadata-peer symbols with exact pin and net assignments."""
    base = native_peer_missing_metadata_netlist()
    nets: dict[str, tuple[str, ...]] = {}
    for number, assignments in (("1", target_assignments), ("2", anchor_assignments)):
        for reference, net in zip(("J1", "J2"), assignments, strict=True):
            if net is not None:
                nets[net] = (*nets.get(net, ()), f"{reference}.{number}")
    functions = dict(base.pin_functions)
    functions["J2.1"] = target_function
    open_pins = tuple(
        f"{reference}.1"
        for reference, net in zip(("J1", "J2"), target_assignments, strict=True)
        if net is None
    )
    return base.model_copy(
        update={
            "nets": nets,
            "pin_functions": functions,
            "unconnected_nets": {"unconnected": open_pins} if open_pins else {},
        }
    )


def named_connector_peer_fixture_contracts() -> dict[str, NetlistContract]:
    """Match each extended native peer fixture to its typed exported netlist."""
    cases = {
        "footprint-alias-named-power-input-fault": _named_peer(
            ("+3V3", None), function="BIAS_IN", electrical_type="power_in"
        ),
        "footprint-alias-named-power-input-control": _named_peer(
            ("+3V3", "+3V3"), function="BIAS_IN", electrical_type="power_in"
        ),
        "footprint-alias-named-signal-input-fault": _named_peer(
            ("UART_RX", None), function="UART_RX", electrical_type="input"
        ),
        "footprint-alias-named-signal-input-control": _named_peer(
            ("UART_RX", "UART_RX"), function="UART_RX", electrical_type="input"
        ),
        "footprint-alias-named-power-output-fault": _named_peer(
            ("BIAS_OUTPUT", None), function="BIAS_OUT", electrical_type="power_out"
        ),
        "footprint-alias-named-power-output-control": _named_peer(
            ("BIAS_OUTPUT", "BIAS_OUTPUT"), function="BIAS_OUT", electrical_type="power_out"
        ),
        "footprint-alias-named-power-input-divergence-fault": _named_peer(
            ("BIAS_INPUT_A", "BIAS_INPUT_B"),
            function="BIAS_IN",
            electrical_type="power_in",
            value="Synthetic named power-input peer",
        ),
        "footprint-alias-named-power-input-divergence-control": _named_peer(
            ("BIAS_INPUT", "BIAS_INPUT"),
            function="BIAS_IN",
            electrical_type="power_in",
            value="Synthetic named power-input peer",
        ),
        "footprint-alias-named-power-input-all-open-fault": _named_peer(
            (None, None),
            function="BIAS_IN",
            electrical_type="power_in",
            value="Synthetic named power-input peer",
        ),
        "footprint-alias-named-power-input-all-open-control": _named_peer(
            ("BIAS_INPUT", "BIAS_INPUT"),
            function="BIAS_IN",
            electrical_type="power_in",
            value="Synthetic named power-input peer",
        ),
        "footprint-alias-named-power-output-divergence-fault": _named_peer(
            ("BIAS_OUTPUT_A", "BIAS_OUTPUT_B"),
            function="BIAS_OUT",
            electrical_type="power_out",
            value="Synthetic named power-output peer",
        ),
        "footprint-alias-named-power-output-divergence-control": _named_peer(
            ("BIAS_OUTPUT", "BIAS_OUTPUT"),
            function="BIAS_OUT",
            electrical_type="power_out",
            value="Synthetic named power-output peer",
        ),
        "footprint-alias-named-power-output-all-open-fault": _named_peer(
            (None, None),
            function="BIAS_OUT",
            electrical_type="power_out",
            value="Synthetic named power-output peer",
        ),
        "footprint-alias-named-power-output-all-open-control": _named_peer(
            ("BIAS_OUTPUT", "BIAS_OUTPUT"),
            function="BIAS_OUT",
            electrical_type="power_out",
            value="Synthetic named power-output peer",
        ),
        "footprint-alias-named-signal-divergence-fault": _named_peer(
            ("UART_TX_A", "UART_TX_B"),
            function="UART_TX",
            electrical_type="output",
            value="Synthetic named signal-output peer",
        ),
        "footprint-alias-named-signal-output-fault": _named_peer(
            ("UART_TX", None),
            function="UART_TX",
            electrical_type="output",
            value="Synthetic named signal-output peer",
        ),
        "footprint-alias-named-signal-output-control": _named_peer(
            ("UART_TX", "UART_TX"),
            function="UART_TX",
            electrical_type="output",
            value="Synthetic named signal-output peer",
        ),
        "footprint-alias-named-signal-all-open-fault": _named_peer(
            (None, None),
            function="UART_TX",
            electrical_type="output",
            value="Synthetic named signal-output peer",
        ),
        "footprint-alias-named-signal-all-open-control": _named_peer(
            ("UART_TX", "UART_TX"),
            function="UART_TX",
            electrical_type="output",
            value="Synthetic named signal-output peer",
        ),
        "footprint-alias-named-signal-mode-dependent-open-fault": _named_peer(
            ("DATA_IO", None),
            function="DATA_IO",
            electrical_type="bidirectional",
            value="Synthetic mode-dependent signal peer",
        ),
        "footprint-alias-named-signal-mode-dependent-open-control": _named_peer(
            ("DATA_IO", "DATA_IO"),
            function="DATA_IO",
            electrical_type="bidirectional",
            value="Synthetic mode-dependent signal peer",
        ),
        "footprint-alias-named-passive-open-fault": _named_peer(
            ("AUX_DETECT", None),
            function="AUX_DETECT",
            electrical_type="passive",
            value="Synthetic named passive signal peer",
        ),
        "footprint-alias-named-passive-open-control": _named_peer(
            ("AUX_DETECT", "AUX_DETECT"),
            function="AUX_DETECT",
            electrical_type="passive",
            value="Synthetic named passive signal peer",
        ),
        "footprint-alias-named-passive-divergence-fault": _named_peer(
            ("AUX_DETECT_A", "AUX_DETECT_B"),
            function="AUX_DETECT",
            electrical_type="passive",
            value="Synthetic named passive divergence peer",
        ),
        "footprint-alias-named-passive-divergence-control": _named_peer(
            ("AUX_DETECT", "AUX_DETECT"),
            function="AUX_DETECT",
            electrical_type="passive",
            value="Synthetic named passive divergence peer",
        ),
        "footprint-alias-peer-metadata-fault": _metadata_peer(
            ("UART_RX_NET", "UART_TX_NET")
        ),
        "footprint-alias-peer-metadata-control": _metadata_peer(
            ("SHARED_PORT", "SHARED_PORT")
        ),
        "footprint-alias-peer-metadata-open-fault": _metadata_peer(
            ("UART_RX_NET", None)
        ),
        "footprint-alias-peer-metadata-open-control": _metadata_peer(
            ("UART_RX_NET", None), anchor_assignments=("REFERENCE_A", "REFERENCE_B")
        ),
        "footprint-alias-peer-missing-metadata-fault": native_peer_missing_metadata_netlist(),
        "footprint-alias-peer-missing-metadata-control": native_peer_missing_metadata_netlist(
            common_target=True
        ),
        "footprint-alias-part-id-peer-missing-metadata-fault": native_peer_missing_metadata_netlist(
            part_ids=("SYNTHETIC-PEER-001", "synthetic-peer-001")
        ),
        "footprint-alias-part-id-peer-missing-metadata-control": native_peer_missing_metadata_netlist(
            common_target=True,
            part_ids=("SYNTHETIC-PEER-001", "synthetic-peer-001"),
        ),
        "footprint-alias-peer-missing-metadata-open-fault": missing_metadata_open_peer_netlist(),
        "footprint-alias-peer-missing-metadata-open-control": missing_metadata_open_peer_netlist(
            target_assignments=("SHARED_PORT", "SHARED_PORT")
        ),
        "mapped-interface-signal-unassigned-fault": mapped_interface_signal_netlist(),
        "mapped-interface-signal-unassigned-control": mapped_interface_signal_netlist(
            target_net="UART_RX"
        ),
    }
    return cases
