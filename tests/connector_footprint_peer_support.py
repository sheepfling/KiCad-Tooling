"""Synthetic typed-netlist fixtures shared by footprint-alias peer regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

FOOTPRINT_PEER_RULE_ID = "connector.footprint_peer_pin_assignment_divergence"
FOOTPRINT_OPEN_RULE_ID = "connector.footprint_peer_pin_open_outlier"
FOOTPRINT_ALL_OPEN_RULE_ID = "connector.footprint_peer_pin_all_open"
NETLIST_SHA256 = "a" * 64


def peer_netlist(
    *,
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("GND", "GND"),
        ("DATA_A", "DATA_B"),
    ),
    functions: tuple[str, str] = ("Pin_1", "Pin_2"),
    electrical_types: tuple[str, str] = ("passive", "passive"),
    part_id: str | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    open_pin: str | None = None,
    ambiguous_pin: str | None = None,
) -> NetlistContract:
    """Build two native-metadata-matched alias peers with controlled assignments."""
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Connector_2x1",
            part_id=part_id,
        )
        for reference in ("J1", "J2")
    }
    nets: dict[str, tuple[str, ...]] = {}
    for number, pair in enumerate(assignments, start=1):
        for reference, net in zip(("J1", "J2"), pair, strict=True):
            pin = f"{reference}.{number}"
            if net is not None and pin != open_pin:
                nets[net] = (*nets.get(net, ()), pin)
    if ambiguous_pin is not None:
        nets["SYNTHETIC_AMBIGUOUS_NET"] = (
            *nets.get("SYNTHETIC_AMBIGUOUS_NET", ()),
            ambiguous_pin,
        )
    pin_numbers = {reference: ("1", "2") for reference in ("J1", "J2")}
    if incomplete_inventory:
        pin_numbers["J2"] = ("1",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:GenericPort", "J2": "Synthetic:GenericPortAlias"},
        component_pin_numbers=pin_numbers,
        pin_functions={
            f"{reference}.{number}": function
            for reference in ("J1", "J2")
            for number, function in enumerate(functions, start=1)
        },
        pin_electrical_types={
            f"{reference}.{number}": electrical_types[int(number) - 1]
            for reference in ("J1", "J2")
            for number in ("1", "2")
            if f"{reference}.{number}" != missing_metadata_pin
        },
    )


def peer_metadata_divergence_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("COMMON_REFERENCE", "COMMON_REFERENCE"),
    target_assignments: tuple[str | None, str | None] = ("UART_RX_NET", "UART_TX_NET"),
    part_id: str | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_pin: str | None = None,
) -> NetlistContract:
    """Build aliases with different native pin roles and controlled net assignments."""
    observed = peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        part_id=part_id,
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        ambiguous_pin=ambiguous_pin,
    )
    functions = {
        **observed.pin_functions,
        "J1.2": "UART_RX",
        "J2.2": "UART_TX",
    }
    electrical_types = {
        **observed.pin_electrical_types,
        "J1.2": "input",
        "J2.2": "output",
    }
    if missing_metadata_pin is not None:
        functions.pop(missing_metadata_pin, None)
        electrical_types.pop(missing_metadata_pin, None)
    return observed.model_copy(
        update={"pin_functions": functions, "pin_electrical_types": electrical_types}
    )


def peer_missing_metadata_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = (
        "COMMON_REFERENCE",
        "COMMON_REFERENCE",
    ),
    target_assignments: tuple[str | None, str | None] = ("UART_RX_NET", "UART_TX_NET"),
    missing_fields: tuple[str, ...] = ("pin_function",),
    missing_reference: str = "J2",
    placeholder_function: str | None = "~",
    part_id: str | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    ambiguous_pin: str | None = None,
) -> NetlistContract:
    """Build exact peer assignments while withholding selected native metadata."""
    observed = peer_metadata_divergence_netlist(
        anchor_assignments=anchor_assignments,
        target_assignments=target_assignments,
        part_id=part_id,
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        ambiguous_pin=ambiguous_pin,
    )
    functions = dict(observed.pin_functions)
    electrical_types = dict(observed.pin_electrical_types)
    pin = f"{missing_reference}.2"
    for field in missing_fields:
        if field == "pin_function":
            if placeholder_function is None:
                functions.pop(pin, None)
            else:
                functions[pin] = placeholder_function
        elif field == "pin_electrical_type":
            electrical_types.pop(pin, None)
        else:
            raise ValueError(f"Unsupported synthetic metadata field: {field}")
    return observed.model_copy(
        update={"pin_functions": functions, "pin_electrical_types": electrical_types}
    )


def native_peer_missing_metadata_netlist(*, common_target: bool = False) -> NetlistContract:
    """Model the numbered pins and assignments in the checked-in native pair."""
    references = ("J1", "J2")
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic peer metadata connector",
                footprint="Synthetic:Package",
            )
            for reference in references
        },
        nets={
            "COMMON_REFERENCE": ("J1.2", "J2.2"),
            **(
                {"SHARED_PORT": ("J1.1", "J2.1")}
                if common_target
                else {"UART_RX_NET": ("J1.1",), "UART_TX_NET": ("J2.1",)}
            ),
        },
        component_symbols={
            "J1": "Lint:PeerMetadataDivergenceA",
            "J2": "Lint:PeerMetadataDivergenceB",
        },
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            "J1.1": "UART_RX",
            "J2.1": "~",
            "J1.2": "2",
            "J2.2": "2",
        },
        pin_electrical_types={
            "J1.1": "input",
            "J2.1": "output",
            "J1.2": "passive",
            "J2.2": "passive",
        },
    )


def named_power_input_divergence_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("BIAS_A", "BIAS_B"),
    function: str = "BIAS_IN",
    electrical_type: str = "power_in",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
) -> NetlistContract:
    """Build a source-like named power-input split or valid connector control."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
    )


