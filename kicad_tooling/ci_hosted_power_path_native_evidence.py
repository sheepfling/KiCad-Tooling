"""Validate native evidence for synthetic power-path fixture topologies."""

from __future__ import annotations

from .hwrepo.models import NetlistContract
from .hwrepo.power_paths import PowerPathMismatch


def validate_power_path_fixture_netlist(
    case: str,
    observed: NetlistContract,
    mismatches: tuple[PowerPathMismatch, ...],
) -> tuple[str, ...]:
    if case in {"diode-control", "diode-reverse-fault", "schottky-diode-control"}:
        expected_source_pin, expected_load_pin = (
            ("D1.1", "D1.2") if case == "diode-reverse-fault" else ("D1.2", "D1.1")
        )
        expected_symbol = "Device:D_Schottky" if case == "schottky-diode-control" else "Device:D"
        if (
            observed.component_symbols.get("D1") != expected_symbol
            or observed.component_pin_numbers.get("D1") != ("1", "2")
            or observed.pin_functions.get("D1.1") != "K"
            or observed.pin_functions.get("D1.2") != "A"
            or expected_source_pin not in observed.nets.get("VIN", ())
            or expected_load_pin not in observed.nets.get("VLOAD", ())
        ):
            raise ValueError(
                f"Native {case} does not preserve the exact diode identity, pin roles, "
                "and source/load assignments"
            )
    if case in {"bridged-jumper-control", "open-jumper-fault"}:
        expected_symbol = (
            "Jumper:SolderJumper_2_Open"
            if case == "open-jumper-fault"
            else "Jumper:SolderJumper_2_Bridged"
        )
        if (
            observed.component_symbols.get("JP1") != expected_symbol
            or observed.component_pin_numbers.get("JP1") != ("1", "2")
            or observed.pin_functions.get("JP1.1") != "A"
            or observed.pin_functions.get("JP1.2") != "B"
            or "JP1.1" not in observed.nets.get("VIN", ())
            or "JP1.2" not in observed.nets.get("VLOAD", ())
        ):
            raise ValueError(
                f"Native {case} does not preserve exact solder-jumper identity, "
                "pin roles, and source/load assignments"
            )
    if case in {
        "bridged-three-pin12-control",
        "bridged-three-pin123-control",
        "bridged-three-pin12-unbridged-terminal-fault",
    }:
        expected_symbol = (
            "Jumper:SolderJumper_3_Bridged123"
            if case == "bridged-three-pin123-control"
            else "Jumper:SolderJumper_3_Bridged12"
        )
        expected_load_pin = "JP1.2" if case == "bridged-three-pin12-control" else "JP1.3"
        expected_spare_pin = "JP1.3" if case == "bridged-three-pin12-control" else "JP1.2"
        expected_spare_net = (
            "JP_UNUSED_3" if case == "bridged-three-pin12-control" else "JP_UNUSED_2"
        )
        if (
            observed.component_symbols.get("JP1") != expected_symbol
            or observed.component_pin_numbers.get("JP1") != ("1", "2", "3")
            or observed.pin_functions.get("JP1.1") != "A"
            or observed.pin_functions.get("JP1.2") != "C"
            or observed.pin_functions.get("JP1.3") != "B"
            or "JP1.1" not in observed.nets.get("VIN", ())
            or expected_load_pin not in observed.nets.get("VLOAD", ())
            or expected_spare_pin not in observed.nets.get(expected_spare_net, ())
            or expected_spare_pin in observed.nets.get("VIN", ())
            or expected_spare_pin in observed.nets.get("VLOAD", ())
        ):
            raise ValueError(
                f"Native {case} does not preserve exact three-terminal jumper identity, "
                "pin roles, bridge-specific endpoints, and separate terminal net"
            )
    if case in {"control", "isolated-control"} and mismatches:
        raise ValueError(f"Native power-path control mismatched: {mismatches}")
    if case in {"fault", "custom-capacitor-fault", "opaque-capacitor-fault"} and (
        len(mismatches) != 1 or mismatches[0].issues != ("FB1.1 is assigned to GND; expected VIN",)
    ):
        raise ValueError(
            f"Native wrong-rail fault differs from the exact mapped expectation: {mismatches}"
        )
    if case == "isolated-control" and (
        tuple(observed.nets.get("ISO_RETURN", ())) != ("C1.2",) or "GND" in observed.nets
    ):
        raise ValueError(
            "Native isolated-return control does not preserve a separate ISO_RETURN net"
        )
    expected_return_names = ("ISO_RETURN",) if case == "isolated-control" else ("GND",)
    observed_return_names = tuple(name for name in ("GND", "ISO_RETURN") if name in observed.nets)
    if observed_return_names != expected_return_names:
        raise ValueError(
            f"Native power-path {case} return-net evidence differs from expectation: "
            f"{observed_return_names}"
        )
    if case in {"external-source-control", "dnp-external-source-fault"}:
        source_is_dnp = case == "dnp-external-source-fault"
        source_reference = "J1"
        source_net_pins = tuple(observed.nets.get("AUX_INPUT", ()))
        return_net_pins = tuple(observed.nets.get("GND", ()))
        dnp_references = {item.casefold() for item in observed.dnp_components}
        if observed.component_symbols.get(source_reference) != "Synthetic:ExternalSupply":
            raise ValueError(f"Native {case} does not preserve the external source symbol identity")
        if observed.component_pin_numbers.get(source_reference) != ("1", "2"):
            raise ValueError(f"Native {case} does not preserve the two-pin source inventory")
        if observed.pin_electrical_types.get("J1.1") != "power_out":
            raise ValueError(f"Native {case} does not preserve J1.1 power_out evidence")
        if "J1.1" not in source_net_pins or "FB1.1" not in source_net_pins:
            raise ValueError(f"Native {case} does not preserve the custom source rail")
        if "J1.2" not in return_net_pins:
            raise ValueError(f"Native {case} does not preserve the source return pin")
        if (source_reference.casefold() in dnp_references) != source_is_dnp:
            raise ValueError(f"Native {case} does not preserve its fitted/DNP source state")
    if case in {"alternate-source-control", "both-sources-dnp-fault"}:
        dnp_references = {item.casefold() for item in observed.dnp_components}
        expected_source_nets = {"J1": "AUX_INPUT", "J2": "ALT_INPUT"}
        for reference, source_net in expected_source_nets.items():
            if observed.component_symbols.get(reference) != "Synthetic:ExternalSupply":
                raise ValueError(
                    f"Native {case} does not preserve {reference} source symbol identity"
                )
            if observed.component_pin_numbers.get(reference) != ("1", "2"):
                raise ValueError(f"Native {case} does not preserve {reference} two-pin inventory")
            if observed.pin_electrical_types.get(f"{reference}.1") != "power_out":
                raise ValueError(
                    f"Native {case} does not preserve {reference}.1 power_out evidence"
                )
            if f"{reference}.1" not in observed.nets.get(source_net, ()):
                raise ValueError(f"Native {case} does not preserve {reference} on {source_net}")
            if f"{reference}.2" not in observed.nets.get("GND", ()):
                raise ValueError(f"Native {case} does not preserve {reference} on GND")
        expected_branch_pins = {
            "AUX_INPUT": {"J1.1", "FB1.1"},
            "ALT_INPUT": {"J2.1", "FB2.1"},
            "VLOAD": {"FB1.2", "FB2.2", "U2.1", "C1.1"},
        }
        if any(
            not pins.issubset(set(observed.nets.get(net, ())))
            for net, pins in expected_branch_pins.items()
        ) or dnp_references != ({"j1"} if case == "alternate-source-control" else {"j1", "j2"}):
            raise ValueError(
                f"Native {case} must preserve distinct source branches converging on VLOAD, "
                "with expected DNP source population"
            )
    return observed_return_names