def named_power_input_all_open_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = (None, None),
    function: str = "BIAS_IN",
    electrical_type: str = "power_in",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build a named power-input contact left open across every alias peer."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_power_output_all_open_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = (None, None),
    function: str = "BIAS_OUT",
    electrical_type: str = "power_out",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build a named power-output contact left open across every alias peer."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_signal_all_open_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = (None, None),
    function: str = "UART_TX",
    electrical_type: str = "output",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build a named signal contact left open across every alias peer."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_signal_mode_dependent_open_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("DATA_BUS", None),
    function: str = "DATA_IO",
    electrical_type: str = "bidirectional",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build a named bidirectional or high-impedance contact open on one peer."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_passive_contact_open_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("AUX_BUS", None),
    function: str = "AUX_DETECT",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build a named passive contact open on one connector-alias peer."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", "passive"),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_passive_contact_divergence_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("AUX_A", "AUX_B"),
    function: str = "AUX_DETECT",
    electrical_type: str = "passive",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    ambiguous_target: bool = False,
) -> NetlistContract:
    """Build named passive contacts assigned to different nets on alias peers."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def named_power_output_divergence_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("OUTPUT_A", "OUTPUT_B"),
    function: str = "AUX_OUT",
    electrical_type: str = "power_out",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
    ambiguous_target: bool = False,
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
) -> NetlistContract:
    """Build a source-like named power-output split or valid connector control."""
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("Pin_1", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
        ambiguous_pin="J1.2" if ambiguous_target else None,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )


def peer_pin_reachability_netlists() -> tuple[NetlistContract, ...]:
    """Provide synthetic alias cases for footprint-peer rule reachability."""
    return (
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", "DATA_B"))),
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None))),
        peer_netlist(
            assignments=(("GND", "GND"), ("BIAS_IN", None)),
            functions=("GND", "BIAS_IN"),
            electrical_types=("passive", "power_in"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("UART_RX", None)),
            functions=("GND", "UART_RX"),
            electrical_types=("passive", "input"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("BIAS_OUT", None)),
            functions=("GND", "BIAS_OUT"),
            electrical_types=("passive", "power_out"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("UART_TX", None)),
            functions=("GND", "UART_TX"),
            electrical_types=("passive", "output"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("UART_TX_A", "UART_TX_B")),
            functions=("GND", "UART_TX"),
            electrical_types=("passive", "output"),
        ),
        named_power_input_divergence_netlist(),
        named_power_input_all_open_netlist(),
        named_power_output_divergence_netlist(),
        peer_missing_metadata_netlist(),
        peer_netlist(assignments=(("GND", "GND"), (None, None))),
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Evaluate one synthetic connector observation with the supplied policy."""
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-footprint-alias-peer-pins",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())
